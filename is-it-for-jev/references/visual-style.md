# Verdict visual

Every verdict comes with a visual card. It must show up on any host: Claude, Copilot, Gemini, an IDE, or a plain terminal. So the card is produced as **files from one spec**, not through any host's built-in drawing tool.

## Delivery: pick the first tier the host supports

1. **Host can run Python** (Claude Code, Codex, Copilot agent modes, Cowork, Gemini with code execution, most agent harnesses). Write the spec to a JSON file and run:
   ```
   python scripts/render_verdict.py spec.json --out verdict
   ```
   This writes `verdict.svg`, `verdict.mmd`, and `verdict.md`. Hand the SVG to the user the way the host shares files (attach it, save it to the workspace, or embed it in Markdown as `![verdict](verdict.svg)`).
2. **No code execution, but Markdown renders Mermaid** (GitHub, GitLab, many IDE chat panels). Write the Mermaid by hand, following the rules and template in SKILL.md section 5 exactly. The two mistakes that break most hand-written diagrams are spaces around `:::` and unquoted labels.
3. **Anything else.** Use the Markdown text card: verdict line, numbered steps, branch, tagline. It renders everywhere, including plain chat.

A host that has its own inline visual tool may use it instead, following the look below. The files are still the portable version and should be offered when the user will share the verdict.

Never skip the visual silently. If no tier above works, give the text card.

## The spec

```json
{
  "verdict": "good | partial | not",
  "headline": "ticket → jev → route",
  "subtitle": "one line: the reason for the verdict",
  "steps": [
    { "icon": "mail", "title": "ticket arrives", "detail": "subject, body, tier" },
    { "icon": "list-details", "title": "known categories",
      "pills": ["billing", "bug", "none fits"] },
    { "icon": "file-text", "title": "extract clauses", "detail": "free text",
      "tone": "gray" },
    { "icon": "list-check", "title": "rubric", "detail": "missing today",
      "detail_tone": "hold" }
  ],
  "branch": [
    { "icon": "send", "label": "high confidence", "title": "auto-route", "tone": "done" },
    { "icon": "user-exclamation", "label": "low confidence", "title": "human triage", "tone": "hold" }
  ],
  "callout": { "icon": "flag", "title": "needs senior review? a yes/no jev could gate" },
  "tagline": { "before": "bounded list plus a judgment call:", "emphasis": "jev's lane", "after": "" }
}
```

Only `verdict`, `headline`, and `steps` are required. `icon` names come from `assets/icons.json` (a curated Tabler set; unknown names fall back to a question mark). `python scripts/render_verdict.py --example good` prints a complete spec for each verdict.

## What goes in the card

- **Three to five steps**, top to bottom. No horizontal flows.
- **Show the bounded thing.** For a good fit, one step must display the actual option list as pills, the rubric levels, or the yes/no proposition. That is the evidence for the verdict; an abstract "jev decides" step is not.
- **Branch** only when the flow forks on a confidence gate: two outcomes at most, `done` for the automatic path and `hold` for review.
- **Callout** only for a not-a-fit verdict that contains one genuinely bounded sub-step. Keep it out of the main flow so it reads as an aside, not as evidence the whole task fits.
- **Tagline**: one sentence, with the key phrase in `emphasis`.

## Tones

| Tone | Meaning | Use |
|---|---|---|
| `accent` | Jev's lane | Steps in a good fit; the callout |
| `gray` | a generative model's or code's job | Steps that fail the HELLO Test in a not-a-fit or partial-fit card |
| `done` | proceeds automatically | The high-confidence branch |
| `hold` | pauses for a person | The review branch; the missing piece in a partial fit |
| `problem` | something is broken | Only for a real failure, such as a vetoed action or a failed verification. Never for a not-a-fit verdict: a correct "no" is not a failure. |

Verdict badges are fixed by the renderer: good uses accent, partial uses hold, not a fit uses gray.

## Palette (from dadloop's `theme.py`, light / dark)

| Token | Light | Dark |
|---|---|---|
| ink | `#1f1a14` | `#e9e3d6` |
| mute | `#6b6157` | `#9a9184` |
| background | `#faf6ee` | `#100e0a` |
| hairline | `#d9cdb9` | `#34302a` |
| accent / bg | `#c4521f` / `#f4e8cc` | `#d97757` / `#2a2114` |
| done / bg | `#5e7d3c` / `#eaf3de` | `#8ba86a` / `#1b1915` |
| hold / bg | `#b07d1f` / `#faeeda` | `#c9a24c` / `#211d18` |
| gray / bg | `#5f5e5a` / `#e9e6df` | `#9a9184` / `#201d18` |
| problem | `#b23a2b` | `#c96f5a` |

The SVG switches between light and dark on its own through `prefers-color-scheme`.
