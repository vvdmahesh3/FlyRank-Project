"""Embed snippet generation.

Produces a single `<script>` tag that the tenant pastes into their HTML.
The script tag loads the widget JS bundle and passes the widget's public_id
and version as data attributes.

Example output:
    <script src="https://api.flyrank.local/api/v1/public/widget/abc12345/script?v=1"
            data-widget-id="abc12345"
            data-widget-version="1"
            async
            defer></script>
"""

from app.models.widget import Widget


def generate_snippet(widget: Widget, base_url: str = "") -> str:
    """Generate the <script> embed tag for a widget."""
    src = f"{base_url}/api/v1/public/widget/{widget.public_id}/script?v={widget.version}"
    return (
        f'<script src="{src}"\n'
        f'        data-widget-id="{widget.public_id}"\n'
        f'        data-widget-version="{widget.version}"\n'
        f'        async\n'
        f'        defer></script>'
    )
