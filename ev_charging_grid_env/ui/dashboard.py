"""Very small HTML view for Hugging Face Spaces smoke checks."""

from __future__ import annotations

from html import escape
from typing import Any


def render_dashboard_html(snapshot: dict[str, Any]) -> str:
    """Render a compact status page without frontend dependencies."""

    task_id = escape(str(snapshot.get("task_id", "unknown")))
    step = escape(str(snapshot.get("step", 0)))
    waiting = escape(str(snapshot.get("queue_length", 0)))
    served = escape(str(snapshot.get("vehicles_served", 0)))

    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <title>EV Charging Grid Optimizer</title>
        <style>
          :root {{
            --bg: #f5f1e8;
            --panel: #fff9ef;
            --ink: #1f2a1f;
            --accent: #0f766e;
          }}
          body {{
            margin: 0;
            font-family: Georgia, 'Times New Roman', serif;
            color: var(--ink);
            background:
              radial-gradient(circle at top left, #d1fae5 0, transparent 30%),
              linear-gradient(135deg, #f5f1e8, #e2e8f0);
          }}
          main {{
            max-width: 860px;
            margin: 3rem auto;
            padding: 2rem;
            background: var(--panel);
            border: 1px solid rgba(15, 118, 110, 0.15);
            box-shadow: 0 20px 60px rgba(15, 23, 42, 0.08);
          }}
          h1 {{ margin-top: 0; font-size: 2.4rem; }}
          p {{ line-height: 1.5; }}
          .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 1rem;
            margin-top: 1.5rem;
          }}
          .stat {{
            padding: 1rem;
            background: white;
            border-left: 4px solid var(--accent);
          }}
          .label {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; }}
          .value {{ font-size: 1.5rem; margin-top: 0.35rem; }}
        </style>
      </head>
      <body>
        <main>
          <h1>Multi-Agent EV Charging Grid Optimizer</h1>
          <p>OpenEnv-ready service for smart urban charging coordination.</p>
          <div class="stats">
            <div class="stat"><div class="label">Task</div><div class="value">{task_id}</div></div>
            <div class="stat"><div class="label">Step</div><div class="value">{step}</div></div>
            <div class="stat"><div class="label">Queue</div><div class="value">{waiting}</div></div>
            <div class="stat"><div class="label">Served</div><div class="value">{served}</div></div>
          </div>
        </main>
      </body>
    </html>
    """
