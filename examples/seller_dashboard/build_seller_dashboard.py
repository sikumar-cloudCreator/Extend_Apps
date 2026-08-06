import sys, json, os
sys.path.insert(0, os.path.expanduser("~/Downloads/extend-llm/gate"))
sys.path.insert(0, os.path.expanduser("~/Downloads/extend-llm/app"))
import extend_build as eb
import schema_tools as st

PID = "31f22653-5cb2-424d-b51c-9a197bc0d887"

def _stat(k, v, color="#f1f5f9"):
    return (f'<div style="display:flex;justify-content:space-between;padding:9px 0;border-top:1px solid #1c2740;font-size:13px;">'
            f'<span style="color:#93a3b8;">{k}</span><span style="font-weight:700;color:{color};">{v}</span></div>')

def ring_html(title, accel, av):
    # ring fill % and color via inline ternaries on the bound numeric attainment (no view math needed)
    p = "{{%s_attain > 100 ? 100 : %s_attain}}" % (av, av)
    c = "{{%s_attain >= 100 ? '#22c55e' : '#38bdf8'}}" % av
    accel_html = (f'<span style="font-size:10.5px;font-weight:700;color:#9fd8c0;background:rgba(52,211,153,.10);'
                  f'border:1px solid rgba(52,211,153,.25);border-radius:7px;padding:5px 8px;white-space:nowrap;">{accel}</span>') if accel else ''
    return (
     '<div style="background:#131c2e;border:1px solid #243049;border-radius:16px;overflow:hidden;'
     'font-family:Inter,system-ui,Arial,sans-serif;color:#f1f5f9;">'
     '<div style="padding:18px 20px 14px;border-bottom:1px solid #1c2740;">'
     '<div style="font-size:10.5px;font-weight:700;letter-spacing:.09em;color:#8595ac;text-transform:uppercase;">Performance Measure</div>'
     f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-top:9px;">'
     f'<h3 style="margin:0;font-size:17px;font-weight:700;line-height:1.25;">{title}</h3>{accel_html}</div></div>'
     f'<div style="display:grid;place-items:center;padding:30px 0 34px;">'
     f'<div style="width:150px;height:150px;border-radius:50%;background:conic-gradient({c} calc({p}*1%), #26324a 0);display:grid;place-items:center;">'
     f'<div style="width:118px;height:118px;border-radius:50%;background:#131c2e;display:flex;flex-direction:column;align-items:center;justify-content:center;">'
     f'<div style="font-size:27px;font-weight:800;">{{{{{av}_attain}}}}%</div>'
     '<div style="font-size:9.5px;font-weight:700;letter-spacing:.11em;color:#64748b;">QTD ATTAIN</div></div></div></div>'
     '<div style="padding:6px 20px 16px;">'
     + _stat("Qtr YTD Quota", "{{%s_qquota}}" % av)
     + _stat("Qtr YTD Credits", "{{%s_qcredits}}" % av, "#5cc7f0")
     + _stat("Annual Quota", "{{%s_aquota}}" % av)
     + _stat("Annual Attainment", "{{%s_aattain}}" % av, "#38bdf8")
     + '</div></div>')

def payout_html(av):
    # separate payout card (own view seller_payout_<m>), stacked under its measure ring card
    return (
     '<div style="background:#131c2e;border:1px solid #243049;border-radius:16px;padding:16px 20px;'
     'font-family:Inter,system-ui,Arial,sans-serif;color:#f1f5f9;display:flex;justify-content:space-between;align-items:center;">'
     '<div><div style="font-size:10px;font-weight:700;letter-spacing:.09em;color:#64748b;text-transform:uppercase;">Calculated Payout</div>'
     f'<div style="font-size:22px;font-weight:800;color:#34d399;margin-top:3px;">{{{{{av}_calc}}}}</div></div>'
     f'<div style="font-size:12px;color:#93a3b8;text-align:right;line-height:1.8;">Released: <b style="color:#34d399;">{{{{{av}_rel}}}}</b><br>'
     f'Pending: <b style="color:#f5b544;">{{{{{av}_pend}}}}</b></div></div>')

