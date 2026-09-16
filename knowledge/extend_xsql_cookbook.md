# Extend xSQL Cookbook — canonical, tenant-validated query patterns

These are the **real** shapes that run inside a Xactly Extend datasource view. Compose measure/quota/
attainment/resolver views from these building blocks. **Do NOT hand-roll incentive math from raw ledgers.**

Companion doc: `knowledge/dashboard_render_defects.md` — the shipped-page defects (R1–R15) that these
rules exist to prevent. Read both.

---

## Rule 0 — never recompute what the engine computes
Attainment %, credited amount toward a quota, and payout are **engine outputs**. Get them from Xactly
table functions (`ShowQuotaAttainment`, `ShowPayment`/`ShowCredit`), NOT by `SUM(xactly.xc_credit.amount)`
+ ad-hoc quota math. Raw `xc_credit` / `xc_payment` are only for a **literal detail/ledger table**
(one row per transaction), never for attainment or KPI tiles.

## Rule 1 — a table function is the SOLE FROM, filtered by a non-correlated IN/WHERE
`ShowXxx(...)` is re-evaluated **once per probe row** if placed in a JOIN → gateway 504. Put it alone in
its own derived table, aggregate it, then join the aggregate. Bind real params (never NULL — NULL scans all
participants and times out).

## Rule 2 — the one-row contract (R1, R12)
**Every view behind a card, tile, or `Custom` control must return exactly one row, always** — including
when nothing matches. A zero-row result renders the literal string **`undefined`** on the page; it does not
render blank or `0`.

- Make the top level an **aggregate** (`SUM`/`MAX`/`COUNT`) with no `GROUP BY`. An aggregate over an empty
  set still returns one row (of NULLs).
- Wrap every output column in `Nvl(...)`, and put the `Nvl` **inside** the formatting (Rule 4).
- This is also how you guarantee a single row **without `rownum`** (Rule 3).

## Rule 3 — binding & typing: no casts, no `rownum` (2026-08-15 directive)
- **Bind the parameter directly.** `WHERE c.participant_id = :v_master_participant_id`.
  - ❌ **`ToNumber(:v_x)`** — banned. ❌ `ToString(col) = :v_x` — banned (per-row cast, defeats the index).
  - Type comes from the **query object**: declare `variables[{name, value, dataType}]` with
    `dataType: "Number" | "String" | "Date"`. Typing is declaration-side, not predicate-side.
- **No `rownum`, no `RowNumber()`, no `LIMIT`.** Reduce to one row by aggregating (Rule 2). Where you need
  one id out of many candidates, use `MAX(id)`; where you need "one of these values", use a non-correlated
  `IN (SELECT …)` instead of a scalar `= (SELECT … rownum = 1)`.
- **`participant_id`, never `eff_participant_id`.** Scope facts (`xc_credit`, `xc_commission`, `xc_payment`)
  on `participant_id`.

## Rule 4 — formatting (R2, R8)
- Money: `Concat('$', FormatNumber(Nvl(x, 0), '#,##0'))` — one format app-wide.
- Percent: `Concat(FormatNumber(Nvl(x, 0), '#,##0.0'), '%')`.
- **`Nvl` goes inside the format call.** `Nvl(Concat(...), '0')` is wrong: if the value is NULL you ship a
  bare `%` or `$` (that is exactly defect R2).
- `FormatNumber` already rounds — don't wrap it in `Round`. Formatting belongs in the **SELECT** only,
  never in a `WHERE`/`JOIN` predicate.
- Guard divide-by-zero with `CASE WHEN Nvl(denom, 0) = 0 THEN 0 ELSE num / denom END`.

## Rule 5 — resolve names, never hardcode them (R3, R4)
A measure / component / credit-type name is **data**, not a literal. Parameterize it (`:v_measure`) or
resolve it from the same list view that renders the label. One parameterized measure view beats three
views with `WHERE name LIKE '<Component>%'` — a literal that doesn't match the tenant silently yields `0`,
which looks like real data.

