#!/usr/bin/env python3
"""
Validate a drafted Jev request body before it is shown or sent.

Checks the body against assets/jev-request.schema.json. Uses the `jsonschema`
package when it is installed and falls back to built-in checks when it is not,
so it runs on any host with plain Python 3.8+.

Also prints design warnings that the schema cannot express:
  - model is an alias ("jev-latest") rather than a pinned version
  - a Choice has no option for "none of these fit"
  - a Choice whose options are dispositions or actions (approve, block,
    fraud, legitimate, ...), which means Jev is being asked for the decision
    instead of the evidence
  - state keys that look like personal data or identifiers the judgment
    rarely needs (names, street addresses, card digits, ids)

Usage:
    python validate_request.py request.json
    cat request.json | python validate_request.py -

Exit code 0 means valid (warnings allowed), 1 means invalid.
"""

import json
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "assets" / "jev-request.schema.json"
ENTRY_TYPES = (str, dict, list)
ABSTAIN_HINTS = ("none", "other", "unknown", "no_match", "abstain", "unclear")
VERDICT_WORDS = {"approve", "approved", "reject", "rejected", "deny", "denied", "block", "blocked",
                 "allow", "allowed", "hold", "escalate", "review", "manual_review", "flag",
                 "fraud", "fraudulent", "legitimate", "suspicious", "safe", "unsafe",
                 "accept", "decline", "merge", "auto_merge", "pass", "fail"}
PII_KEYS = ("name", "street", "address", "email", "phone", "card_last_four", "card_number",
            "ssn", "dob", "date_of_birth", "customer_id", "order_id", "device_id", "account_id",
            "user_id", "ip_address", "postal_code", "zip")


def builtin_errors(body):
    errs = []
    if not isinstance(body, dict):
        return ["body must be a JSON object"]
    for key in ("state", "model", "questions"):
        if key not in body:
            errs.append(f"missing required field '{key}'")
    extra = set(body) - {"state", "model", "questions"}
    if extra:
        errs.append(f"unexpected top-level fields: {sorted(extra)}")
    if "state" in body and not isinstance(body["state"], ENTRY_TYPES):
        errs.append("state must be a string, object, or array")
    if "model" in body and (not isinstance(body["model"], str) or not body["model"]):
        errs.append("model must be a non-empty string")
    qs = body.get("questions")
    if qs is None:
        return errs
    if not isinstance(qs, dict) or not qs:
        errs.append("questions must be a non-empty object")
        return errs
    for qid, q in qs.items():
        where = f"questions.{qid}"
        if not isinstance(q, dict):
            errs.append(f"{where} must be an object")
            continue
        qtype = q.get("type")
        if qtype not in ("noul", "choice", "score"):
            errs.append(f"{where}.type must be noul, choice, or score")
            continue
        if not isinstance(q.get("instructions"), ENTRY_TYPES):
            errs.append(f"{where}.instructions is required (string, object, or array)")
        allowed = {"type", "instructions", "criteria"}
        if set(q) - allowed:
            errs.append(f"{where} has unexpected fields: {sorted(set(q) - allowed)}")
        crit = q.get("criteria")
        if qtype == "noul" and crit is not None:
            if not isinstance(crit, dict) or set(crit) - {"true", "false"}:
                errs.append(f"{where}.criteria may only have 'true' and 'false'")
        if qtype == "choice":
            if not isinstance(crit, dict):
                errs.append(f"{where}.criteria must map option ids to descriptions")
            elif not 2 <= len(crit) <= 255:
                errs.append(f"{where}.criteria needs 2 to 255 options, has {len(crit)}")
        if qtype == "score":
            if not isinstance(crit, list):
                errs.append(f"{where}.criteria must be an ordered array of levels")
            elif not 2 <= len(crit) <= 10:
                errs.append(f"{where}.criteria needs 2 to 10 levels, has {len(crit)}")
    return errs


def schema_errors(body):
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return None
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'.'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
        for e in validator.iter_errors(body)
    ]


def warnings(body):
    out = []
    if not isinstance(body, dict):
        return out
    if body.get("model") == "jev-latest":
        out.append("model is the 'jev-latest' alias, which can move without notice; pin a version for production")
    for qid, q in (body.get("questions") or {}).items():
        if isinstance(q, dict) and q.get("type") == "choice" and isinstance(q.get("criteria"), dict):
            opts = [k.lower() for k in q["criteria"]]
            verdicts = [k for k in opts if k in VERDICT_WORDS]
            if len(verdicts) >= 2:
                out.append(f"questions.{qid}: options {verdicts} read as a verdict; ask about the evidence "
                           "(separate questions) and decide the disposition in code")
            elif not any(h in k for k in opts for h in ABSTAIN_HINTS):
                out.append(f"questions.{qid}: no 'none fits' option; Jev always returns one of the listed options")
    hits = sorted({k for k, parent in _keys(body.get("state"))
                   if (k.lower() in PII_KEYS or k.lower().endswith("_id"))
                   and not (k.lower() == "name" and parent in THING_LISTS)})
    if hits:
        out.append(f"state has keys that look like personal data or ids {hits}; drop them unless a question "
                   "actually needs them")
    return out


THING_LISTS = {"items", "products", "line_items", "tools", "options", "skills", "files"}


def _keys(node, parent=None):
    """Every (key, parent key) pair anywhere in the state. A `name` inside a list of
    things (items, tools, files) names the thing, not a person, so callers can skip it."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield k, parent
            yield from _keys(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from _keys(v, parent)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    raw = sys.stdin.read() if sys.argv[1] == "-" else Path(sys.argv[1]).read_text()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"INVALID: not JSON ({e})")
        return 1
    # Built-in checks give field-specific messages; jsonschema, when installed,
    # is the backstop for anything they miss.
    errs, mode = builtin_errors(body), "built-in checks"
    js = schema_errors(body)
    if js is not None:
        mode = "built-in checks + jsonschema"
        if not errs:
            errs = js
    for w in warnings(body):
        print(f"WARN: {w}")
    if errs:
        for e in errs:
            print(f"ERROR: {e}")
        print(f"INVALID ({mode})")
        return 1
    print(f"VALID ({mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
