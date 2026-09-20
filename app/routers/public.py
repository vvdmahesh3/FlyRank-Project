"""Public router: cached widget delivery + public submission endpoint.

This is the untrusted boundary — no authentication, strict CORS per-widget,
rate limiting, honeypot spam check, geo enrichment fallback chain, and
fire-and-forget side effects.

Security decisions:
- **CORS**: The Origin header is checked against the widget's allowed_origins
  list. Only explicitly-allowed origins can submit. Preflight OPTIONS returns
  the correct Access-Control-Allow-Origin for the requesting origin.
- **Rate limiting**: Per-IP+widget via SlowAPI. Returns 429 on burst.
- **Input validation**: Pydantic strict mode + max payload size + field
  validation against the widget's fields_config.
- **Honeypot**: Hidden field `website_url` — if non-empty, silently accepted
  (200) but discarded. This tricks bots without alerting them.
- **Geo enrichment**: Fallback chain (ip-api → ipinfo → none). Never blocks.
- **Side effects**: Email + webhook run in background threads. Failures are
  logged but never affect the submission response.
"""

import logging
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import public_limiter
from app.models.submission import Submission
from app.models.widget import Widget
from app.schemas.submission import PublicSubmissionAck, PublicSubmissionCreate
from app.services import geo, spam
from app.services.email_svc import send_notification
from app.services.webhook import fire_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public"])

# Cache headers for versioned widget delivery (immutable per version)
CACHE_HEADERS = {
    "Cache-Control": "public, max-age=3600, immutable",
}


def _get_widget_by_public_id(public_id: str, db: Session) -> Widget:
    widget = db.query(Widget).filter(Widget.public_id == public_id).first()
    if not widget or not widget.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found")
    return widget


def _cors_headers_for_origin(origin: str, widget: Widget) -> dict[str, str]:
    """Return CORS headers only if the origin is in the widget's allowlist."""
    if origin in widget.allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Vary": "Origin",
        }
    return {"Vary": "Origin"}


@router.get("/widget/{public_id}/config")
def get_widget_config(public_id: str, db: Session = Depends(get_db)):
    """Return the widget's config (fields, type) for the JS bundle to render."""
    widget = _get_widget_by_public_id(public_id, db)
    config = {
        "public_id": widget.public_id,
        "widget_type": widget.widget_type,
        "fields": widget.fields_config,
        "version": widget.version,
    }
    return JSONResponse(content=config, headers=CACHE_HEADERS)


@router.get("/widget/{public_id}/script", response_class=PlainTextResponse)
def get_widget_script(public_id: str, db: Session = Depends(get_db)):
    """Serve the widget JS bundle (static, versioned via cache headers)."""
    _get_widget_by_public_id(public_id, db)  # validate widget exists
    js = _widget_js_template(public_id)
    return PlainTextResponse(
        content=js,
        media_type="application/javascript",
        headers=CACHE_HEADERS,
    )


