# INTRODUCTION
FRD for a Rep Payout Summary dashboard in Xactly Extend.

# OVERVIEW
A rep-facing page: payout KPI tiles across the year to date, plus a by-measure payout breakdown,
filtered by participant and period.

# APPLICATION LAYOUT
One page, "Payout Summary", in the nav. Global filters: Period, Participant.

# PAGES

## PAYOUT SUMMARY
### User Stories
- As a rep, I want my total credits, commissions, released and pending payout for the period so I can
  check my statement before it is paid.
- As a rep, I want the same figures broken out per measure so I can see which component drove the payout.

### Assumptions
- The participant is chosen in a filter and resolved to a master participant / master position by the
  standard resolver chain; the year is derived from the selected period.
- Payout figures come from the engine, not from re-summed ledgers.

### Filters at the top of the page
- Period, Participant.

### Fields and their source
| Field | Component | Datasource view | Column | Params |
|---|---|---|---|---|
| Total YTD Credits | KPI tile | q_sd_summary_kpis | total_ytd_credits | :v_master_participant_id, :v_period, :v_year_number |
| Total Commissions | KPI tile | q_sd_summary_kpis | total_commissions | :v_master_participant_id, :v_period, :v_year_number |
| Total Released | KPI tile | q_sd_summary_kpis | total_released | :v_master_participant_id, :v_period, :v_year_number |
| Total Pending | KPI tile | q_sd_summary_kpis | total_pending | :v_master_participant_id, :v_period, :v_year_number |
| Measure | Detail table | q_sd_payouts_by_measure | measure_name | :v_master_participant_id, :v_master_position_id, :v_period, :v_year_number |
| Calculated / Released / Pending payout | Detail table | q_sd_payouts_by_measure | calculated_payout, released_payout, pending_payout | as above |

# DOCUMENT ACCEPTANCE
Accepted for build.