Corollary: **a breakdown column and its total must come from one rowset.** Build parts as
`SUM(CASE WHEN <key> = <resolved value> THEN amount ELSE 0 END)` over the total's rowset — not as
separately filtered sub-selects (that's how a shipped breakdown table showed every component at `0`
  beside a correct total).

---

## Pattern A — Measure card: attainment + credits + quota  (VALIDATED, ~2s)
One view, **parameterized by measure**. `ShowQuotaAttainment` gives attainment + credited total;
`xc_quota_assignment.amount` gives the quota value (walked up the period hierarchy). Both sides are
aggregates → each is exactly one row → the join is one row (Rule 2). **One period grain per card** (R5):
everything below is QTD; annual figures are separate, explicitly-named columns.

```sql
CREATE VIEW demo.seller_measure_card AS
SELECT
  Concat(FormatNumber(Nvl(cr.qtd_attainment, 0), '#,##0.0'), '%')  AS qtd_attainment_pct,
  Concat('$', FormatNumber(Nvl(cr.total_credit, 0), '#,##0'))      AS qtd_credits,
  Concat('$', FormatNumber(Nvl(qt.quota_amount, 0), '#,##0'))      AS qtd_quota,
  Concat(FormatNumber(CASE WHEN Nvl(qt.quota_amount, 0) = 0 THEN 0
                           ELSE Nvl(cr.total_credit, 0) / qt.quota_amount * 100 END,
                      '#,##0.0'), '%')                             AS qtd_attainment_recomputed_pct
FROM
  ( SELECT Nvl(SUM(qr.total_credit), 0)   AS total_credit,
           Nvl(SUM(qr.qtd_attainment), 0) AS qtd_attainment
    FROM ShowQuotaAttainment(
           ParticipantId = :v_master_participant_id,
           PeriodId      = ( SELECT MAX(period_id) FROM xactly.xc_period WHERE name = :v_quarter )
         ) qr
    WHERE qr.quota_name = :v_measure
  ) cr
JOIN
  ( SELECT Nvl(SUM(xqa.amount), 0) AS quota_amount
    FROM xactly.xc_quota_assignment xqa
    JOIN xactly.xc_period p ON p.period_id = xqa.period_id
    WHERE xqa.assignment_id = :v_master_position_id
      AND xqa.quota_id IN ( SELECT quota_id FROM xactly.xc_quota WHERE name = :v_measure )
      AND ( p.name = :v_quarter
            OR p.parent_period_id IN ( SELECT period_id FROM xactly.xc_period WHERE name = :v_quarter ) )
  ) qt ON 1 = 1
```
params: `v_master_participant_id`, `v_master_position_id`, `v_quarter`, `v_measure`
- `ShowQuotaAttainment(ParticipantId=, PeriodId=)` returns one row per quota: `quota_name`, `total_credit`,
  `quota_amount`, `Yearly_attainment`, `qtd_attainment`. Filter to one measure with `WHERE qr.quota_name = :v_measure`.
- Quota value = **`xc_quota_assignment.amount`** (NOT `xc_quota.quotavalue`). Resolve `quota_id` by name via `IN`.
- Period hierarchy: `p.name = :v_quarter` (booked at the quarter) **OR** `p.parent_period_id IN (…quarter…)`
  (booked at the parent/year and rolled down).
- `qtd_attainment_recomputed_pct` is the engine % re-derived from the two numbers the card **displays**;
  if it disagrees with `qtd_attainment_pct` the card is mixing grains (R5) — fix the query, don't ship both.
- Two single-row derived tables → `JOIN … ON 1 = 1` is fine **in view context**. (In strict
  variableConfigurator/whereClause context, prefer a constant-key join `ON a.k = b.k`.)

