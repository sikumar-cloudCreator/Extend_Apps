# Runtime data defects — numbers that pass the gate and still lie

Source: Seller Dashboard iteration **2026-09-05 → 2026-09-10** (v3.x → v5.7), distilled
to tenant-agnostic rules. These are the failure classes where every structural gate
passes and the page still shows **$0.00**, **inflated SUMs**, or a QTD quota that is
really "this quarter only".

Companion to `period_correctness_rules.md` (domain) and `dashboard_render_defects.md`
(render). Enforcement today is prompt + cookbook + seed lessons — not a lint yet.

---

## D1 — Enrichment join fan-out (extends render R7)

| Symptom | Root cause | Rule |
|---|---|---|
| Every credit / portfolio / ledger aggregate is **~3× too high**; `COUNT(*)` on the enrichment view ≫ `COUNT(*)` on `xc_credit` | Joined `xc_order_stage` on `(order_code, item_code)` — that is **not** its key (`ORDER_STAGE_ID`, `PERIOD_ID`). Multiple active rows per order key across period / batch / upload / version. `xc_customer` is period-versioned the same way. | **Collapse enrichment lookups to one row per business key before any `SUM`.** Dedup with `GROUP BY` + `Max(...)` (no window functions in this engine). Verify: enrichment row count must equal the spine credit count. |

```sql
-- one row per (order_code, item_code)
LEFT JOIN (
  SELECT os.order_code, os.item_code,
         Max(os.descr) AS descr, Max(os.batch_name) AS batch_name
  FROM   xactly.xc_order_stage os
  WHERE  os.is_active = '1'
  GROUP BY os.order_code, os.item_code
) o ON o.order_code = c.order_code AND o.item_code = c.item_code
```

---

## D2 — Flag columns are strings, not numbers

| Symptom | Root cause | Rule |
|---|---|---|
| Released **and** pending payout both `$0.00` at once | `xc_payment.IS_RELEASED` (and `IS_ACTIVE` on stage/customer/credit) is `string(1)`. Predicates `= 1` / `= 0` match nothing. | **Compare flag columns as strings:** `is_released IN ('1','Y')`, `is_active = '1'`. Make pending the **complement** of released so the two always total. Quote literals so the predicate can push down instead of coercing per row. |

---

## D3 — Quota cumulation is grain-aware (refines period R2)

| Symptom | Root cause | Rule |
|---|---|---|
| QTD quota cell shows **one quarter's** amount, not year-to-date in force | Pivot is **PERIOD** grain (separate Q1–Q4 rows). Reading only `period_name = :v_quarter` returns that quarter alone. | **Branch on grain.** PERIOD: `SUM` amounts where `quarter_ordinal <= selected_ordinal` (after R1 has already picked one in-force version per quarter). YEAR: keep `ordinal/4` proration — and **do not** also sum across quarters or it multiplies. Never `annual_quota/4` when the pivot already carries period amounts. |

Version selection (period R1) and cumulation are **two steps**. Cumulation must not re-open the version question.

---

## D4 — Period predicates must match grain across facts

| Symptom | Root cause | Rule |
|---|---|---|
| Commission / payment tiles `$0.00` while credits look fine | Commission filter required the commission period to sit **entirely inside** `[year_start, quarter_end]`; credits only tested start-date overlap. Any period coarser than monthly failed every row. | **Keep period tests symmetric across facts.** If credits use start-date-in-range / overlap, commission and payment use the same shape — never a stricter "wholly contained" test on one side only. |

---

## D5 — Bundle import / datasource resolution (see also `import_blockers.md`)

Observed on ClaimRequest **2026-09-05** and Seller Dashboard v3.4 drift:

| # | Rule |
|---|---|
| I1–I5 | Zip root, real hex UUIDs, bare SELECT in `xsql`, CSV column counts, ADLC↔files — `gate/check_import_ready.py` |
| S8 | Control binds a datasource the bundle does not ship → empty forever (ERROR) |
| S9 | Query ships with no consumer → drift (WARN); three stranded on Seller v3.4 after a layout change |

---

## Where each rule lives

| Rule | Prompt / seed | Cookbook |
|---|---|---|
| D1 | `knowledge_base` SEED (query) | Rule 13 |
| D2 | `knowledge_base` SEED (query) | Rule 13 |
| D3 | supersedes period R2 seed; `period_correctness_rules.md` | Rule 13 |
| D4 | `knowledge_base` SEED (query) | Rule 13 |
| D5 | `import_blockers.md` + orchestrator prompt | — |
