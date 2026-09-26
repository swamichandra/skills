#!/usr/bin/env python3
"""
Render a verdict card for is-it-for-jev as portable files, with no host-specific
visual tool required. Plain Python 3.8+, standard library only.

Writes, from one JSON spec:
  <out>.svg   self-contained SVG, dadloop palette, light and dark mode.
              Opens in any browser, attaches to any chat or doc, and embeds in
              Markdown with ![verdict](<out>.svg).
  <out>.mmd   Mermaid flowchart, for hosts that render Mermaid in Markdown
              (GitHub, GitLab, many IDE chat panels) but cannot show files.
  <out>.md    Plain Markdown text card, the fallback that renders everywhere.

Usage:
    python render_verdict.py spec.json --out verdict
    python render_verdict.py --example good|partial|not --out demo

Spec format: see references/visual-style.md, or run --example and read the
printed spec.
"""

import argparse
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
ICONS = json.loads((HERE.parent / "assets" / "icons.json").read_text())

# dadloop palette: (light, dark)
PALETTE = {
    "ink": ("#1f1a14", "#e9e3d6"),
    "mute": ("#6b6157", "#9a9184"),
    "line": ("#d9cdb9", "#34302a"),
    "bg": ("#faf6ee", "#100e0a"),
    "accent": ("#c4521f", "#d97757"),
    "accent-bg": ("#f4e8cc", "#2a2114"),
    "done": ("#5e7d3c", "#8ba86a"),
    "done-bg": ("#eaf3de", "#1b1915"),
    "hold": ("#b07d1f", "#c9a24c"),
    "hold-bg": ("#faeeda", "#211d18"),
    "gray": ("#5f5e5a", "#9a9184"),
    "gray-bg": ("#e9e6df", "#201d18"),
    "problem": ("#b23a2b", "#c96f5a"),
}
VERDICTS = {
    "good": ("good fit for jev", "check", "accent"),
    "partial": ("partial fit for jev", "adjustments", "hold"),
    "not": ("not a fit for jev", "ban", "gray"),
}
FONT = "-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
W, PAD = 600, 32


def text_w(s, size, bold=False):
    """Rough rendered width. Deliberately generous so wrapped text never clips."""
    return len(s) * size * (0.58 if bold else 0.54)


def wrap(s, size, max_w, bold=False):
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if cur and text_w(trial, size, bold) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]


def icon(name, cx, cy, size, cls):
    body = ICONS.get(name) or ICONS["help"]
    s = size / 24
    return (f'<g class="{cls}" fill="none" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" transform="translate({cx - size / 2:.1f},{cy - size / 2:.1f}) '
            f'scale({s:.3f})">{body}</g>')