def kpi_card(label, value_html, sub_html):
    # white tile, blue lettering (each KPI is its own separate Custom component)
    return ('<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:18px 20px;'
            'display:flex;flex-direction:column;gap:7px;font-family:Inter,system-ui,Arial,sans-serif;">'
            f'<div style="font-size:10.5px;font-weight:700;letter-spacing:.09em;color:#0079c1;text-transform:uppercase;">{label}</div>'
            f'<div style="font-size:27px;font-weight:800;letter-spacing:-.02em;line-height:1;color:#003087;">{value_html}</div>'
            f'<div style="font-size:12px;color:#0079c1;">{sub_html}</div></div>')

def kpi_attain_card():
    return ('<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:18px 20px;'
            'display:flex;flex-direction:column;gap:7px;font-family:Inter,system-ui,Arial,sans-serif;">'
            '<div style="font-size:10.5px;font-weight:700;letter-spacing:.09em;color:#0079c1;text-transform:uppercase;">Overall QTD Attainment</div>'
            '<div style="display:flex;align-items:center;gap:8px;"><div style="font-size:27px;font-weight:800;color:#003087;line-height:1;">{{v_kpi_attain}}</div>'
            '<span style="font-size:10.5px;font-weight:700;padding:3px 8px;border-radius:5px;background:#e6f0fa;color:#003087;">{{v_kpi_target == \'Yes\' ? \'Target Met\' : \'Below Target\'}}</span></div>'
            '<div style="height:5px;border-radius:99px;background:#e2e8f0;overflow:hidden;margin-top:2px;"><i style="display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#0079c1,#003087);width:{{v_kpi_bar}}%;"></i></div></div>')

