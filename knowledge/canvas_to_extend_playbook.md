# Canvas → Extend page, in one pass

Companion to `prompts/30_page_designer.md`. That prompt takes an **FRD page-spec**.
This one takes an **HTML canvas** — a hand-designed or AI-generated static mockup —
and turns it into a page that renders the same thing, first try, no iteration.

Worked reference: `seller_dashboard_canvas.html` → the v3 Seller Dashboard export
(46 views, 46 controls, PASS on all four gate stages). Read that export beside this.

---

## 0. The single-pass contract

A canvas is not a spec, it is a **rendering**. Read it as three separable layers and
resolve all three before emitting anything:

| Layer | What you extract | Where it lands |
|---|---|---|
| **Structure** | section order, row grouping, tile counts | control order + `layoutSize` |
| **Data** | every distinct number/string on the page | one view column, one bound variable |
| **Behaviour** | what changes when a filter moves | the event graph |

The failure mode that forces a second pass is always the same: you emit structure
and data, then discover a control needs a variable that nothing produces. **Build
the variable inventory first** (§3), and that cannot happen.

---

## 1. Read the canvas top-to-bottom, once

Walk the DOM in order. Every `<section>` becomes one of five things — there is no
sixth, and guessing outside this table is what produces unrenderable pages:

| Canvas pattern | Control | Why |
|---|---|---|
| Banner / heading + sub + badge | `Custom` (or `label`) | fixed text, no rows |
| Small box, 2–8 labelled numbers | `Custom` with `bound` | fixed field set |
| Box whose field count depends on data | `table` | **never** `Custom` |
| `<table>` with a `<thead>` | `table`, columns from `<th>` in order | headers are the spec |
| `<canvas>` / any plotted series | `composedChart` | |
| `<select>` | `dropdown` | |
| `<input type=text>` for filtering | `input`, `useEnterBroadcast: true` | |
| Tab strip | `tabContainer` + one `tab` per button | children nest in `tab.pageSchema` |
| A value with no visible control (e.g. "Refreshed <date>") | `vc` | invisible driver |

**Hard exclusion — no dynamic grids.** If the canvas implies columns that vary by
data (a pivot, a "column per month", a matrix), you do **not** generate columns at
runtime. Either fix the column set (name every column explicitly, as the v3 Credit
Details grid does) or restructure the view to be tall rather than wide. A `Custom`
control renders only the fields you hardcode; a `table` renders only the `columns`
you declare. Neither invents a column.

### Reading a `<th>` row
The `<thead>` is the column contract, verbatim and in order. `headerName` is the
`<th>` text; `field` is the snake_case view column you will author to match. Do not
reorder, do not drop, do not add. If the canvas shows 12 columns, the view returns
12 columns and the table declares 12.

---

## 2. Structure → layout

`prompts/30_page_designer.md` §"Layout alignment" is authoritative: rows sum to 100,
allowed widths only, headers/tables/charts/search inputs are always `100` alone.

Canvas → width, mechanically:
- `grid-cols-3` / three sibling cards → `33.33` each
- `grid-cols-4` → `25` each
- a 6-cell strip → `16.66` each
- `grid-cols-5` → **does not divide**; split 3+2 across two rows, or make it one
  `Custom` block with an internal CSS grid (what v3 does for the profile strip and
  the waterfall band — one control, `layoutSize: 100`, `repeat(auto-fit, minmax(...))`
  inside). Prefer the single-control form when the cells are one logical unit: it
  also survives narrow viewports, which six `16.66` controls do not.

---

## 3. Data → the variable inventory (do this before writing any control)

Enumerate **every** distinct value the canvas displays. For each, decide one of:

1. **Comes from a view column** → needs `bound: [[v_x, column]]` on a `Custom`, or a
   `table` column, or a `vc`.
2. **Comes from a filter the user sets** → the `dropdown`'s `var`.
3. **Is static copy** → inline it in the HTML, no variable.

Then check the two closure rules the gate enforces, *before* emitting:

- **Every `{{v_x}}` token has a producer.** A token with no producing control is a
  page that renders `{{v_x}}` literally to the user.