def render_svg(spec):
    label, badge_icon, tone = VERDICTS[spec["verdict"]]
    out, y = [], PAD
    text_x = PAD + 42 + 16
    max_text = W - text_x - PAD

    # verdict badge
    bt = label.upper()
    bw = 12 + 14 + 6 + text_w(bt, 11, True) + 1.2 * len(bt) + 12
    out.append(f'<rect x="{PAD}" y="{y}" width="{bw:.0f}" height="24" rx="12" class="f-{tone}-bg"/>')
    out.append(icon(badge_icon, PAD + 12 + 7, y + 12, 14, f"s-{tone}"))
    out.append(f'<text x="{PAD + 32}" y="{y + 16}" class="t-{tone}" font-size="11" '
               f'font-weight="700" letter-spacing="1.2">{escape(bt)}</text>')
    y += 24 + 20

    # headline and subtitle
    for line in wrap(spec["headline"], 22, W - 2 * PAD, True):
        y += 22
        out.append(f'<text x="{PAD}" y="{y}" class="t-ink" font-size="22" font-weight="600">{escape(line)}</text>')
        y += 6
    if spec.get("subtitle"):
        y += 4
        for line in wrap(spec["subtitle"], 14, W - 2 * PAD):
            y += 18
            out.append(f'<text x="{PAD}" y="{y}" class="t-mute" font-size="14">{escape(line)}</text>')
    y += 24

    # vertical steps
    steps = spec.get("steps", [])
    for i, st in enumerate(steps):
        stone = st.get("tone", "accent")
        cy = y + 21
        out.append(f'<circle cx="{PAD + 21}" cy="{cy}" r="21" class="f-{stone}-bg"/>')
        out.append(icon(st.get("icon", "help"), PAD + 21, cy, 21, f"s-{stone}"))
        ty = y + 16
        out.append(f'<text x="{text_x}" y="{ty}" class="t-ink" font-size="15" font-weight="600">{escape(st["title"])}</text>')
        block_bottom = ty + 4
        if st.get("detail"):
            dcls = f"t-{st['detail_tone']}" if st.get("detail_tone") in PALETTE else "t-mute"
            for line in wrap(st["detail"], 13, max_text):
                block_bottom += 17
                out.append(f'<text x="{text_x}" y="{block_bottom}" class="{dcls}" font-size="13">{escape(line)}</text>')
        if st.get("pills"):
            px, py = text_x, block_bottom + 8
            for p in st["pills"]:
                pw = text_w(p, 12) + 20
                if px + pw > W - PAD:
                    px, py = text_x, py + 28
                out.append(f'<rect x="{px:.0f}" y="{py}" width="{pw:.0f}" height="22" rx="11" class="f-{stone}-bg"/>')
                out.append(f'<text x="{px + pw / 2:.0f}" y="{py + 15}" class="t-{stone}" font-size="12" '
                           f'text-anchor="middle">{escape(p)}</text>')
                px += pw + 6
            block_bottom = py + 22
        y = max(y + 40, block_bottom + 4)
        if i < len(steps) - 1 or spec.get("branch"):
            is_branch = i == len(steps) - 1
            out.append(icon("corner-down-right" if is_branch else "arrow-down",
                            PAD + 21, y + 13, 16, "s-mute"))
            y += 28

    # branch outcomes: same icon-circle-plus-wrapped-text shape as every step
    # above, stacked vertically. A two-column side-by-side layout looks tidy in
    # a mock but breaks the moment a real title is a sentence rather than one
    # word ("call tool; the model writes the arguments" does not fit in a
    # 200px column), so outcomes get the full row width and the same wrap()
    # used everywhere else.
    if spec.get("branch"):
        for j, b in enumerate(spec["branch"]):
            btone = b.get("tone", "done") if b.get("tone") in ("done", "hold") else "done"
            cy = y + 18
            out.append(f'<circle cx="{PAD + 18}" cy="{cy}" r="18" class="f-{btone}-bg"/>')
            out.append(icon(b.get("icon", "check"), PAD + 18, cy, 18, f"s-{btone}"))
            ty = y + 14
            if b.get("label"):
                out.append(f'<text x="{text_x}" y="{ty}" class="t-mute" font-size="12">{escape(b["label"])}</text>')
                ty += 18
            for line in wrap(b["title"], 14, max_text, True):
                out.append(f'<text x="{text_x}" y="{ty}" class="t-{btone}" font-size="14" font-weight="600">{escape(line)}</text>')
                ty += 19
            y = max(y + 40, ty) + (14 if j < len(spec["branch"]) - 1 else 4)

    # optional callout for one bounded step inside a not-a-fit task
    if spec.get("callout"):
        c = spec["callout"]
        lines = wrap(c["title"], 14, W - 2 * PAD - 60, True)
        h = 24 + 16 + 18 * len(lines)
        y += 20
        out.append(f'<rect x="{PAD}" y="{y}" width="{W - 2 * PAD}" height="{h}" rx="10" fill="none" '
                   f'class="s-accent" stroke-width="1.2" stroke-dasharray="5 4"/>')
        out.append(f'<circle cx="{PAD + 30}" cy="{y + h / 2:.0f}" r="18" class="f-accent-bg"/>')
        out.append(icon(c.get("icon", "flag"), PAD + 30, y + h / 2, 17, "s-accent"))
        ly = y + 22
        out.append(f'<text x="{PAD + 58}" y="{ly}" class="t-accent" font-size="11" font-weight="700" '
                   f'letter-spacing="1">{escape(c.get("label", "optional, if you build this out").upper())}</text>')
        for line in lines:
            ly += 18
            out.append(f'<text x="{PAD + 58}" y="{ly}" class="t-ink" font-size="14" font-weight="600">{escape(line)}</text>')
        y += h

    # tagline: emphasis in accent with underline, wrapping safely
    if spec.get("tagline"):
        t = spec["tagline"]
        y += 22
        out.append(f'<line x1="{PAD}" y1="{y}" x2="{W - PAD}" y2="{y}" class="s-line" stroke-width="1"/>')
        y += 8
        words = [(w, False) for w in t.get("before", "").split()] + \
                [(w, True) for w in t.get("emphasis", "").split()] + \
                [(w, False) for w in t.get("after", "").split()]
        lines, cur = [], []
        for w in words:
            trial = " ".join(x for x, _ in cur + [w])
            if cur and text_w(trial, 15, True) > W - 2 * PAD:
                lines.append(cur)
                cur = [w]
            else:
                cur.append(w)
        if cur:
            lines.append(cur)
        for ln in lines:
            y += 22
            # group consecutive words by emphasis so the underline runs unbroken
            groups = []
            for w, em in ln:
                if groups and groups[-1][1] == em:
                    groups[-1][0].append(w)
                else:
                    groups.append(([w], em))
            spans = []
            for k, (ws, em) in enumerate(groups):
                sp = " " if k else ""
                chunk = escape(" ".join(ws))
                if em:
                    spans.append(f'{sp}<tspan class="t-accent" text-decoration="underline">{chunk}</tspan>')
                else:
                    spans.append(f'{sp}{chunk}')
            out.append(f'<text x="{PAD}" y="{y}" class="t-ink" font-size="15" font-weight="600" '
                       f'xml:space="preserve">{"".join(spans)}</text>')

    H = y + PAD
    light = "".join(f".t-{k}{{fill:{v[0]}}}.f-{k}{{fill:{v[0]}}}.s-{k}{{stroke:{v[0]}}}" for k, v in PALETTE.items())
    dark = "".join(f".t-{k}{{fill:{v[1]}}}.f-{k}{{fill:{v[1]}}}.s-{k}{{stroke:{v[1]}}}" for k, v in PALETTE.items())
    line_light, line_dark = PALETTE["line"]
    title = escape(f"{label}: {spec['headline']}")
    desc = escape(spec.get("subtitle", ""))
    margin = 12  # room around the card for the drop shadow to render into
    fw, fh = W + margin * 2, H + margin * 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fw:.0f} {fh:.0f}" width="{fw:.0f}" '
            f'height="{fh:.0f}" role="img" font-family="{FONT}">'
            f'<title>{title}</title><desc>{desc}</desc>'
            f'<style>{light}@media (prefers-color-scheme: dark){{{dark}}}</style>'
            f'<defs><filter id="card-shadow" x="-20%" y="-20%" width="140%" height="140%">'
            f'<feDropShadow dx="0" dy="2" stdDeviation="6" flood-opacity="0.10"/>'
            f'</filter></defs>'
            f'<g transform="translate({margin},{margin})">'
            f'<rect width="{W}" height="{H:.0f}" rx="16" class="f-bg" filter="url(#card-shadow)" '
            f'stroke="{line_light}" stroke-width="1"/>'
            + "".join(out) + "</g></svg>")