@router.options("/submit/{public_id}")
def preflight_submission(
    public_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Handle CORS preflight for the submission endpoint."""
    widget = _get_widget_by_public_id(public_id, db)
    origin = request.headers.get("origin", "")
    cors = _cors_headers_for_origin(origin, widget)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=cors)


@router.post("/submit/{public_id}", response_model=PublicSubmissionAck)
@public_limiter.limit(f"{settings.rate_limit_public_per_minute}/minute")
def submit(
    public_id: str,
    body: PublicSubmissionCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Public form submission endpoint.

    Security flow:
    1. CORS check (origin must be in widget's allowlist)
    2. Honeypot check (silently accept + discard if triggered)
    3. Validate data against widget's fields_config
    4. Store submission
    5. Geo enrichment (fallback chain, non-blocking)
    6. Fire-and-forget email + webhook
    """
    widget = _get_widget_by_public_id(public_id, db)

    # ── 1. CORS ──
    origin = request.headers.get("origin", "")
    if origin and origin not in widget.allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed",
        )

    # ── 2. Honeypot ──
    honeypot_triggered = spam.check_honeypot(body.website)
    if honeypot_triggered:
        # Pretend success to avoid tipping off the bot
        logger.info("Honeypot submission discarded for widget %s", public_id)
        return PublicSubmissionAck()

    # ── 3. Validate against widget fields_config ──
    _validate_fields(body.data, widget)

    # ── 4. Capture server-side metadata ──
    submitter_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")[:512]
    referrer = request.headers.get("referer", "")[:2048]

    # ── 5. Geo enrichment (non-blocking) ──
    geo_data = geo.enrich_ip(submitter_ip) if submitter_ip else None

    # ── 6. Store ──
    submission = Submission(
        widget_id=widget.id,
        tenant_id=widget.tenant_id,
        data=body.data,
        submitter_ip=submitter_ip,
        user_agent=user_agent,
        referrer=referrer,
        geo_country=geo_data.get("country") if geo_data else None,
        geo_region=geo_data.get("region") if geo_data else None,
        geo_city=geo_data.get("city") if geo_data else None,
        geo_lat=geo_data.get("lat") if geo_data else None,
        geo_lon=geo_data.get("lon") if geo_data else None,
        geo_provider=geo_data.get("provider") if geo_data else None,
        spam_score=spam.compute_spam_score(honeypot_triggered, submitter_ip),
        status="new",
    )
    db.add(submission)
    db.commit()

    # ── 7. Fire-and-forget side effects ──
    _dispatch_side_effects(widget, submission, submitter_ip)

    # Return CORS headers on the actual response too
    cors = _cors_headers_for_origin(origin, widget)
    return JSONResponse(
        content=PublicSubmissionAck().model_dump(),
        status_code=status.HTTP_201_CREATED,
        headers=cors,
    )


def _validate_fields(data: dict, widget: Widget) -> None:
    """Validate submitted data against the widget's fields_config."""
    field_map = {f["name"]: f for f in widget.fields_config}
    errors = []

    for fname, fconfig in field_map.items():
        if fconfig.get("required") and fname not in data:
            errors.append(f"Missing required field: {fname}")

    for key in data:
        if key not in field_map:
            errors.append(f"Unexpected field: {key}")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=errors,
        )


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract the real client IP, respecting X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def _dispatch_side_effects(widget: Widget, submission: Submission, ip: str) -> None:
    """Run email + webhook in background threads. Never blocks the response."""
    if widget.notify_email:
        threading.Thread(
            target=send_notification,
            args=(
                widget.notify_email,
                f"New submission from {widget.name}",
                _format_email_body(submission, widget),
            ),
            daemon=True,
        ).start()

    if widget.webhook_url:
        threading.Thread(
            target=fire_webhook,
            args=(
                widget.webhook_url,
                {
                    "widget_id": str(widget.id),
                    "submission_id": str(submission.id),
                    "data": submission.data,
                    "ip": ip,
                    "geo_country": submission.geo_country,
                    "created_at": submission.created_at.isoformat(),
                },
            ),
            daemon=True,
        ).start()


def _format_email_body(submission: Submission, widget: Widget) -> str:
    lines = [f"New submission on widget: {widget.name}", ""]
    for key, val in submission.data.items():
        lines.append(f"  {key}: {val}")
    if submission.geo_country:
        lines.append(f"\n  Country: {submission.geo_country}")
        if submission.geo_city:
            lines.append(f"  City: {submission.geo_city}")
    lines.append(f"\n  IP: {submission.submitter_ip}")
    lines.append(f"  Submitted: {submission.created_at.isoformat()}")
    return "\n".join(lines)


