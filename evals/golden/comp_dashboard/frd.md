# FRD — Compensation / Seller Dashboard (gold class)

## Intent
IC and manager compensation dashboard: quota in force for the selected quarter, YTD credits and attainment by measure, YTD commission vs released/pending payout, supplemental incentives, historical attainment trend by measure, searchable credit details by measure tab, and a role-gated team leaderboard for managers.

## Pages
1. **Seller Dashboard** — single page.

## Filters
- Seller representative (defaults from resolver chain)
- Fiscal quarter (defaults from current period spine)
- Performance measure selector for the historical trend (Revenue / Sales Profitability / BXO TPV)
- Credit search box

## Sections (required)
1. Header with refresh timestamp
2. Profile strip (name, role, position, manager, effective dates)
3. Performance measures matrix (all measures × credits, cumulative quota, attainment, annual, commission, released, pending)
4. Payout by quarter (one row per quarter — never merge released + pending into one figure)
5. Supplemental cards: SPIFF, Milestone Bonus, Prior Period Pay, Draw/Guarantee
6. Historical attainment trend (percent only) driven by measure selector
7. Credit details in tabs (Revenue / Profitability / BXO / Supplemental) with totals strip + grid; cumulative through selected quarter
8. Team performance matrix — visible only for Manager/Leader

## Data rules
- Customer-defined schema; fully qualify all objects
- Quota = version in force for selected period; cumulative grain-aware
- No ShowQuotaAttainment for employee-facing attainment/payout
- Commission ≠ payment; show both
- Dedup enrichment joins before SUM

## Delivery
Assembler write_bundle + pack_bundle only; import_ready + simulate must PASS.
