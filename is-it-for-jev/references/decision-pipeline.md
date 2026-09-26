# Decision pipeline: a worked example

## The split

```
TASK
 ├─ deterministic facts: deadline, budget left, which models are up, context length
 │     → code
 └─ semantic properties: ambiguity, reasoning depth needed, domain risk
       → Jev
             ↓
 deterministic policy combines both
             ↓
 model or action chosen
```

## Model routing, end to end

**Goal and possible actions.** Route an incoming task to one of: a fast cheap model, a frontier model, or a human.

**Decision-relevant distinctions.**
- Exact, so code: deadline slack, budget remaining, which models are currently available.
- Semantic, so Jev: how ambiguous the task is, how much reasoning it needs, whether the domain carries elevated risk.

**Representation.** Only what the question needs:
`{ task_summary, domain_tag, prior_error_rate_this_domain }`. Budget and deadline stay out of the state; code applies them afterward.

**Judgment.** One request, two questions:

```json
{
  "state": {
    "task_summary": "Reconcile Q3 lease abstractions against the amended master agreement",
    "domain_tag": "legal",
    "prior_error_rate_this_domain": 0.07
  },
  "model": "jev-1.13.0",
  "questions": {
    "depth": {
      "type": "score",
      "instructions": "How much multi-step reasoning does `task_summary` need to complete correctly?",
      "criteria": ["Lookup or reformatting", "A few connected steps", "Long chains with cross-checking"]
    },
    "needs_human": {
      "type": "noul",
      "instructions": "Would an error on `task_summary` in `domain_tag` be costly enough that a person should own the result?",
      "criteria": { "true": "Material legal, financial, or safety exposure", "false": "Errors are cheap to catch and fix" }
    }
  }
}
```

**Decision rule, in code.**
```python
a = response["answers"]
if a["needs_human"]["noul"] >= 0.7:
    route = "human"
elif a["depth"]["confidence"] < 0.6:
    route = "frontier_model"          # unsure how hard it is: take the safe default
elif a["depth"]["score"] >= 1.5 and budget_ok and frontier_up:
    route = "frontier_model"
else:
    route = "fast_model"
log(request, response, route)
```

**Outcome.** Compare the route against what happened (did the fast model need a retry, did the human change the answer). When outcomes disagree with the routing, find out why before changing thresholds: a variable missing from the state, a distinction that was really exact rather than semantic, a miscalibrated answer, or a threshold in the wrong place. Never keep routing the same way when outcomes say otherwise.

## Fraud screening: evidence in, disposition out

The tempting request asks Jev for the disposition directly ("legitimate, suspicious, or fraud?") and then asks for a fraud-risk Score on top. It validates, and it returns a plausible answer. It is still the wrong design: the options are the decision, the Score measures the same thing twice, and when an order is held nobody can say why.

The better shape splits the judgment into the separate facts a reviewer would weigh. `assets/examples/checkout-risk.composite.json` is the full request, built from a real test order: 16.7 times the customer's usual spend, a new address changed during checkout, eight candy boxes and four costumes in late September. It asks three Noul questions: does the basket look like resale, is there an ordinary occasion for it (Halloween is the obvious one here, which is exactly the kind of context a rule can't see), and does the session look like someone other than the account holder.

Code does the rest, in order:

```python
# 1. Exact checks first. These never go to Jev.
if not payment["cvv_match"] or payment["payment_attempts"] > 3 or on_blocklist(order):
    return hold("hard rule", request_id=None)

# 2. One Jev call, three independent answers.
resp = jev(request)                     # on any error: return hold("jev unavailable")
a = resp["answers"]
risk = (0.45 * a["not_account_owner"]["noul"]
      + 0.35 * a["resale_pattern"]["noul"]
      + 0.20 * (1 - a["plausible_occasion"]["noul"]))

# 3. Disposition, owned by code. Weights and cutoffs are starting values.
if risk < 0.30:
    outcome = "approve"
elif risk < 0.60 and not payment["three_d_secure"]:
    outcome = "step_up"                 # ask for 3-D Secure before approving
else:
    outcome = "manual_review"

log(resp["request_id"], resp["model"], a, risk, outcome)   # the "why" behind every hold
```

When fraud losses rise, raise a weight or lower a cutoff. Nothing in the request changes. When a reviewer asks why an order was held, the log names the fact that drove it.

## HELLO Test, applied

Before finalizing any integration, confirm the Jev step never asks for:
- drafted or rewritten text
- generated code
- a value that is not in the caller's option list
- arithmetic, counting, or date math (compute these in code, pass the result in state)
- anything beyond noul, choice, or score answers

If it needs any of those, the step belongs to a generative model or to code, not Jev.
