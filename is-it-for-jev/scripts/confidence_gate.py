#!/usr/bin/env python3
"""
Template for the caller-owned decision rule that sits between a Jev answer
and any action. Jev returns judgments; this code owns thresholds and
consequences. Copy the gate functions into an integration; this is not a library.

Works on the real response shape from POST /v1/systemone:
  - noul answers carry only `noul` (0 to 1). There is no confidence field,
    so the gate thresholds the noul value itself, with a middle band for review.
  - choice and score answers carry `confidence`; the gate acts on the answer
    only above a threshold and sends everything else to review.

Usage:
    python confidence_gate.py --demo
    python confidence_gate.py response.json --high 0.85 --low 0.15

Thresholds are placeholders. Set them from labeled outcomes in shadow mode,
not from these defaults.
"""

import argparse
import json
from pathlib import Path


def gate_noul(p, yes_at, no_at):
    """Return 'yes', 'no', or 'review' for a noul probability."""
    if p >= yes_at:
        return "yes"
    if p <= no_at:
        return "no"
    return "review"


def gate_confident(answer, act_at):
    """Return ('act', value) or ('review', value) for a choice or score answer."""
    value = answer["choice"] if answer["type"] == "choice" else answer["score"]
    return ("act" if answer["confidence"] >= act_at else "review", value)


def gate_response(response, high, low):
    decisions = {}
    for qid, ans in response["answers"].items():
        if ans["type"] == "noul":
            decisions[qid] = {"type": "noul", "noul": ans["noul"],
                              "outcome": gate_noul(ans["noul"], high, low)}
        elif ans["type"] in ("choice", "score"):
            outcome, value = gate_confident(ans, high)
            decisions[qid] = {"type": ans["type"], "value": value,
                              "confidence": ans["confidence"], "outcome": outcome}
        else:
            decisions[qid] = {"type": ans.get("type"), "outcome": "review",
                              "note": "unknown answer type; never act on it"}
    return {"model": response.get("model"), "decisions": decisions}


DEMO_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "is_fraud": {"type": "noul", "noul": 0.42},
        "department": {"type": "choice", "choice": "billing",
                       "probabilities": {"billing": 0.88, "technical": 0.12, "none_fits": 0.0},
                       "confidence": 0.81},
        "urgency": {"type": "score", "score": 1.05,
                    "legend": {"0": "Can wait", "1": "This week", "2": "Today"},
                    "probabilities": {"0": 0.0, "1": 0.95, "2": 0.05},
                    "confidence": 0.92},
    },
    "usage": {"input_tokens": 318, "output_tokens": 34},
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("response", nargs="?", help="path to a saved /v1/systemone response")
    ap.add_argument("--demo", action="store_true", help="run on a built-in example response")
    ap.add_argument("--high", type=float, default=0.85,
                    help="act threshold for choice/score confidence, and the 'yes' cutoff for noul")
    ap.add_argument("--low", type=float, default=0.15, help="the 'no' cutoff for noul")
    args = ap.parse_args()
    if args.demo:
        response = DEMO_RESPONSE
    elif args.response:
        response = json.loads(Path(args.response).read_text())
    else:
        ap.print_help()
        return
    print(json.dumps(gate_response(response, args.high, args.low), indent=2))


if __name__ == "__main__":
    main()