## Pattern B — Master participant id resolver (single row, no `rownum`)
```sql
CREATE VIEW demo.seller_master_participant_id AS
SELECT Nvl(MAX(master_pa.participant_id), 0) AS master_participant_id
FROM   xactly.xc_participant pa
JOIN   xactly.xc_period p
       ON pa.effective_start_date < p.end_date AND pa.effective_end_date > p.start_date
JOIN   xactly.xc_participant master_pa
       ON pa.employee_id = master_pa.employee_id AND master_pa.is_master = 1
WHERE  p.name = :v_year_name AND pa.name = :v_participant
```
- The aggregate guarantees **exactly one row** whether or not the rep resolves — no `rownum`, and no
  zero-row case that would 404 a downstream numeric `= :param` or render `undefined`.
- `Nvl(..., 0)` is the "no rep selected" sentinel: downstream views return empty rather than erroring.
- `MAX` is safe here because the master record is unique per employee (`is_master = 1`).

## Pattern C — Master position id resolver (single row; `xc_position` has TWO date ranges)
```sql
CREATE VIEW demo.seller_master_position_id AS
SELECT Nvl(MAX(pos.master_position_id), 0) AS master_position_id
FROM   xactly.xc_participant master_part
JOIN   xactly.xc_period curr ON curr.name = :v_year_name
JOIN   xactly.xc_participant part
       ON part.employee_id = master_part.employee_id
       AND part.effective_start_date < curr.end_date AND part.effective_end_date > curr.start_date
JOIN   xactly.xc_pos_part_assignment ppa ON ppa.participant_id = master_part.participant_id
JOIN   xactly.xc_position pos ON pos.position_id = ppa.position_id
       AND pos.effective_start_date < curr.end_date AND pos.effective_end_date > curr.start_date
       AND pos.incent_st_date       < curr.end_date AND pos.incent_end_date   > curr.start_date
WHERE  master_part.participant_id = :v_master_participant_id AND master_part.is_master = 1
```
- `xc_position` requires BOTH `effective_*` AND `incent_*` overlap. `xc_pos_part_assignment` has NO effective dates.
- If a rep can hold several concurrent positions, `MAX` picks one deterministically — when the page must
  choose, make it an explicit position **dropdown** instead of an implicit `MAX`.

## Pattern D — Quota list for a position (period hierarchy + effective dates)
```sql
SELECT xq.name, Nvl(FormatNumber(SUM(xqa.amount), '#,##0.00'), '0.00') AS quota_value
FROM   xactly.xc_quota_assignment xqa
JOIN   xactly.xc_period xp_m ON xp_m.name = :v_period
JOIN   xactly.xc_period xp_q ON xp_q.period_id = xp_m.parent_period_id
JOIN   xactly.xc_period xp_y ON xp_y.period_id = xp_q.parent_period_id AND xqa.period_id = xp_y.period_id
JOIN   xactly.xc_quota  xq ON xqa.quota_id = xq.quota_id
JOIN   xactly.xc_period qs ON xqa.effective_start_period_id = qs.period_id
JOIN   xactly.xc_period qe ON xqa.effective_end_period_id   = qe.period_id
WHERE  xqa.assignment_id = :v_master_position_id
  AND  qs.start_date <= xp_m.end_date AND qe.end_date >= xp_m.start_date
GROUP BY xq.name
ORDER BY 2 DESC
```
- `GROUP BY` the displayed key instead of `SELECT DISTINCT` over a fan-out (R7).

## Pattern E — Optional filters that render on load: the `All` sentinel
A dashboard must show data BEFORE the user touches a filter. Give each optional filter an `All` branch and
seed the driving dropdown to `'All'` (include an `All` row in its list view):
```sql
WHERE p.name = :v_quarter                                   -- required scope
  AND ( :v_measure = 'All' OR ct.name = :v_measure )        -- optional
  AND ( :v_granularity = 'All' OR g.name = :v_granularity ) -- optional
```
- A blank/`All` filter returns the full set instead of 0 rows. This is what prevents "undefined/empty on load".
- Required, resolved ids (`:v_master_participant_id`, `:v_master_position_id`) need **no** guard and **no**
  cast — Pattern B/C already guarantee a value (`0` when unresolved).

