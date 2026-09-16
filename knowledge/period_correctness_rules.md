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

## R2 — Quotas load **cumulative**. Never sum periods.

> "We don't load the quarterly value, we load quarter-to-date value. We would load
> 10, then 20, then 30 — not 10, 10, 10."
> "You're adding the quarters up. That's not how quota is actually structured."

The quota row **at** a period already contains everything to date. Therefore:

- ✅ read the row at the selected period: `qe.period_name = :v_quarter`
- ❌ `SUM` across Q1+Q2+Q3
- ❌ `annual_quota / 4` to derive a quarter (this was a live defect in
  `seller_measure_branded_checkout` v2)
- ❌ any "divide by remaining quarters" arithmetic

Same for credits used against a cumulative quota: compare QTD credits to the QTD
quota, YTD credits to the annual quota. Never mix the two grains.

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

## Note on cookbook Rule 0

`extend_xsql_cookbook.md` Rule 0 says: don't recompute what the engine computes —
prefer `ShowQuotaAttainment` over `SUM(xc_credit.amount)` + quota math.

That rule stands generally. R1/R2 are the documented exception: the requirement is
explicit control over *which quota version* is read, and an engine attainment
function applies its own period semantics that you cannot inspect or override. The
v3 views therefore compute quota selection explicitly, from
`xc_quota_assignment` + effective periods.

**Open, unverified.** What is established from existing exports:

- `ShowQuotaAttainment` **does** return a quota value, so it could in principle
  replace H1. Signature `(ParticipantId=, PeriodId=)` or
  `(PeriodName=, ParticipantName=)`; columns `quota_name, total_credit,
  quota_amount, Yearly_attainment, qtd_attainment, month_attainment`.
- Two prior builds had it available and **still hand-rolled the quota** from
  `xc_quota_assignment` — including one headed "rebuilt to the engine-native
  pattern". Neither wrote down why. That build also had no effective-date
  filtering and used `quota_amount / 4`, so it carried both the R1 and R2
  defects: going engine-native is not by itself a route to a correct quota.
- **Scope mismatch, independent of the version question.**
  `ShowQuotaAttainment` is keyed on **participant**; quota assignments are held
  by **position**. For a rep who changed position mid-year these are different
  sets, so the function may not be a drop-in for H1 even if it applies the
  in-force rule.

What is **not** established: what it returns when two versions overlap a
quarter. That needs one run against a tenant. Until then, keep H1.