def measure_card(title, color, credits_var, qquota, qattain, aquota, aattain):
    return (f'<div style="height:330px;padding:24px;font-family:Poppins,Arial,sans-serif;background:#fff;'
            f'border:1px solid #eef2f6;border-top:4px solid {color};border-radius:20px;box-shadow:0 10px 25px rgba(0,48,135,.05);display:flex;flex-direction:column;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">'
            f'<h3 style="margin:0;font-size:15px;font-weight:800;color:#0f172a;">{title}</h3>'
            f'<span style="padding:3px 8px;font-size:10px;font-weight:bold;color:{color};background:{color}18;border-radius:5px;text-transform:uppercase;">Measure</span></div>'
            f'<div style="padding:12px 14px;background:#f8fafc;border:1px solid #f1f5f9;border-radius:12px;margin-bottom:16px;">'
            f'<div style="font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;">Qtr YTD Credits</div>'
            f'<div style="font-size:24px;font-weight:800;color:{color};">{{{{{credits_var}}}}}</div></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px;"><span style="color:#64748b;">Qtr Quota</span><span style="font-weight:bold;color:#334155;">{{{{{qquota}}}}}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:14px;"><span style="color:#64748b;">Qtr Attainment</span><span style="font-weight:800;color:{color};">{{{{{qattain}}}}}</span></div>'
            f'<div style="border-top:1px solid #f1f5f9;padding-top:12px;">'
            f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px;"><span style="color:#64748b;">Annual Quota</span><span style="font-weight:bold;color:#334155;">{{{{{aquota}}}}}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:13px;"><span style="color:#64748b;">Annual Attainment</span><span style="font-weight:800;color:{color};">{{{{{aattain}}}}}</span></div></div></div>')

def payout_card(title, color, pct, calc, rel, pend):
    return (f'<div style="height:270px;padding:22px;font-family:Poppins,Arial,sans-serif;background:#fff;border:1px solid #eef2f6;border-top:4px solid {color};border-radius:20px;box-shadow:0 10px 25px rgba(0,48,135,.05);display:flex;flex-direction:column;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;"><h3 style="margin:0;font-size:13px;font-weight:800;color:#0f172a;">{title}</h3>'
            f'<span style="padding:3px 8px;font-size:10px;font-weight:bold;color:{color};background:{color}18;border-radius:5px;text-transform:uppercase;">Payout</span></div>'
            f'<div style="display:flex;justify-content:space-between;padding-bottom:10px;border-bottom:1px solid #f1f5f9;margin-bottom:12px;"><span style="font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;">Payout %</span><span style="font-size:18px;font-weight:800;color:{color};">{{{{{pct}}}}}</span></div>'
            f'<div style="font-size:10px;font-weight:bold;color:#94a3b8;text-transform:uppercase;">Calculated Payout</div>'
            f'<div style="font-size:26px;font-weight:800;color:{color};margin-bottom:16px;">{{{{{calc}}}}}</div>'
            f'<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:8px;"><span style="color:#64748b;">Released</span><span style="font-weight:800;color:#16a34a;">{{{{{rel}}}}}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:13px;"><span style="color:#64748b;">Pending</span><span style="font-weight:800;color:#d97706;">{{{{{pend}}}}}</span></div></div>')

C = []  # control list
# ---- init chain / loader — hide ONCE THE PERIOD FILTER IS LOADED (current_period_select),
#      an early channel that always fires on load; NOT the deep master_position_id (may never complete). ----
C += [
 {"kind":"pageloader","title":"Loading...","onload":["showLoader"],"subscribes":[["current_period_select",["hideLoader"]]]},
 {"kind":"vc","title":"Session Id VC","ds":"seller_session_id","schema":"demo","valueField":"session_id","var":"v_session_id","produces":"e_session_id"},
 {"kind":"vc","title":"Refresh Date VC","ds":"seller_refresh_date","schema":"demo","valueField":"refresh_date","var":"v_refresh_date","produces":"e_refresh_date"},
 {"kind":"vc","title":"Year Number VC","ds":"seller_current_year","schema":"demo","valueField":"year_number","var":"v_year_number","produces":"year_number_vc","subscribes":[["e_refresh_date",["refresh"]]]},
 {"kind":"vc","title":"Year Name VC","ds":"seller_current_year","schema":"demo","valueField":"year_name","var":"v_year_name","produces":"year_name_vc","subscribes":[["year_number_vc",["refresh"]]]},
 # period filter — fires on load; the loader hides on its channel
 {"kind":"vc","title":"Current Period VC","ds":"incnt_stmt_current_period","schema":"demo","valueField":"current_period_id","var":"v_current_period_id","produces":"current_period_select","subscribes":[["year_name_vc",["refresh"]]]},
]
# ---- header ----
C += [{"kind":"card","title":"Header","internalName":"Header - Seller Dashboard","layoutSize":100,
       "html":'<div style="padding:28px 36px;font-family:Poppins,Arial,sans-serif;background:#fff;border-bottom:2px solid #f2f5f7;border-radius:16px 16px 0 0;"><span style="font-size:12px;font-weight:bold;color:#003087;text-transform:uppercase;">PayPal Merchant Network</span> <span style="padding:2px 8px;font-size:11px;color:#475569;background:#f1f5f9;border-radius:4px;">Refreshed: {{v_refresh_date}}</span><h1 style="margin:2px 0 0;font-size:26px;font-weight:bold;color:#003087;">Seller Dashboard</h1></div>',
       "bound":[["v_refresh_date","refresh_date"]],"ds":"seller_refresh_date","schema":"demo","subscribes":[["e_refresh_date",["refresh"]]]}]
# ---- top KPI tiles: 4 SEPARATE Custom components (white tiles, blue text) ----
_ksub = [["master_participant_id",["refresh"]],["master_position_id",["refresh"]],["quarter_select",["refresh"]]]
C += [
 {"kind":"card","title":"Total QTD Credits","internalName":"KPI - Credits","layoutSize":25,"ds":"seller_summary_kpis","schema":"demo",
  "html":kpi_card("Total QTD Credits Earned","{{v_kpi_credits}}","Total Quota: <b style=\"color:#003087;font-weight:700;\">{{v_kpi_quota}}</b>"),
  "bound":[["v_kpi_credits","total_qtd_credits"],["v_kpi_quota","total_quota"]],"subscribes":_ksub},
 {"kind":"card","title":"Overall Attainment","internalName":"KPI - Attainment","layoutSize":25,"ds":"seller_summary_kpis","schema":"demo",
  "html":kpi_attain_card(),
  "bound":[["v_kpi_attain","overall_qtd_attainment"],["v_kpi_bar","attain_bar_pct"],["v_kpi_target","target_met_flag"]],"subscribes":_ksub},
 {"kind":"card","title":"Estimated Commission","internalName":"KPI - Commission","layoutSize":25,"ds":"seller_summary_kpis","schema":"demo",
  "html":kpi_card("Total Estimated Commission","{{v_kpi_comm}}","Released: <b style=\"color:#003087;font-weight:700;\">{{v_kpi_released}}</b>"),
  "bound":[["v_kpi_comm","total_commission"],["v_kpi_released","released_commission"]],"subscribes":_ksub},
 {"kind":"card","title":"Pending Payout","internalName":"KPI - Pending","layoutSize":25,"ds":"seller_summary_kpis","schema":"demo",
  "html":kpi_card("Pending Payout Balance","{{v_kpi_pending}}","Verification in progress"),
  "bound":[["v_kpi_pending","pending_payout"]],"subscribes":_ksub},
]
# ---- filters (rep incl IC/Mgr/Leader, manager, quarter, NEW measure + granularity) ----
C += [
 {"kind":"dropdown","title":"Seller Representative","ds":"seller_representative_list","schema":"demo","valueField":"rep_name","displayField":"rep_name","var":"v_participant","produces":"rep_select","layoutSize":25,"subscribes":[["defaultparticipant",["assignCurrentVariable","refresh"]]]},
 {"kind":"vc","title":"Default Participant VC","ds":"seller_representative_list","schema":"demo","valueField":"rep_name","var":"v_default_participant","produces":"defaultparticipant","subscribes":[["year_name_vc",["refresh"]]]},
 {"kind":"dropdown","title":"Sales Director / Manager","ds":"seller_manager_list","schema":"demo","valueField":"manager_name","displayField":"manager_name","var":"v_manager","produces":"manager_select","layoutSize":25,"subscribes":[["master_participant_id",["refresh"]]]},
 {"kind":"dropdown","title":"Fiscal Quarter","ds":"seller_fiscal_quarter_list","schema":"demo","valueField":"name","displayField":"name","var":"v_quarter","produces":"quarter_select","layoutSize":16.66,"subscribes":[["year_number_vc",["refresh"]]]},
 # NEW (comment 4/5): measure selector
 {"kind":"dropdown","title":"Performance Measure","ds":"seller_measure_list","schema":"demo","valueField":"measure_name","displayField":"measure_name","var":"v_measure","produces":"measure_select","layoutSize":16.66},
 # NEW (comment 5): quarter/monthly granularity toggle
 {"kind":"dropdown","title":"View","ds":"seller_granularity_list","schema":"demo","valueField":"granularity","displayField":"granularity","var":"v_granularity","produces":"granularity_select","layoutSize":16.66},
 {"kind":"button","title":"Download Statement","produces":"e_download","layoutSize":16.66,"buttonColorType":"link"},
 {"kind":"export","title":"Export As PDF","subscribes":[["e_download",["exportAsPDF"]]]},
]
# ---- id chain + NEW role VC ----
C += [
 {"kind":"vc","title":"Master Participant ID VC","ds":"seller_master_participant_id","schema":"demo","valueField":"master_participant_id","var":"v_master_participant_id","produces":"master_participant_id","subscribes":[["defaultparticipant",["refresh"]],["rep_select",["refresh"]]]},
 {"kind":"vc","title":"Master Position ID VC","ds":"seller_master_position_id","schema":"demo","valueField":"master_position_id","var":"v_master_position_id","produces":"master_position_id","subscribes":[["master_participant_id",["refresh"]]]},
 # NEW (comment 2): role of selected user -> gates the team section
 {"kind":"vc","title":"Role VC","ds":"seller_participant_role","schema":"demo","valueField":"role","var":"v_role","produces":"role_select","subscribes":[["rep_select",["refresh"]]]},
]
# ---- measure RING cards (row 1) + payout cards (row 2), separate views, stacked per column ----
_msub = [["master_position_id",["refresh"]],["quarter_select",["refresh"]],["granularity_select",["refresh"]]]
_psub = [["master_participant_id",["refresh"]],["quarter_select",["refresh"]]]
_mbound = lambda av: [[f"{av}_attain","qtd_attainment_pct"],[f"{av}_qquota","qtd_quota"],[f"{av}_qcredits","qtd_credits"],[f"{av}_aquota","annual_quota"],[f"{av}_aattain","annual_attainment_pct"]]
_pbound = lambda av: [[f"{av}_calc","calculated_payout"],[f"{av}_rel","released_amount"],[f"{av}_pend","pending_amount"]]
# row 1: measure ring cards
C += [
 {"kind":"card","title":"Revenue","internalName":"Measure - Revenue","layoutSize":33.33,"ds":"seller_measure_revenue","schema":"demo","html":ring_html("Revenue","1.25x Accelerator","v_rev"),"bound":_mbound("v_rev"),"subscribes":_msub},
 {"kind":"card","title":"Profitability","internalName":"Measure - Sales Profitability","layoutSize":33.33,"ds":"seller_measure_sales_profitability","schema":"demo","html":ring_html("Profitability","","v_sp"),"bound":_mbound("v_sp"),"subscribes":_msub},
 # comment 3: Branded Checkout must map credit type 'BXO TPV' (fix in seller_measure_branded_checkout view)
 {"kind":"card","title":"Branded Checkout TPV (BXO TPV)","internalName":"Measure - Branded Checkout (BXO TPV)","layoutSize":33.33,"ds":"seller_measure_branded_checkout","schema":"demo","html":ring_html("Branded Checkout TPV (BXO TPV)","1.25x Accelerator","v_bc"),"bound":_mbound("v_bc"),"subscribes":_msub},
]
# row 2: payout cards (separate views), aligned under their measure card
C += [
 {"kind":"card","title":"Revenue Payout","internalName":"Payout - Revenue","layoutSize":33.33,"ds":"seller_payout_revenue","schema":"demo","html":payout_html("v_prev"),"bound":_pbound("v_prev"),"subscribes":_psub},
 {"kind":"card","title":"Profitability Payout","internalName":"Payout - Sales Profitability","layoutSize":33.33,"ds":"seller_payout_sales_profitability","schema":"demo","html":payout_html("v_psp"),"bound":_pbound("v_psp"),"subscribes":_psub},
 {"kind":"card","title":"Branded Checkout Payout","internalName":"Payout - Branded Checkout (BXO TPV)","layoutSize":33.33,"ds":"seller_payout_branded_checkout","schema":"demo","html":payout_html("v_pbc"),"bound":_pbound("v_pbc"),"subscribes":_psub},
]
# ---- historical performance (measure-selectable chart, comment 4) ----
C += [
 {"kind":"card","title":"Historical Performance","internalName":"Header - Historical Performance","layoutSize":100,
  "html":'<div style="padding:24px 32px;font-family:Poppins,Arial,sans-serif;background:#fff;border-radius:16px 16px 0 0;"><h2 style="margin:0;font-size:18px;font-weight:700;color:#003087;">Historical Performance</h2><div style="font-size:12px;color:#64748b;">YTD Attainment Trend — {{v_year_name}} · Measure: {{v_measure}}</div></div>',
  "bound":[["v_year_name","year_name"]],"ds":"seller_current_year","schema":"demo","subscribes":[["measure_select",["refresh"]]]},
 {"kind":"chart","internalName":"Chart - Historical Attainment Trend","layoutSize":100,"ds":"seller_attainment_trend_monthly","schema":"demo",
  "chart":{"x":"month_name","ys":[{"key":"attainment_pct","label":"Attainment %","fill":"#3b82f6","type":"bar"},{"key":"accelerator_goal_pct","label":"Accelerator Goal","fill":"#d97706","type":"line"}]},
  "subscribes":[["master_position_id",["refresh"]],["measure_select",["refresh"]]]},
]
# ---- attainment & ledger matrix + deal ledger search ----
C += [
 {"kind":"card","title":"Attainment & Ledger Matrix","internalName":"Header - Attainment & Ledger Matrix","layoutSize":100,"html":'<div style="padding:16px 20px;font-family:Poppins,Arial,sans-serif;background:#fff;"><h2 style="margin:0;font-size:16px;font-weight:700;color:#1e293b;">Attainment &amp; Ledger Matrix</h2></div>'},
 {"kind":"table","internalName":"Table - Attainment & Ledger Matrix","layoutSize":100,"ds":"seller_attainment_ledger_matrix","schema":"demo",
  "columns":[{"field":"period_component","headerName":"Period / Component"},{"field":"paypal_core","headerName":"PayPal Core"},{"field":"braintree","headerName":"Braintree"},{"field":"qtd_total","headerName":"QTD Totals"}],
  "subscribes":[["master_participant_id",["refresh"]],["granularity_select",["refresh"]]]},
 {"kind":"card","title":"Deal Ledger Details","internalName":"Header - Deal Ledger Details","layoutSize":100,"html":'<div style="padding:20px 24px;font-family:Poppins,Arial,sans-serif;background:#fff;border-radius:16px 16px 0 0;"><h2 style="margin:0;font-size:16px;font-weight:700;color:#0f172a;">Deal Ledger Details</h2></div>'},
 {"kind":"input","title":"Search","internalName":"Input - Ledger Search","placeholder":"Search Opportunity, product, account id....","var":"v_ledger_search","produces":"ledger_search","layoutSize":100},
 {"kind":"table","internalName":"Table - Deal Ledger Details","layoutSize":100,"ds":"seller_deal_ledger","schema":"demo",
  "columns":[{"field":"opportunity_name","headerName":"Opportunity"},{"field":"rep_name","headerName":"Rep"},{"field":"product_family","headerName":"Product Family"},{"field":"actual_vol_ytd","headerName":"Actual Vol YTD"},{"field":"commission_date","headerName":"Commission Date"}],
  "subscribes":[["master_participant_id",["refresh"]],["ledger_search",["refresh"]]]},
]
# ---- NEW (comment 5): Portfolio Details + Incremental Details ----
C += [
 {"kind":"card","title":"Portfolio Details","internalName":"Header - Portfolio Details","layoutSize":100,"html":'<div style="padding:20px 24px;font-family:Poppins,Arial,sans-serif;background:#fff;border-radius:16px 16px 0 0;"><h2 style="margin:0;font-size:16px;font-weight:700;color:#0f172a;">Portfolio Details</h2><div style="font-size:12px;color:#64748b;">Measure: {{v_measure}} · View: {{v_granularity}}</div></div>',"bound":[["v_measure","measure_name"]],"ds":"seller_measure_list","schema":"demo","subscribes":[["measure_select",["refresh"]]]},
 {"kind":"input","title":"Search Portfolio","internalName":"Input - Portfolio Search","placeholder":"Search Account Name, Customer ID, BT ID...","var":"v_portfolio_search","produces":"portfolio_search","layoutSize":100},
 {"kind":"table","internalName":"Table - Portfolio Details","layoutSize":100,"ds":"seller_portfolio_details","schema":"demo",
  "columns":[{"field":"account_name","headerName":"Account Name"},{"field":"customer_id","headerName":"Customer ID"},{"field":"bt_id","headerName":"BT ID"},{"field":"measure_value","headerName":"Value"}],
  "subscribes":[["master_position_id",["refresh"]],["measure_select",["refresh"]],["granularity_select",["refresh"]],["portfolio_search",["refresh"]]]},
 {"kind":"card","title":"Incremental Details","internalName":"Header - Incremental Details","layoutSize":100,"html":'<div style="padding:20px 24px;font-family:Poppins,Arial,sans-serif;background:#fff;border-radius:16px 16px 0 0;"><h2 style="margin:0;font-size:16px;font-weight:700;color:#0f172a;">Incremental Details</h2></div>'},
 {"kind":"input","title":"Search Incremental","internalName":"Input - Incremental Search","placeholder":"Search Opportunity ID, Opportunity Name, Customer ID, BT ID...","var":"v_incremental_search","produces":"incremental_search","layoutSize":100},
 {"kind":"table","internalName":"Table - Incremental Details","layoutSize":100,"ds":"seller_incremental_details","schema":"demo",
  "columns":[{"field":"opportunity_id","headerName":"Opportunity ID"},{"field":"opportunity_name","headerName":"Opportunity Name"},{"field":"customer_id","headerName":"Customer ID"},{"field":"bt_id","headerName":"BT ID"},{"field":"measure_value","headerName":"Value"}],
  "subscribes":[["master_position_id",["refresh"]],["measure_select",["refresh"]],["granularity_select",["refresh"]],["incremental_search",["refresh"]]]},
]
# ---- NEW (comment 2): Manager/Leader team section, HIDDEN by default (role-gated) ----
C += [
 {"kind":"card","title":"Team Performance (Managers & Leaders)","internalName":"Header - Team Section","layoutSize":100,"hidden":True,"html":'<div style="padding:20px 24px;font-family:Poppins,Arial,sans-serif;background:#fff;border-radius:16px 16px 0 0;"><h2 style="margin:0;font-size:16px;font-weight:700;color:#003087;">Team Performance</h2><div style="font-size:12px;color:#64748b;">Visible for Managers & Leaders · Role: {{v_role}}</div></div>',"bound":[["v_role","role"]],"ds":"seller_participant_role","schema":"demo","subscribes":[["role_select",["refresh"]]]},
 {"kind":"table","internalName":"Table - Team Leaderboard","layoutSize":66.66,"hidden":True,"ds":"seller_team_leaderboard","schema":"demo",
  "columns":[{"field":"rep_name","headerName":"Rep"},{"field":"attainment_pct","headerName":"Attainment %"},{"field":"credits","headerName":"Credits"},{"field":"rank","headerName":"Rank"}],
  "subscribes":[["master_position_id",["refresh"]],["role_select",["refresh"]]]},
 {"kind":"card","title":"IC Contribution","internalName":"Card - IC Contribution to Team","layoutSize":33.33,"hidden":True,"ds":"seller_team_contribution","schema":"demo",
  "html":'<div style="height:260px;padding:22px;font-family:Poppins,Arial,sans-serif;background:#fff;border:1px solid #eef2f6;border-top:4px solid #003087;border-radius:20px;"><h3 style="margin:0;font-size:14px;font-weight:800;color:#0f172a;">IC Contribution to Team</h3><div style="font-size:32px;font-weight:800;color:#003087;margin-top:16px;">{{v_ic_contrib_pct}}</div><div style="font-size:12px;color:#64748b;">of overall team performance</div></div>',
  "bound":[["v_ic_contrib_pct","contribution_pct"]],"subscribes":[["master_position_id",["refresh"]],["role_select",["refresh"]]]},
]

shell = {"pageDefinitionId": PID, "title": "Seller Dashboard", "versionName": "v2"}
page = eb.build_page(C, shell)
gate = eb.validate_page(page, shell, catalog=st._CATALOG)
props = page["pageSchema"]["controlSchema"]["schema"]["properties"]
out = os.path.expanduser(f"~/Downloads/extend-llm/out_app/seller_redesign/app/{PID}.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(page, open(out,"w"), indent=2)
print("controls built:", len(props))
print("VERDICT:", gate["verdict"], "| errors:", len(gate["errors"]), "| warnings:", len(gate["warnings"]))
for e in gate["errors"][:12]: print("  ERR", e["category"], e["problem"][:80])
# summarize new-vs-existing view warnings
unknown = sorted({w["note"].split("'")[1] for w in gate["warnings"] if "not in the catalog" in w["note"]})
print("NEW views to create (", len(unknown), "):", unknown)
print("saved:", out)