## Pattern F — Participant scoping: ALWAYS resolve via the selected-rep chain
**Never** scope a query to a person with a current-user / user-context lookup function
(`LookupCurrentUserMasterParticipantId()`, `LookupCurrentUserMasterPositionId()`, or any
`LookupCurrentUser*`). These resolve to the *logged-in* user, so the page shows the viewer's own data
instead of the participant selected in the filter — this breaks the rep picker for every user, IC and
manager alike. Treat these functions as **disallowed for all users**.

Scope every person-filtered view on the resolver chain outputs — rep dropdown (`:v_participant`) →
Pattern B (`:v_master_participant_id`) → Pattern C (`:v_master_position_id`):
```sql
WHERE c.participant_id = :v_master_participant_id     -- participant-scoped (NOT eff_participant_id)
WHERE xqa.assignment_id = :v_master_position_id       -- position-scoped
```
- Even an IC "self-view" uses this chain — the rep dropdown simply defaults to the current rep via a VC.

## Pattern G — Trend view: one row per period, zero-filled (R14)
A trend chart needs a row for **every** period in the range, not just periods with data — otherwise the
line collapses onto two points and the axis rescales to whatever series is largest.
```sql
CREATE VIEW demo.seller_attainment_trend AS
SELECT p.name                                                      AS period_name,
       Nvl(SUM(a.attainment_pct), 0)                               AS attainment_pct,
       Nvl(MAX(g.goal_pct), 0)                                     AS accelerator_goal_pct
FROM   xactly.xc_period p
LEFT JOIN demo.seller_attainment_by_period a ON a.period_id = p.period_id
LEFT JOIN demo.seller_accelerator_goal     g ON g.period_id = p.period_id
WHERE  p.parent_period_id IN ( SELECT period_id FROM xactly.xc_period WHERE name = :v_year_name )
GROUP BY p.name, p.start_date
ORDER BY p.start_date
```
- The **period table is the spine**, joined LEFT to the facts — that's the zero-fill.
- **All plotted series must share one unit.** Chart percents with percents; never put a credit amount
  (millions) and an attainment % (0–200) on the same axis.

## Pattern H — Detail / ledger hygiene (R6, R7)
```sql
SELECT o.order_code, p.name AS rep, ct.name AS product_family,
       Nvl(FormatNumber(SUM(c.amount), '#,##0.00'), '0.00') AS amount
FROM   xactly.xc_credit c
JOIN   xactly.xc_participant p ON p.participant_id = c.participant_id
JOIN   xactly.xc_order o       ON o.order_id = c.order_id
JOIN   xactly.xc_credit_type ct ON ct.credit_type_id = c.credit_type_id
WHERE  c.participant_id = :v_master_participant_id
  AND  o.order_code NOT LIKE 'Trigger%'          -- engine trigger/adjustment rows are not deals
GROUP BY o.order_code, p.name, ct.name           -- de-dup the join fan-out at the displayed grain
```
- Exclude engine-generated trigger/adjustment/reversal rows from anything called a *deal* ledger.
- `GROUP BY` exactly the displayed columns; if two columns always carry the same value, ship one.

---

## Query OBJECT contract (what actually ships)
A datasource is a query OBJECT, not a bare .sql file: `queries/<schema>/<name>.json`
```json
{ "name": "<view>", "schemaName": "demo", "xsql": "<CREATE-less SELECT or view body>",
  "variables": [ { "name": "v_quarter", "value": "All", "dataType": "String" },
                 { "name": "v_master_participant_id", "value": "0", "dataType": "Number" } ],
  "savedInEditor": true, "isValid": true, "properties": {} }
```
- A page control's `datasource.name` + `.schema` MUST equal a shipped query object's `name`/`schemaName`.
- Every `:v_param` in `xsql` is a page variable; seed its **default** in `variables[]` (e.g. `All`, `0`, or a
  current period id) and declare its **`dataType`** — that declaration is what types the bind, which is why
  the predicate needs no `ToNumber`.
- Do NOT default a param to a `LookupCurrentUser…` value — resolve the participant via the selected-rep chain.

