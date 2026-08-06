#!/usr/bin/env python3
"""
feedback_store.py — the learning loop (user point 5), realized as a feedback store + few-shot recall
(decision D1: no live weight-training; improve by reusing accepted examples and surfacing recurring fixes).

Every accepted/corrected artifact is appended as one JSONL record. The engines pull the top accepted
examples of the relevant kind and inject them as few-shot context, so good outputs get reinforced and
past corrections stop recurring. `promote_candidates()` surfaces frequent correction signatures to graduate
into the prompt guardrails.

Record kinds: "query" (xSQL), "page" (control list / page design), "frd" (FRD revision), "app".
Store: ~/Downloads/extend-llm/feedback/feedback.jsonl (override with EXTEND_FEEDBACK_PATH).
Stdlib only — fully testable, no API key.

CLI:
    python feedback_store.py stats
    python feedback_store.py promote
"""
import os, json, time, hashlib

STORE = os.path.expanduser(os.environ.get(
    "EXTEND_FEEDBACK_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "feedback", "feedback.jsonl")))


def _ensure():
    os.makedirs(os.path.dirname(STORE), exist_ok=True)


def record(kind: str, request: str, output: str, accepted: bool,
           verdict: str | None = None, comment: str = "", meta: dict | None = None) -> dict:
    """Append one feedback record. `accepted`=True for approvals, False for corrections/rejections."""
    _ensure()
    rec = {"ts": time.time(), "kind": kind, "request": request, "output": output,
           "accepted": bool(accepted), "verdict": verdict, "comment": comment, "meta": meta or {}}
    with open(STORE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def iter_records(kind: str | None = None, accepted: bool | None = None):
    if not os.path.exists(STORE):
        return
    with open(STORE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if kind is not None and r.get("kind") != kind:
                continue
            if accepted is not None and r.get("accepted") is not accepted:
                continue
            yield r


def few_shot(kind: str, k: int = 3, max_chars: int = 4000) -> str:
    """Top-k most-recent ACCEPTED examples of a kind, formatted for prompt injection. '' if none."""
    accepted = list(iter_records(kind=kind, accepted=True))[-k:]
    if not accepted:
        return ""
    blocks = ["PRIOR ACCEPTED EXAMPLES (match this style; do not repeat past mistakes):"]
    for r in reversed(accepted):
        blocks.append(f"--- request:\n{r['request'].strip()}\n--- accepted output:\n{r['output'].strip()}")
    text = "\n".join(blocks)
    return text[:max_chars]


def stats() -> dict:
    by_kind: dict = {}
    for r in iter_records():
        k = r.get("kind", "?")
        d = by_kind.setdefault(k, {"total": 0, "accepted": 0, "corrected": 0})
        d["total"] += 1
        d["accepted" if r.get("accepted") else "corrected"] += 1
    return {"store": STORE, "by_kind": by_kind, "total": sum(d["total"] for d in by_kind.values())}


def promote_candidates(min_count: int = 2) -> list[dict]:
    """Recurring correction comments/verdicts → candidates to graduate into the prompt guardrails."""
    counts: dict = {}
    for r in iter_records(accepted=False):
        sig = (r.get("comment") or r.get("verdict") or "").strip().lower()
        if not sig:
            continue
        key = hashlib.md5(sig.encode()).hexdigest()[:8]
        c = counts.setdefault(key, {"signature": sig[:200], "count": 0, "kinds": set()})
        c["count"] += 1
        c["kinds"].add(r.get("kind"))
    out = [{"signature": v["signature"], "count": v["count"], "kinds": sorted(k for k in v["kinds"] if k)}
           for v in counts.values() if v["count"] >= min_count]
    return sorted(out, key=lambda x: -x["count"])


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "promote":
        print(json.dumps(promote_candidates(), indent=2))
    else:
        print(json.dumps(stats(), indent=2))
