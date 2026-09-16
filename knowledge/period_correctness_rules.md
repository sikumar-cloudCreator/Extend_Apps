# Period-correctness rules (R1–R5)

Source: a customer working session on quota/commission reporting, 2026-09-04.
Customer specifics are deliberately omitted; the rules below are general to any
Xactly tenant. Figures are illustrative.

These are the five domain rules that decide whether a compensation dashboard is
*correct*, as opposed to merely rendering. Every one of them came out of a defect
found on a shipped page. Apply them to any Xactly page that shows quota,
attainment, credits, commission or payout by period.

Reference implementation: v3 Seller Dashboard, `build/datasources.sql`, helper
views H1–H4.

---

## R1 — Quota is the version in force for the **selected** period

> "We want that quota to be based on the payment period. If they're paid in Q1 on
> version 1, we don't want that to reflect version 2 that was effective April,
> because that quota does not match what was used for that payment."

Quota assignments are versioned by effective period window. A rep with a Jan–Mar V1
of 10M and an Apr–Dec V2 of 20M must show **10M when Q1 is selected** and 20M when
Q2 is selected. Not "the latest version" — the version that was in force.

The original defect was worse than picking the wrong version: it summed **both**,
reporting 30M.

**The pattern** (H1, `demo.seller_quota_effective`) — two filters, both required:

```sql
-- 1. overlap: only versions whose effective window touches the period survive
WHERE  qstart.start_date <= psel.end_date
  AND  qend.end_date     >= psel.start_date
-- 2. newest-in-force: if two still overlap, keep only one, so SUM cannot double
  AND  qstart.start_date  = ( SELECT MAX(w_start.start_date)
                              FROM   ... same joins, same overlap test ...
                              WHERE  w.assignment_id = xqa.assignment_id
                                AND  w.quota_id      = xqa.quota_id
                                AND  w_sel.period_id = psel.period_id )
```

Filter 1 alone is *usually* enough and is what most tenants get away with. Filter 2
is what makes the doubling structurally impossible instead of merely unlikely.

Resolve this **once**, in a parameterless helper view keyed by
`(assignment_id, quota_name, period_name)`. Every consumer then reads a single
short predicate and cannot get it wrong.

---

## R2 — Quotas load **cumulative**. Cumulation is **grain-aware**.

> "We don't load the quarterly value, we load quarter-to-date value. We would load
> 10, then 20, then 30 — not 10, 10, 10."
> "You're adding the quarters up. That's not how quota is actually structured."

What "cumulative" means depends on how the tenant **loads** quota:

| Pivot grain | What each row holds | QTD / in-force YTD |
|---|---|---|
| **YEAR** (one annual row) | Full-year amount | Prorate with `ordinal/4` — **do not** also `SUM` across quarters or it multiplies |
| **PERIOD** (separate Q1–Q4 rows) | That quarter's slice only | `SUM` amounts where `quarter_ordinal <= selected_ordinal` **after** R1 has picked one in-force version per quarter |

Therefore:

- ✅ branch on grain — PERIOD cumulates ordinals; YEAR prorates
- ✅ version selection (R1) happens **before** cumulation; cumulation never re-opens versions
- ❌ `annual_quota / 4` when the pivot already carries period amounts (live defect in
  `seller_measure_branded_checkout` v2, and again when PERIOD grain was mis-read as "row at quarter")
- ❌ any "divide by remaining quarters" arithmetic
- ❌ reading only `period_name = :v_quarter` on a PERIOD-grain pivot and calling it QTD —
  that is **this quarter**, not year-to-date (Seller Dashboard fix, 2026-09-09)

Same for credits used against a cumulative quota: compare QTD credits to the QTD
quota, YTD credits to the annual quota. Never mix the two grains.

See also `knowledge/runtime_data_defects.md` **D3**.

---

## R3 — Historical credits cannot be replayed today. Gate it, don't fake it.

> "We cannot go back and tell you what your attainment was after we've already
> processed PPAs."

