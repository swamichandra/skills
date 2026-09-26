# Jev API: the contract, and how to write requests that work

Transcribed from TypeSafe's HTTP API reference (docs.typesafe.ai/api), checked September 2026. Jev is in early access and moving quickly. Before shipping anything, re-check the live reference and the models page; if they disagree with this file, they win.

Machine-readable versions of everything below:
- `assets/jev-request.schema.json`: request body, JSON Schema draft 2020-12
- `assets/jev-response.schema.json`: response body
- `assets/examples/*.json`: complete, valid requests to copy from
- `scripts/validate_request.py`: checks a drafted request (no dependencies)

## Endpoint and access

```
POST https://api.typesafe.ai/v1/systemone
Authorization: Bearer $TYPESAFE_API_KEY
Content-Type: application/json
```

Direct access is waitlisted. The same request shape is also served through gateways, each with its own model id and key: OpenRouter (beta, `typesafe/jev-1.13`, System One endpoint), Vercel AI Gateway (`typesafe-ai/jev`, through the AI SDK's experimental `evaluate`), and others. Confirm the current id on the gateway's own model page before use.

## Using Jev from an agent through MCP

For Claude Code, Claude Desktop, and Codex, the community `evaluate` MCP server (github.com/itsmostafa/typesafe-mcp) exposes Jev as a tool. It is a single Go binary, not an npm package. Its tool takes the same `state` and `questions` as the HTTP API, with the server supplying the model and key, and it can also batch up to 500 records per call. `assets/examples/mcp-evaluate-call.json` shows one call and its result.

Setup, from the project README. It is a community project, and the installer is a remote shell script, so read `install.sh` before running it (see `trust/guardrails.md`):
```
curl -fsSL https://raw.githubusercontent.com/itsmostafa/typesafe-mcp/main/install.sh | sh
evaluate setup mcp      # reads TYPESAFE_API_KEY or OPENROUTER_API_KEY from the environment
codex mcp list
claude mcp list
```
`evaluate setup mcp` registers the server with every supported client it finds. If a client is missed, show the manual registration command for that client before running it.

## Request body

Three required fields, nothing else.

| Field | Type | Notes |
|---|---|---|
| `state` | string, object, or array | What is being judged. Send only what the questions need; accuracy drops as unrelated content piles up. |
| `model` | string | `jev-latest` is an alias that can move without notice. Pin a version (for example `jev-1.13.0`) in production and log the `model` returned in each response. |
| `questions` | map of id → question | One request can carry several questions. Each is answered independently against the same state. |

The question id is yours and is **never sent to the model**. Every question's `instructions` must make sense on its own. Point at a state field in backticks, including nested paths and array indices, for example "Which team should handle `body`?" or "Does `ticket.messages[0].text` request a refund?"

### The three question types

All three share `type` and `instructions` (string, object, or array). They differ in `criteria`.

**Noul**: yes/no, answered as a probability of yes.
```json
{ "type": "noul",
  "instructions": "Does `message` describe a software defect?",
  "criteria": { "true": "Broken or unexpected product behavior", "false": "A question or a feature request" } }
```
`criteria` is optional but worth writing: it pins down what yes and no mean.

**Choice**: pick one option from a set you define.
```json
{ "type": "choice",
  "instructions": "Which team should handle `body`?",
  "criteria": {
    "billing": "Charges, invoices, refunds",
    "account_access": "Login, passwords, SSO",
    "none_fits": "None of the teams above clearly fits" } }
```
`criteria` maps option id → description (or `null`). 2 to 255 options. Jev always returns one of the listed options, so if "none of these" is a real outcome, it has to be an option.

**Score**: place the state on an ordered rubric.
```json
{ "type": "score",
  "instructions": "How time-sensitive is this ticket?",
  "criteria": ["Can wait", "This week", "Today"] }
```
`criteria` is an ordered array, lowest first, 2 to 10 levels.

## Writing questions that work

This is the part that actually determines whether a Jev integration is any good. The request shape is easy; a well-posed question is not.

**Ask for one snap judgment, not an analysis.** "Does this message convey urgency?" is a good question. "Analyze this ticket and determine the best course of action" is not; that is exactly the multi-step reasoning Jev cannot do. If what's needed sounds like an analysis, it is several snap judgments wearing a trenchcoat. Split it.

**Split a judgment that depends on several factors, and combine the answers in code.** Don't ask "rate this startup pitch." Ask about market size, technical feasibility, and differentiation as separate questions, then weight them in code (TypeSafe calls this composite scoring). When priorities change, edit a weight, not a prompt.

**Ask everything that might matter in one request, including questions some inputs won't need.** Every question in a request runs in parallel against the same state, so extra questions cost a little state token and are close to free. TypeSafe's own benchmark found batching 13 questions into one call ran about 11.5x cheaper and 9.6x faster than 13 separate calls. Ask up front, and let the caller's code ignore the answers a given input doesn't use.

**Make a second, dependent request only when the code genuinely cannot build it yet.** Questions in one request are independent; no answer becomes context for another question in the same call. That's fine for almost everything. Reach for a second request only when the first answer decides what to fetch next, what the second state should contain, or which options the second question even offers, not as a default way to chain judgments.

**Picking Choice, Score, or Noul:** prefer whichever answer the caller's code acts on directly. A Choice between named outcomes maps onto separate code paths. A Score maps onto a threshold along a spectrum. A Noul maps onto an `if`. The one real trap: a Noul answer of 0.5 means "even odds of yes or no," not "medium." "Is this candidate strong in Python?" is a bad Noul question because "strong" isn't a yes/no condition; either sharpen it into a real yes/no ("does the resume state professional Python experience?") or make it a Score with defined levels ("no experience" through "deep expertise").

## Response body

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "is_bug":  { "type": "noul", "noul": 0.93 },
    "team":    { "type": "choice", "choice": "account_access",
                 "probabilities": { "billing": 0.04, "account_access": 0.91, "none_fits": 0.05 },
                 "confidence": 0.86 },
    "urgency": { "type": "score", "score": 1.8,
                 "legend": { "0": "Can wait", "1": "This week", "2": "Today" },
                 "probabilities": { "0": 0.02, "1": 0.16, "2": 0.82 },
                 "confidence": 0.77 }
  },
  "usage": { "input_tokens": 318, "output_tokens": 34 }
}
```

How to read each answer:
- **Noul** returns only `noul`. There is no `confidence` field. Threshold the value itself: high means yes, low means no, and the middle band goes to review.
- **Choice** returns the top option, the full distribution, and `confidence`. Gate on `confidence`, not on the top option's probability alone.
- **Score** returns `score` as a probability-weighted level index that can land between levels (1.8 above is "leaning Today"), plus `legend`, the distribution, and `confidence`.

`scripts/confidence_gate.py` implements exactly these three rules.

## Errors

| Status | Meaning | What the caller does |
|---|---|---|
| 401 | Missing or bad key | Stop. Never retry with a guessed key. |
| 422 | Body failed validation | Stop. Fix the request; `validate_request.py` catches most causes before sending. |
| 429 | Rate limited | Retry with exponential backoff; honor `Retry-After` when present. |
| 529 | TypeSafe overloaded | Same as 429. |

On any failure, the decision falls back to the caller's safe default (usually: send to review). A decision point must never fail open because Jev was unreachable.

## What Jev will not do

Typed output means no out-of-schema values. It does not mean correct. A well-formed answer can still be confidently wrong, so schema errors and wrong decisions are separate problems.

Jev writes no text, code, summaries, or explanations of its reasoning. It is also a poor fit for arithmetic, counting, and date reasoning: compute those in code and put the result in the state.

## Published figures: treat as vendor claims

- Pricing: $0.042 per million input tokens, output unmetered (TypeSafe; matches the OpenRouter listing at time of checking).
- Context: 32K tokens (OpenRouter listing).
- Speed and cost versus LLMs: TypeSafe reports up to 193.6x faster and 444.6x cheaper on its own workflow evaluations. That is a ceiling from the vendor's own tests, not an expected result.

Run Jev in shadow mode beside the current path, label outcomes, and size decisions on your own measurements.