## Anti-patterns (these are why generated views were "not compatible")
- ❌ `ToNumber(:v_x)` anywhere, or `ToString(col) = :v_x` in a predicate → declare `dataType` and compare directly.
- ❌ `rownum = 1` / `RowNumber()` / `LIMIT` → aggregate to one row (`MAX`, `SUM`) or use a non-correlated `IN`.
- ❌ `eff_participant_id` → `participant_id`.
- ❌ A card/tile view that can return **zero rows** → renders `undefined` (R1). Aggregate it.
- ❌ `Nvl(Concat(x, '%'), '0%')` → the NULL is inside; you ship a bare `%` (R2). `Nvl` goes innermost.
- ❌ Hardcoded measure/component names (`LIKE '<Component>%'`) → parameterize or resolve (R3/R4).
- ❌ `SUM(c.amount)` from `xc_credit` as "credits earned toward attainment" → use `ShowQuotaAttainment.total_credit`.
- ❌ `MAX(xq.quotavalue)` from `xc_quota` as the quota → use `SUM(xc_quota_assignment.amount)`.
- ❌ `ShowQuotaAttainment(...)` inside a JOIN → 504; make it the sole FROM.
- ❌ NULL params to a table function → full scan/timeout; always bind resolved ids.
- ❌ `LookupCurrentUser*` → binds to the logged-in user, not the selected rep; use Pattern B/C for ALL users.

---

## Rule 12 — the 300-line ceiling: compose, don't copy

**A view over ~300 lines does not run.** That is an operational limit, not a style
preference, and it binds hardest exactly where you are most tempted to copy-paste:
a dashboard with three measure tiles, three payout tiles, three detail grids and a
leaderboard, all needing the same period/quota/commission logic.

Written naively, the v3 Seller Dashboard's quota rule (R1, an overlap test plus a
correlated `MAX(effective_start)` — 28 lines) appears **11 times**. The measure
scorecard alone hit 140 lines with two of its four subqueries inlined.

### The pattern: parameterless helper views + short leaves

Hoist every rule that would repeat into a **parameterless** view keyed by the
columns consumers filter on. Leaves bind `:params` and stay short.

```sql
-- helper: no :params, resolves the rule once, keyed for lookup
CREATE VIEW demo.seller_quota_effective AS
SELECT xqa.assignment_id, q.name AS quota_name, psel.name AS period_name,
       Nvl(SUM(xqa.amount), 0) AS quota_amount
FROM   ...28 lines of R1 version-selection...
GROUP BY xqa.assignment_id, q.name, psel.name

-- leaf: 5 lines, and structurally cannot get the version rule wrong
JOIN ( SELECT Nvl(SUM(qe.quota_amount), 0) AS amt
       FROM   demo.seller_quota_effective qe
       WHERE  qe.assignment_id = :v_master_position_id
         AND  qe.quota_name    = 'Revenue'
         AND  qe.period_name   = :v_quarter ) qq ON 1 = 1
```

v3 ships four helpers — quota-effective, commission-attribution, credit-enriched,
payment-scoped — and its **longest** view is then 95 lines.

### Keep helpers parameterless

Do not put `:params` in a helper that another view selects from. Bind propagation
into a nested view is not something to rely on; put the bind predicates in the
consuming leaf, where the query object declares them. A helper that needs a
per-request value should expose the raw column and let the leaf filter it (H3
exposes `batch_name`; the leaf applies the `:v_lock_status` gate).

### Two consequences worth knowing

- **Correctness concentrates.** Fixing the quota rule is one edit in one view, not
  eleven edits you might do ten of.
- **The lint's "card view has no aggregate" warning goes false-positive** on
  helpers whose names end in `_measure` / `_id`. A helper feeding a `table` is
  meant to be multi-row. Record the reason and move on.

### Still repeat when the literal is the only difference
Three measure tiles differing solely in `'Revenue'` / `'Sales Profitability'` /
`'BXO TPV'` stay as three views. Merging them behind a `:v_measure` param would
merge them into one control — and the design calls for three tiles side by side.
Repetition of a *literal* is fine; repetition of a *rule* is the thing to hoist.