Prior-period adjustments are loaded back onto the *original* incentive date, so a
Q1 credit and a Q1-dated PPA processed during Q2 are indistinguishable after the
fact. Q1 attainment as it stood at Q1 close is **not recoverable** from the current
data. Do not invent a reconstruction.

What you build instead is the **hook**, plus the swap point:

```sql
-- 'current'  : as it stands today, PPAs rolled into the selected quarter
-- 'as_paid'  : only rows whose PROCESSING period is the selected quarter
AND ( :v_lock_status = 'current'
      OR ce.batch_name LIKE Concat('%', Concat(:v_quarter_code, '%')) )
```

- **Interim source: batch name.** Batch names carry the processing quarter. Chosen
  over `created_date` because a reset/recalc rewrites `created_date` and silently
  reclassifies history — the comp-ops objection, and it is correct.
- **Target source: a processing-period date column** on the order load. The call
  agreed a **date**, not a string. `xc_order_stage.Order_Custom_Field1` is the
  landing spot in this tenant; H3 already surfaces it as `processing_period_raw`.
  When it is populated, swap the predicate and delete the batch branch.

Pair the hook with a visible **reporting-basis selector** so the number on screen
always states which basis it is on. A dashboard that silently switches basis is
worse than one that cannot switch at all.

---

## R4 — Commission ≠ payment. Show both, never conflate.

> "My commission could be $50,000 as of Q3, but my payment for Q3 would be $15,000,
> because I already paid $45,000 in Q1 and Q2."

| | Grain | Source | Question it answers |
|---|---|---|---|
| **Commission** | running **YTD** | `xc_commission` | "What have I earned this year?" |
| **Payment** | discrete, per period | `xc_payment` | "What am I getting paid this quarter?" |

Annual plans calculate commission year-to-date on year-to-date performance; the
payment is that minus what was already released. A page showing only payment cannot
be reconciled by a rep, which is why the v2 dashboard was rejected.

Two consequences for layout:

1. Every measure tile carries **both** QTD commission and YTD commission.
2. Releases get **one line per quarter**, not a single blended figure:
   `Released Q1 / Released Q2 / Pending Q3`, plus a total. One number invites
   exactly the wrong question — "is that the quarter or the year?"

---

## R5 — Commission attribution is a two-part query

> "All the commissions generated will use quota, but the ones where I deduct
> previous earnings would have the word *previous* in the commission rule name."
> — "I'd pull based on the quota name, and one based on the actual rule name, and
> join those two together to get you one final number." (comp ops)

`xc_commission` rows split in two:

- **Earned** — carry `quota_name`. Attribute by quota name.
- **True-up** — the rule that negates previously earned commission. Carries **no**
  quota; the measure is only in `rule_name`, alongside the token `previous`.

Miss the second half and every YTD commission figure is overstated by the whole
true-up. Resolve it once, in a helper view (H2,
`demo.seller_commission_measure`), that normalises both into `measure_name` +
`commission_kind ∈ {Earned, True-up}`. Consumers then filter on a clean column, and
Prior Period Pay becomes `commission_kind = 'True-up'` for free.

Match `'%revious%'` — case varies across rule names.

---

## Note on cookbook Rule 0 / ShowQuotaAttainment

**Superseded 2026-09-16 by Xactly official BP Q18** (`knowledge/xactly_extend_best_practices.md`):
do **not** use `ShowQuotaAttainment()` for employee-facing attainment, payout, or MBO.

Keep computing quota selection explicitly from `xactly.xc_quota_assignment` + effective periods
(H1 / R1–R2). Additional reasons this remains correct even aside from the official ban:

- The function is keyed on **participant**; assignments are held by **position** — mid-year
  position changes diverge.
- Its period/version semantics are opaque; overlapping versions cannot be inspected or pinned
  the way H1 does.

What is **not** established (and no longer needed for the build path): what the function returns
when two versions overlap a quarter. Do not call it for compensation tiles.
