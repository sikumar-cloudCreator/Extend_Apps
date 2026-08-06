CREATE VIEW demo.seller_summary_kpis AS
SELECT
  Nvl(FormatNumber(cr.qtd_credits, '#,##0.00'), '0.00') AS total_qtd_credits,
  Nvl(FormatNumber(qt.total_quota, '#,##0.00'), '0.00') AS total_quota,
  CASE WHEN Nvl(qt.total_quota, 0) > 0
       THEN Concat(FormatNumber((Nvl(cr.qtd_credits, 0) / qt.total_quota) * 100, '#,##0.00'), '%')
       ELSE '—' END AS overall_qtd_attainment,
  CASE WHEN Nvl(qt.total_quota, 0) > 0
       THEN CASE WHEN (Nvl(cr.qtd_credits, 0) / qt.total_quota) * 100 > 100 THEN 100
                 WHEN (Nvl(cr.qtd_credits, 0) / qt.total_quota) * 100 < 0 THEN 0
                 ELSE (Nvl(cr.qtd_credits, 0) / qt.total_quota) * 100 END
       ELSE 0 END AS attain_bar_pct,
  CASE WHEN Nvl(qt.total_quota, 0) > 0
        AND (Nvl(cr.qtd_credits, 0) / qt.total_quota) * 100 >= 100
       THEN 'Yes' ELSE 'No' END AS target_met_flag,
  Nvl(FormatNumber(cm.total_commission, '#,##0.00'), '0.00') AS total_commission,
  Nvl(FormatNumber(pm.released_commission, '#,##0.00'), '0.00') AS released_commission,
  Nvl(FormatNumber(pm.pending_payout, '#,##0.00'), '0.00') AS pending_payout
FROM
  (SELECT SUM(c.amount) AS qtd_credits
     FROM xactly.xc_credit c
    WHERE c.period_id = :v_period
      AND c.eff_participant_id = :v_master_participant_id
      AND c.position_id = :v_master_position_id) cr,
  (SELECT SUM(q.quota_value) AS total_quota
     FROM xactly.xc_quota q
    WHERE q.quota_period_id = :v_period) qt,
  (SELECT SUM(cm2.amount) AS total_commission
     FROM xactly.xc_commission cm2
    WHERE cm2.period_id = :v_period
      AND cm2.eff_participant_id = :v_master_participant_id
      AND cm2.position_id = :v_master_position_id) cm,
  (SELECT SUM(p.amount) AS released_commission,
          SUM(CASE WHEN p.is_held = '1' THEN p.amount ELSE 0 END) AS pending_payout
     FROM xactly.xc_payment p
    WHERE p.period_id = :v_period
      AND p.eff_participant_id = :v_master_participant_id
      AND p.position_id = :v_master_position_id) pm
