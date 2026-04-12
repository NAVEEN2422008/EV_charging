"""Simple UI helpers for the EV charging grid environment."""

from __future__ import annotations

from typing import Any


def render_dashboard_html(snapshot: dict[str, Any]) -> str:
    """Render a simple HTML dashboard for the EV charging grid snapshot."""
    html_template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>EV Charging Grid Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    .card {{ background: #f7f9fc; border: 1px solid #d4d8df; border-radius: 10px; padding: 18px; max-width: 640px; }}
    .card h1 {{ margin-top: 0; }}
    .metric {{ margin: 10px 0; }}
    .metric strong {{ display: inline-block; width: 160px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>EV Charging Grid Dashboard</h1>
    <div class="metric"><strong>Task ID:</strong> {task_id}</div>
    <div class="metric"><strong>Step:</strong> {step}</div>
    <div class="metric"><strong>Queue Length:</strong> {queue_length}</div>
    <div class="metric"><strong>Vehicles Served:</strong> {vehicles_served}</div>
  </div>
</body>
</html>"""
    
    return html_template.format(
        task_id=snapshot.get('task_id'),
        step=snapshot.get('step'),
        queue_length=snapshot.get('queue_length'),
        vehicles_served=snapshot.get('vehicles_served'),
    )