def mm_label(text):
    """Make text safe inside a quoted Mermaid label."""
    return " ".join(str(text).split()).replace('"', "#quot;")


BADGE_CLASS = {
    "good": "fill:#f4e8cc,stroke:#c4521f,color:#c4521f,font-weight:bold",
    "partial": "fill:#faeeda,stroke:#b07d1f,color:#b07d1f,font-weight:bold",
    "not": "fill:#e9e6df,stroke:#5f5e5a,color:#5f5e5a,font-weight:bold",
}


def render_mermaid(spec):
    """Follows the hand-written Mermaid rules in SKILL.md section 5, so the two stay in sync."""
    label = VERDICTS[spec["verdict"]][0].upper()
    lines = ["flowchart TD", f'  v["{mm_label(label + " · " + spec["headline"])}"]:::badge']
    ids = []
    for i, st in enumerate(spec.get("steps", []), 1):
        parts = [mm_label(st["title"])]
        if st.get("detail"):
            parts.append(mm_label(st["detail"]))
        if st.get("pills"):
            parts.append(" · ".join(mm_label(p) for p in st["pills"]))
        tone = st.get("tone", "accent")
        tone = tone if tone in ("accent", "gray", "done", "hold") else "accent"
        lines.append(f'  s{i}["{"<br/>".join(parts)}"]:::{tone}')
        ids.append(f"s{i}")
    if ids:
        lines.append(f"  v --- {ids[0]}")
        if len(ids) > 1:
            lines.append("  " + " --> ".join(ids))
    for j, b in enumerate(spec.get("branch", []), 1):
        tone = b.get("tone", "done") if b.get("tone") in ("done", "hold") else "done"
        text = mm_label(f'{b.get("label", "")}: {b["title"]}' if b.get("label") else b["title"])
        lines.append(f'  b{j}(["{text}"]):::{tone}')
        if ids:
            lines.append(f"  {ids[-1]} --> b{j}")
    if spec.get("callout"):
        c = spec["callout"]
        lines.append(f'  c1["{mm_label(c.get("label", "optional").upper() + ": " + c["title"])}"]:::callout')
        if ids:
            lines.append(f"  {ids[-1]} -.- c1")
    lines += [
        f"  classDef badge {BADGE_CLASS[spec['verdict']]}",
        "  classDef accent fill:#f4e8cc,stroke:#c4521f,color:#1f1a14",
        "  classDef gray fill:#e9e6df,stroke:#5f5e5a,color:#1f1a14",
        "  classDef done fill:#eaf3de,stroke:#5e7d3c,color:#1f1a14",
        "  classDef hold fill:#faeeda,stroke:#b07d1f,color:#1f1a14",
        "  classDef callout fill:#faf6ee,stroke:#c4521f,stroke-dasharray:5 4,color:#1f1a14",
    ]
    return "\n".join(lines) + "\n"