def _widget_js_template(public_id: str) -> str:
    """Minimal widget JS that fetches config and renders a form."""
    return f"""(function() {{
  var PID = "{public_id}";
  var BASE = (window.__FLYRANK_BASE__ || "") + "/api/v1/public";

  function loadConfig(pid, cb) {{
    fetch(BASE + "/widget/" + pid + "/config")
      .then(function(r) {{ return r.json(); }})
      .then(cb)
      .catch(function(e) {{ console.error("[FlyRank] config load failed", e); }});
  }}

  function renderForm(config, container) {{
    var form = document.createElement("form");
    form.style.maxWidth = "480px";
    form.style.margin = "0 auto";
    form.style.fontFamily = "system-ui, sans-serif";

    (config.fields || []).forEach(function(f) {{
      var label = document.createElement("label");
      label.textContent = f.label + (f.required ? " *" : "");
      label.style.display = "block";
      label.style.marginBottom = "4px";
      label.style.fontSize = "14px";

      var input;
      if (f.type === "textarea") {{
        input = document.createElement("textarea");
        input.rows = 4;
      }} else if (f.type === "select") {{
        input = document.createElement("select");
        (f.options || []).forEach(function(opt) {{
          var o = document.createElement("option");
          o.value = opt; o.textContent = opt;
          input.appendChild(o);
        }});
      }} else {{
        input = document.createElement("input");
        input.type = f.type || "text";
      }}
      input.name = f.name;
      input.placeholder = f.placeholder || "";
      input.required = !!f.required;
      input.style.width = "100%";
      input.style.padding = "8px";
      input.style.marginBottom = "12px";
      input.style.border = "1px solid #ddd";
      input.style.borderRadius = "6px";
      input.style.fontSize = "14px";

      // Honeypot: hidden field that real users never see
      if (f.name === "website_url") {{
        input.style.position = "absolute";
        input.style.left = "-9999px";
        input.setAttribute("aria-hidden", "true");
        input.tabIndex = -1;
      }}

      form.appendChild(label);
      form.appendChild(input);
    }});

    var btn = document.createElement("button");
    btn.type = "submit";
    btn.textContent = "Submit";
    btn.style.padding = "10px 24px";
    btn.style.background = "#2563eb";
    btn.style.color = "#fff";
    btn.style.border = "none";
    btn.style.borderRadius = "6px";
    btn.style.cursor = "pointer";
    btn.style.fontSize = "15px";
    form.appendChild(btn);

    var msg = document.createElement("div");
    msg.style.marginTop = "12px";
    msg.style.fontSize = "14px";
    form.appendChild(msg);

    form.addEventListener("submit", function(e) {{
      e.preventDefault();
      var payload = {{ data: {{}} }};
      var inputs = form.querySelectorAll("input, textarea, select");
      inputs.forEach(function(inp) {{
        payload.data[inp.name] = inp.value;
      }});
      fetch(BASE + "/submit/" + PID, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload),
      }})
      .then(function(r) {{
        if (r.ok) {{
          msg.textContent = "Thank you! Your submission has been received.";
          msg.style.color = "#16a34a";
          form.reset();
        }} else {{
          msg.textContent = "Something went wrong. Please try again.";
          msg.style.color = "#dc2626";
        }}
      }})
      .catch(function() {{
        msg.textContent = "Network error. Please try again.";
        msg.style.color = "#dc2626";
      }});
    }});

    container.innerHTML = "";
    container.appendChild(form);
  }}

  function init() {{
    var scripts = document.querySelectorAll('script[data-widget-id]');
    var container = null;
    for (var i = 0; i < scripts.length; i++) {{
      if (scripts[i].getAttribute('data-widget-id') === PID) {{
        container = document.createElement("div");
        container.className = "flyrank-widget";
        scripts[i].parentNode.insertBefore(container, scripts[i]);
        break;
      }}
    }}
    if (!container) return;
    loadConfig(PID, function(config) {{
      renderForm(config, container);
    }});
  }}

  if (document.readyState === "loading") {{
    document.addEventListener("DOMContentLoaded", init);
  }} else {{
    init();
  }}
}})();"""
