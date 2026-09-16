#!/usr/bin/env python3
"""learn_from_review.py — add a lesson after reviewing a generated app.

Usage:
  python app/learn_from_review.py page "Comp dashboards use one measure MATRIX Custom" "Gold 1af96141…"
  python app/learn_from_review.py query "D1 collapse order_stage before SUM" "3.4x fan-out"

Scopes: query | page | architect | frd | all
See knowledge/training_loop.md.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import knowledge_base as kb

def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    scope, rule, why = sys.argv[1], sys.argv[2], sys.argv[3]
    out = kb.add_lesson(scope, rule, why, source="iteration")
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