- **Every variable a control owns has a consumer** — some view takes it as a
  `:param`, or another control binds it, or the page's own HTML prints it. A
  variable nothing consumes is a control that does nothing, and the render gate
  fails the page for it. v3 shipped three of these inherited from v2
  (`v_session_id`, `v_year_number`, `v_team_hide`); two were deleted and the third
  was given a guard that references it (`validationXsql: ":v_team_hide=1"`).

Naming: `v_<area>_<field>`, short and collision-free (`v_rev_qcredits`,
`v_ctr_row_count`). Reuse one prefix per tile so a reader can see at a glance which
control owns which token.

---

## 4. Behaviour → the event graph

Extend has no reactive binding. **Nothing refreshes unless an event tells it to.**
A canvas cannot show you this — you infer it from what each filter logically affects.

### The bootstrap spine is fixed. Copy it.
Identity and period resolution is the same on every seller-facing page. Chain it
**linearly**, one `vc` per link, each binding the previous link's CREATE event:

```
$onPageLoad
  → defaultperiod        (latest closed month)
  → year_name_vc         (:v_year_name)
  → defaultparticipant   (:v_participant)
  → current_period_id    (:v_current_period_id)
  → month_start_date     (:v_month_start_date)
  → default_quarter      (:v_quarter)
  → master_participant_id(:v_master_participant_id)   ← also binds rep_select
  → master_position_id   (:v_master_position_id)
  → quarter_code         (:v_quarter_code)            ← last link
        ↓
   every data control binds master_position_id / quarter_select
```

**Linear, not fan-out.** Two `vc`s bound to the same upstream event have *no
ordering guarantee* between them. If a downstream view binds both their variables,
it can fire with one unresolved. v3 hit exactly this: `month_start_date` and
`default_quarter` both hung off `current_period_id`, and
`seller_team_leaderboard` binds `:v_month_start_date` — so `default_quarter` was
rechained beneath `month_start_date`. When in doubt, make it a chain.

**PageLoader hides mid-chain, never on the terminal link.** `showLoader` on
`$onPageLoad`; `hideLoader` on an event that always fires on load *and* by which
the period is resolved (`default_quarter` in v3). Hiding on the deepest channel
leaves the loader spinning forever if any link fails — a shipped defect.

### Seeding a variable with no view
A filter default that is a constant (a lock status, an empty search string) is a
`vc` with `useStaticValue: true` and `staticValue: "<const>"`, fired on
`$onPageLoad`. Do this for **every** `:param` a view binds that no dropdown sets on
load, or the first query runs with an unbound param.

### Show/hide gates come in complementary pairs
A role-gated section needs *both* halves wired, or it fails silently in one
direction (see `reference_extend_showhide_gate`):

```
vc  seller_team_gate_manager → CREATE team_show, validationXsql ":v_team_show=1"
vc  seller_team_gate_ic      → CREATE team_hide, validationXsql ":v_team_hide=1"
target control: BIND team_show → ["show"], BIND team_hide → ["hide"]
                plus shouldRenderHidden: true   (hidden until proven otherwise)
```

Default hidden and show on proof. Never default visible and hide on proof — if the
gate view returns zero rows the section stays exposed to the wrong audience.

### Tab children need `$onTabOpen`
A control inside a `tab` is not rendered until the tab opens, so it misses events
broadcast earlier. Every data control inside a tab binds `$onTabOpen → refresh`
**in addition to** its normal filter subscriptions.

---

## 5. Emit, then gate — never emit and stop

```bash
check_extend.sh <page.json> <views.sql>   # structure + xSQL + render quality
check_extend.sh <bundle_dir>              # datasource/param resolution across the export
```

Four stages. `RESULT: ✓ PASS` on all four is the definition of done. The render
stage is the one that catches canvas-specific mistakes — unconsumed variables,
partially-bound datasources, tiles that can render `undefined`.

Warnings you may leave, with a reason recorded:
- *hardcoded name literal* on a per-measure view. Three tiles need three literals;
  parameterising would merge them into one control, which is not the design.
- *card/tile view has no aggregate* on a **helper** row-set view. The check matches
  on name suffix (`_measure`, `_id`); a helper feeding a `table` is meant to be
  multi-row.
- *filter has no All-branch* when the all-branch is `:v_x = ''` and the variable is
  seeded by a static `vc`. The checker looks for `IS NULL` / `'All'`.

Everything else, fix.
