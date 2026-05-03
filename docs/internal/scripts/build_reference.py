# Parse docs/internal/reference.md and write docs/reference.html
import re
import sys
from pathlib import Path

REPO = Path(__file__).parents[3]
SRC  = REPO / "docs/internal/reference.md"
DEST = REPO / "docs/reference.html"

# ── Parser ────────────────────────────────────────────────────────────────────

def parse(text):
    """Return list of sections: {title, entries: [{cmd, desc, badges, details}]}"""
    sections = []
    current_section = None
    current_entry = None

    for line in text.splitlines():
        # ## Section
        if line.startswith("## "):
            if current_entry:
                current_section["entries"].append(current_entry)
                current_entry = None
            current_section = {"title": line[3:].strip(), "entries": []}
            sections.append(current_section)

        # ### `cmd`
        elif line.startswith("### "):
            if current_entry:
                current_section["entries"].append(current_entry)
            raw = line[4:].strip().strip("`")
            current_entry = {"cmd": raw, "desc": "", "badges": [], "details": ""}

        # > Short desc #Badge1 #Badge2
        elif line.startswith("> ") and current_entry is not None:
            content = line[2:].strip()
            badges = re.findall(r"#(\w+)", content)
            desc = re.sub(r"\s*#\w+", "", content).strip()
            current_entry["desc"] = desc
            current_entry["badges"] = badges

        # Details (non-empty, non-special line)
        elif current_entry is not None and line.strip() and not line.startswith("#") and not line.startswith("---"):
            if current_entry["details"]:
                current_entry["details"] += " " + line.strip()
            else:
                current_entry["details"] = line.strip()

    if current_entry and current_section:
        current_section["entries"].append(current_entry)

    return sections


# ── Renderer ──────────────────────────────────────────────────────────────────

BADGE_LABELS = {"CLI": "CLI", "WebUI": "Web UI", "ROS": "ROS"}

CHEVRON = '<svg class="cmd__chevron" width="12" height="12" viewBox="0 0 12 12" fill="none"><polyline points="4,2 8,6 4,10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

def render_cmd(entry):
    badges_html = "".join(
        f'<span class="badge badge--cli">{BADGE_LABELS.get(b, b)}</span>'
        for b in entry["badges"]
    )
    cmd_html = f'<span class="cmd__code">{entry["cmd"]}</span>'
    return f"""
        <div class="cmd" onclick="toggle(this)">
          <div class="cmd__row">
            {cmd_html}
            <div class="cmd__desc">{entry["desc"]}</div>
            <div class="cmd__badges">{badges_html}</div>
            {CHEVRON}
          </div>
          <div class="cmd__detail"><div class="cmd__detail-inner">{entry["details"]}</div></div>
        </div>"""


def render_section(section):
    entries_html = "".join(render_cmd(e) for e in section["entries"])
    return f"""
    <div class="section">
      <div class="section__title">{section["title"]}</div>
      <div class="cmd-list">{entries_html}
      </div>
    </div>"""


def render_page(sections):
    body = "".join(render_section(s) for s in sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Psilia Edge — Docs</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@300;400&display=swap');

    :root {{
      --color-bg:       #ffffff;
      --color-surface:  #f5f5f5;
      --color-text:     #111111;
      --color-muted:    #777777;
      --color-accent:   #111111;
      --color-dim:      #aaaaaa;
      --font-ui:        'Calibri', 'Gill Sans', sans-serif;
      --font-mono:      'Roboto Mono', monospace;
      --border:         1px solid rgba(0,0,0,0.1);
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: var(--color-bg);
      color: var(--color-text);
      font-family: var(--font-ui);
      font-weight: 300;
      line-height: 1.6;
      min-height: 100vh;
    }}

    .page {{
      max-width: 600px;
      margin: 0 auto;
      padding: 2rem 1.25rem 4rem;
    }}

    .header {{ margin-bottom: 2.5rem; }}

    .brand {{
      font-size: 1rem;
      letter-spacing: 0.1em;
    }}

    .header__sub {{
      font-family: var(--font-mono);
      font-size: 0.65rem;
      color: var(--color-dim);
      letter-spacing: 0.04em;
      margin-top: 0.2rem;
    }}

    .section {{ margin-bottom: 2.5rem; }}

    .section__title {{
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.12em;
      color: var(--color-accent);
      font-weight: 300;
      margin-bottom: 0.75rem;
    }}

    .cmd-list {{
      background: var(--color-surface);
      border-radius: 6px;
      overflow: hidden;
    }}

    .cmd {{ border-bottom: var(--border); }}
    .cmd:last-child {{ border-bottom: none; }}

    .cmd__row {{
      display: flex;
      align-items: baseline;
      gap: 1rem;
      padding: 0.6rem 0.9rem;
      cursor: pointer;
      transition: background 0.15s;
    }}

    .cmd__row:hover {{ background: rgba(0,0,0,0.02); }}

    .cmd__code {{
      font-family: var(--font-mono);
      font-size: 0.75rem;
      white-space: nowrap;
      flex-shrink: 0;
      font-weight: 400;
      color: var(--color-text);
    }}

    .cmd__desc {{
      font-size: 0.75rem;
      color: var(--color-dim);
      font-weight: 300;
    }}

    .cmd__chevron {{
      flex-shrink: 0;
      color: var(--color-dim);
      transition: transform 0.2s;
    }}

    .cmd.open .cmd__chevron {{ transform: rotate(90deg); }}

    .cmd__detail {{
      max-height: 0;
      overflow: hidden;
      transition: max-height 0.25s ease;
    }}

    .cmd.open .cmd__detail {{ max-height: 600px; }}

    .cmd__detail-inner {{
      padding: 0 0.9rem 0.7rem;
      font-size: 0.73rem;
      color: var(--color-muted);
      font-weight: 300;
      line-height: 1.65;
    }}

    .badge {{
      font-family: var(--font-mono);
      font-size: 0.55rem;
      font-weight: 400;
      letter-spacing: 0.04em;
      padding: 0.12rem 0.4rem;
      border-radius: 3px;
      display: inline-block;
      white-space: nowrap;
      color: var(--color-muted);
      border: 1px solid rgba(0,0,0,0.12);
    }}

    .cmd__badges {{
      display: flex;
      gap: 0.35rem;
      margin-left: auto;
    }}
  </style>
</head>
<body>
  <div class="page">

    <div class="header">
      <div class="brand">Psilia Edge</div>
      <div class="header__sub">CLI Reference</div>
    </div>
{body}
  </div>

  <script>
    function toggle(cmd) {{
      cmd.classList.toggle('open');
    }}
  </script>

</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    text = SRC.read_text()
    sections = parse(text)
    html = render_page(sections)
    DEST.write_text(html)
    print(f"wrote {DEST.relative_to(REPO)}")
