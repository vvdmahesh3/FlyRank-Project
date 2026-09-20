# EVIDENCE — FlyRank Capstone

This document provides proof for each requirement. Run the commands below
against a running instance (`docker compose up`) and paste the output here.

---

## REQ-1: Widget Management API (Authenticated CRUD, Tenant-Isolated)

### Register a tenant + user
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"owner@tenant-a.com","password":"testpass123","tenant_name":"Tenant A","full_name":"Alice"}'
```
**Expected:** 201 + JWT token

### Create a widget
```bash
TOKEN="<token from register>"
curl -X POST http://localhost:8000/api/v1/widgets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Contact Form",
    "widget_type": "contact_form",
    "fields_config": [
      {"name":"name","label":"Name","type":"text","required":true},
      {"name":"email","label":"Email","type":"email","required":true},
      {"name":"message","label":"Message","type":"textarea","required":true},
      {"name":"website_url","label":"Website","type":"text","required":false}
    ],
    "allowed_origins": ["http://localhost:5173"]
  }'
```
**Expected:** 201 + widget with public_id

### List widgets
```bash
curl http://localhost:8000/api/v1/widgets -H "Authorization: Bearer $TOKEN"
```
**Expected:** Array with the created widget

### Update widget
```bash
curl -X PUT http://localhost:8000/api/v1/widgets/<widget_id> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Updated Contact Form"}'
```
**Expected:** 200 + version incremented

### Delete widget
```bash
curl -X DELETE http://localhost:8000/api/v1/widgets/<widget_id> \
  -H "Authorization: Bearer $TOKEN"
```
**Expected:** 204

### Tenant isolation proof
Register a second tenant (owner@tenant-b.com), create a widget, then list
widgets as Tenant B — Tenant A's widgets must NOT appear.
```bash
# As Tenant B:
curl http://localhost:8000/api/v1/widgets -H "Authorization: Bearer $TOKEN_B"
```
**Expected:** Only Tenant B's widgets

---

## REQ-2: Embed Snippet Generation

```bash
curl http://localhost:8000/api/v1/widgets/<widget_id>/snippet \
  -H "Authorization: Bearer $TOKEN"
```
**Expected:**
```json
{
  "snippet": "<script src=\"...\"\n        data-widget-id=\"...\"\n        data-widget-version=\"1\"\n        async\n        defer></script>",
  "public_id": "...",
  "version": 1
}
```

---

## REQ-3: Cached Widget Delivery

### Config endpoint
```bash
curl -I http://localhost:8000/api/v1/public/widget/<public_id>/config
```
**Expected header:** `Cache-Control: public, max-age=3600, immutable`

### Script endpoint
```bash
curl -I http://localhost:8000/api/v1/public/widget/<public_id>/script
```
**Expected header:** `Cache-Control: public, max-age=3600, immutable`
**Expected Content-Type:** `application/javascript`

---

## REQ-4: Public Submission Endpoint

### Valid submission
```bash
curl -X POST http://localhost:8000/api/v1/public/submit/<public_id> \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{"data":{"name":"John","email":"john@example.com","message":"Hello!"}}'
```
**Expected:** 201 + `{"success": true, "message": "Thank you!..."}`

### CORS preflight
```bash
curl -X OPTIONS http://localhost:8000/api/v1/public/submit/<public_id> \
  -H "Origin: http://localhost:5173" \
  -H "Access-Control-Request-Method: POST"
```
**Expected:** 204 + `Access-Control-Allow-Origin: http://localhost:5173`

### Rejected origin
```bash
curl -X POST http://localhost:8000/api/v1/public/submit/<public_id> \
  -H "Content-Type: application/json" \
  -H "Origin: http://evil.com" \
  -d '{"data":{"name":"x"}}'
```
**Expected:** 403 Forbidden

### Malformed payload (unexpected field)
```bash
curl -X POST http://localhost:8000/api/v1/public/submit/<public_id> \
  -H "Content-Type: application/json" \
  -d '{"data":{"name":"x","bogus_field":"y"}}'
```
**Expected:** 422 Unprocessable Entity

---

## REQ-5: Protection & Enrichment

### Rate limiting (429 on burst)
```bash
# Fire 15 rapid requests (limit is 10/min):
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/api/v1/public/submit/<public_id> \
    -H "Content-Type: application/json" \
    -H "Origin: http://localhost:5173" \
    -d '{"data":{"name":"test","email":"t@t.com","message":"x"}}'
done
```
**Expected:** First 10 return 201, then 429

### Honeypot (spam silently discarded)
```bash
curl -X POST http://localhost:8000/api/v1/public/submit/<public_id> \
  -H "Content-Type: application/json" \
  -H "Origin: http://localhost:5173" \
  -d '{"data":{"name":"Bot","email":"bot@bot.com","message":"spam","website_url":"http://spam.com"}}'
```
**Expected:** 200/201 (pretends success) but submission is NOT stored

### Geo enrichment fallback chain
Submit from a real IP and check the dashboard — geo_country should be
populated. To test fallback, temporarily break ip-api by setting an
invalid URL and verify ipinfo is used instead.

### Safe side effects
Configure a webhook_url pointing to a dead endpoint. Submit a form.
**Expected:** Submission succeeds (201) even though webhook fails.
Check logs for "Webhook delivery failed" warning.

---

## REQ-6: Owner Dashboard API

### Stats
```bash
curl http://localhost:8000/api/v1/dashboard/stats \
  -H "Authorization: Bearer $TOKEN"
```
**Expected:** JSON with total_widgets, total_submissions, by_status, by_country, top_widgets

### Paginated submissions
```bash
curl "http://localhost:8000/api/v1/dashboard/submissions?page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN"
```
**Expected:** Paginated list with items, total, page, has_next

### Per-widget submissions
```bash
curl "http://localhost:8000/api/v1/dashboard/widgets/<widget_id>/submissions" \
  -H "Authorization: Bearer $TOKEN"
```
**Expected:** Only submissions for that widget

---

## REQ-7: Multi-Tenant Isolation

1. Register Tenant A and Tenant B (separate emails)
2. Create a widget as Tenant A
3. As Tenant B, try to GET Tenant A's widget by ID
```bash
curl http://localhost:8000/api/v1/widgets/<tenant_a_widget_id> \
  -H "Authorization: Bearer $TOKEN_B"
```
**Expected:** 404 Not Found (Tenant B cannot see Tenant A's widget)

4. As Tenant B, try to list submissions — only Tenant B's submissions appear
5. Public submissions to Tenant A's widget are only visible to Tenant A's dashboard

---

## Mailpit Email Verification

1. Open http://localhost:8025
2. Configure a widget with `notify_email: "owner@tenant-a.com"`
3. Submit a form via the public endpoint
4. Check Mailpit UI — a notification email should appear
