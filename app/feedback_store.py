#!/usr/bin/env python3
"""
feedback_store.py — the learning loop (user point 5), stored in the shared SQLite DB (db.py).

Accepted input->output EXAMPLES (few-shot) and corrections, persisted so the whole team's feedback
compounds. Complements knowledge_base's distilled RULES. Kinds: "query", "page", "frd", "app".
CLI:  python feedback_store.py stats   |   python feedback_store.py promote
"""
import os, sys, json, time, hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db


def record(kind: str, request: str, output: str, accepted: bool,
           verdict: str | None = None, comment: str = "", meta: dict | None = None) -> dict:
    """Append one feedback record. accepted=True for approvals, False for corrections/rejections."""
    rec = {"ts": time.time(), "kind": kind, "request": request, "output": output,
           "accepted": bool(accepted), "verdict": verdict, "comment": comment, "meta": meta or {}}
    c = db.connect()
    try:
        c.execute("INSERT INTO feedback(ts,kind,request,output,accepted,verdict,comment,meta) VALUES(?,?,?,?,?,?,?,?)",
                  (rec["ts"], kind, request, output, 1 if accepted else 0, verdict, comment, json.dumps(rec["meta"])))
        c.commit()
    finally:
        c.close()
    return rec


def iter_records(kind: str | None = None, accepted: bool | None = None):
    q = "SELECT ts,kind,request,output,accepted,verdict,comment,meta FROM feedback"
    conds, args = [], []
    if kind is not None:
        conds.append("kind=?"); args.append(kind)
    if accepted is not None:
        conds.append("accepted=?"); args.append(1 if accepted else 0)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY id"
    c = db.connect()
    try:
        for r in c.execute(q, args):
            d = dict(r); d["accepted"] = bool(d["accepted"])
            try:
                d["meta"] = json.loads(d["meta"] or "{}")
            except Exception:
                d["meta"] = {}
            yield d
    finally:
        c.close()


def few_shot(kind: str, k: int = 3, max_chars: int = 4000) -> str:
    """Top-k most-recent ACCEPTED examples of a kind, formatted for prompt injection. '' if none."""
    accepted = list(iter_records(kind=kind, accepted=True))[-k:]
    if not accepted:
        return ""
    blocks = ["PRIOR ACCEPTED EXAMPLES (match this style; do not repeat past mistakes):"]
    for r in reversed(accepted):
        blocks.append(f"--- request:\n{r['request'].strip()}\n--- accepted output:\n{r['output'].strip()}")
    return "\n".join(blocks)[:max_chars]


def stats() -> dict:
    by_kind: dict = {}
    for r in iter_records():
        d = by_kind.setdefault(r["kind"], {"total": 0, "accepted": 0, "corrected": 0})
        d["total"] += 1
        d["accepted" if r["accepted"] else "corrected"] += 1
    return {"db": db.DB_PATH, "by_kind": by_kind, "total": sum(d["total"] for d in by_kind.values())}


def promote_candidates(min_count: int = 2) -> list[dict]:
    """Recurring correction comments/verdicts -> candidates to graduate into the knowledge base."""
    counts: dict = {}
    for r in iter_records(accepted=False):
        sig = (r.get("comment") or r.get("verdict") or "").strip().lower()
        if not sig:
            continue
        key = hashlib.md5(sig.encode()).hexdigest()[:8]
        cc = counts.setdefault(key, {"signature": sig[:200], "count": 0, "kinds": set()})
        cc["count"] += 1
        cc["kinds"].add(r.get("kind"))
    out = [{"signature": v["signature"], "count": v["count"], "kinds": sorted(k for k in v["kinds"] if k)}
           for v in counts.values() if v["count"] >= min_count]
    return sorted(out, key=lambda x: -x["count"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    print(json.dumps(promote_candidates() if cmd == "promote" else stats(), indent=2))
