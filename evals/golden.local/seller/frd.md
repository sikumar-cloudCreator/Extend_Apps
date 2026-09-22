# INTRODUCTION
FRD for a Seller Performance dashboard app in Xactly Extend.

# OVERVIEW
Two pages: a Sales Dashboard (KPIs + by-measure detail) and a Payouts page.

# PAGES

## SALES DASHBOARD
### User Stories
- As a seller, I want YTD credits and attainment by measure so I can track performance.
### Filters at the top of the page
- Period, Participant.
### Fields and their source
| Field | Datasource view | Column | Params |
|---|---|---|---|
| Measure detail | q_sd_annual_credits_by_measure | measure_name, annual_ytd_credits | :v_period |

## PAYOUTS
### User Stories
- As a seller, I want to see payouts by measure.
### Fields and their source
| Field | Datasource view | Column | Params |
|---|---|---|---|
| Payouts | q_sd_payouts_by_measure | measure_name | :v_period |

# DOCUMENT ACCEPTANCE
| Name | Role | Date |
|---|---|---|
|  | Sponsor |  |