def render_markdown(spec):
    label = VERDICTS[spec["verdict"]][0].upper()
    md = [f"**{label}** · {spec['headline']}", ""]
    if spec.get("subtitle"):
        md += [f"_{spec['subtitle']}_", ""]
    for i, st in enumerate(spec.get("steps", []), 1):
        tag = " _(not jev)_" if st.get("tone") == "gray" else ""
        line = f"{i}. **{st['title']}**{tag}"
        if st.get("detail"):
            line += f": {st['detail']}"
        if st.get("pills"):
            line += " (" + ", ".join(f"`{p}`" for p in st["pills"]) + ")"
        md.append(line)
    for b in spec.get("branch", []):
        md.append(f"    - {b.get('label', '')}: **{b['title']}**")
    if spec.get("callout"):
        c = spec["callout"]
        md += ["", f"> **{c.get('label', 'optional, if you build this out')}:** {c['title']}"]
    if spec.get("tagline"):
        t = spec["tagline"]
        md += ["", f"{t.get('before', '')} **{t.get('emphasis', '')}** {t.get('after', '')}".strip()]
    return "\n".join(md) + "\n"


EXAMPLES = {
    "good": {
        "verdict": "good", "headline": "ticket → jev → route",
        "subtitle": "a fixed list of teams is what makes this a jev fit",
        "steps": [
            {"icon": "mail", "title": "ticket arrives", "detail": "subject, body, customer tier"},
            {"icon": "list-details", "title": "known categories",
             "pills": ["billing", "bug", "feature", "account", "none fits"]},
            {"icon": "scale", "title": "jev picks one", "detail": "a choice question over that list"},
            {"icon": "gauge", "title": "confidence check", "detail": "your threshold, your code"},
        ],
        "branch": [
            {"icon": "send", "label": "high confidence", "title": "auto-route", "tone": "done"},
            {"icon": "user-exclamation", "label": "low confidence", "title": "human triage", "tone": "hold"},
        ],
        "tagline": {"before": "bounded list plus a judgment call:", "emphasis": "jev's lane"},
    },
    "partial": {
        "verdict": "partial", "headline": "draft → quality score",
        "subtitle": "a score question works once someone writes the rubric down",
        "steps": [
            {"icon": "file-text", "title": "draft arrives", "detail": "title, body, target audience"},
            {"icon": "list-check", "title": "rubric", "tone": "hold",
             "detail": "missing today: what separates a 2 from a 4", "detail_tone": "hold"},
            {"icon": "scale", "title": "jev scores it", "detail": "only after the rubric exists"},
        ],
        "tagline": {"before": "write the rubric first,", "emphasis": "then it fits"},
    },
    "not": {
        "verdict": "not", "headline": "contract → risk memo",
        "subtitle": "every step needs free text or open-ended reasoning, which is a generative model's job",
        "steps": [
            {"icon": "file-text", "title": "extract clauses", "detail": "open-ended reading", "tone": "gray"},
            {"icon": "search", "title": "cross-reference regulations", "detail": "retrieval and synthesis", "tone": "gray"},
            {"icon": "message-2", "title": "explain the reasoning", "detail": "free text", "tone": "gray"},
        ],
        "callout": {"icon": "flag", "title": "needs senior review? a yes/no jev could gate"},
        "tagline": {"before": "the model writes the memo;", "emphasis": "jev can only gate the escalation"},
    },
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="path to a verdict spec JSON")
    ap.add_argument("--example", choices=sorted(EXAMPLES), help="render a built-in example")
    ap.add_argument("--out", default="verdict", help="output path without extension")
    ap.add_argument("--formats", default="svg,mmd,md", help="comma list of svg, mmd, md")
    args = ap.parse_args()
    if args.example:
        spec = EXAMPLES[args.example]
        print(json.dumps(spec, indent=2, ensure_ascii=False))
    elif args.spec:
        spec = json.loads(Path(args.spec).read_text())
    else:
        ap.print_help()
        return 2
    if spec.get("verdict") not in VERDICTS:
        print("spec.verdict must be one of: good, partial, not", file=sys.stderr)
        return 1
    renderers = {"svg": render_svg, "mmd": render_mermaid, "md": render_markdown}
    for fmt in args.formats.split(","):
        path = Path(f"{args.out}.{fmt}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(renderers[fmt](spec), encoding="utf-8")
        print(f"wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
