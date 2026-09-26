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

## HELLO Test, applied

Before finalizing any integration, confirm the Jev step never asks for:
- drafted or rewritten text
- generated code
- a value that is not in the caller's option list
- arithmetic, counting, or date math (compute these in code, pass the result in state)
- anything beyond noul, choice, or score answers

If it needs any of those, the step belongs to a generative model or to code, not Jev.
