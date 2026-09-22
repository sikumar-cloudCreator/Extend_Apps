-- incnt_stmt_active_participant_list_admin_view
-- variables: v_period=MAR-2025 (String)
CREATE VIEW exincst.incnt_stmt_active_participant_list_admin_view AS
select pa.name from xactly.xc_participant pa 
inner join 
xactly.xc_period p 
on pa.effective_start_date < p.end_date 
and pa.effective_end_date > p.start_date
where p.name = :v_period
order by pa.name asc;

-- incnt_stmt_actual_payment_upload_date_format
-- variables: v_period=SEP-2026 (String)
CREATE VIEW exincst.incnt_stmt_actual_payment_upload_date_format AS
select FormatDateTime(start_date,'YYYYMM') as formatted_date from xactly.xc_period where name =:v_period;

-- incnt_stmt_current_period
CREATE VIEW exincst.incnt_stmt_current_period AS
select period_id as current_period_id from xactly.xc_period per where name = :v_period;

-- incnt_stmt_default_participant
-- variables: v_period=DEC-2025 (String)
CREATE VIEW exincst.incnt_stmt_default_participant AS
select  part.name from xactly.xc_participant part
	 join xactly.xc_part_user_assignment pua on part.participant_id = pua.participant_id
     join xactly.xc_user u on pua.user_id = u.user_id
     join xactly.xc_pos_part_assignment ppa on part.participant_id = ppa.participant_id
     join xactly.xc_position pos on ppa.position_id = pos.position_id
where pos.effective_start_date <= (select end_date from xactly.xc_period where name = :v_period) and pos.effective_end_date >= (select start_date from xactly.xc_period where name = :v_period) 
and xc_user.email = CurrentUserEmail();

-- incnt_stmt_earnings_by_group
CREATE VIEW exincst.incnt_stmt_earnings_by_group AS
SELECT
      eg.name AS earning_group,
      Nvl(FormatNumber(SUM(cm.amount), '#,##0.00'), '0.00') AS eg_py,
      
      -- Changed ELSE NULL to ELSE '0.00'
      CASE WHEN MAX(Month(curr.start_date)) >= 1  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 1  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_jan,
      CASE WHEN MAX(Month(curr.start_date)) >= 2  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 2  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_feb,
      CASE WHEN MAX(Month(curr.start_date)) >= 3  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 3  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_mar,
      CASE WHEN MAX(Month(curr.start_date)) >= 4  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 4  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_apr,
      CASE WHEN MAX(Month(curr.start_date)) >= 5  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 5  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_may,
      CASE WHEN MAX(Month(curr.start_date)) >= 6  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 6  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_jun,
      CASE WHEN MAX(Month(curr.start_date)) >= 7  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 7  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_jul,
      CASE WHEN MAX(Month(curr.start_date)) >= 8  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 8  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_aug,
      CASE WHEN MAX(Month(curr.start_date)) >= 9  THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 9  THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_sep,
      CASE WHEN MAX(Month(curr.start_date)) >= 10 THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 10 THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_oct,
      CASE WHEN MAX(Month(curr.start_date)) >= 11 THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 11 THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_nov,
      CASE WHEN MAX(Month(curr.start_date)) >= 12 THEN Nvl(FormatNumber(SUM(CASE WHEN Month(per.start_date) = 12 THEN cm.amount ELSE 0 END), '#,##0.00'), '0.00') ELSE '0.00' END AS eg_dec
      
  FROM xactly.xc_participant master_part
  JOIN xactly.xc_period curr ON 1=1
  JOIN xactly.xc_commission cm ON cm.participant_id = master_part.participant_id
  JOIN xactly.xc_period per
      ON per.period_id          = cm.period_id
     AND per.end_date          <= curr.end_date
     AND Year(per.start_date)   = Year(curr.start_date)
  JOIN xactly.xc_earning_group eg ON eg.earning_group_id = cm.earning_group_id
  
  WHERE master_part.participant_id = :v_master_participant_id
    AND master_part.is_master      = 1
    AND curr.name                  = :v_period
    AND (:v_master_position_id IS NULL OR cm.position_id = :v_master_position_id)
    and eg.name in ('CNS Deal Award - SaaS',
'CNS SPIFF - Security',
'CNS SPIFF - CCS',
'CNS SPIFF - NaC',
'CNS Special Incentive',
'NI Growth Booster',
'Holiday Pay',
'100% of PITA',
'NI SPIFF - Infinera',
'Negative Balance',
'Payment Adjustment',
'Payment Hold',
'Recoverable Draw',
'Non-Recoverable Draw',
'NI Q1 Fast Start')
    
  GROUP BY eg.name
  ORDER BY eg.name;

-- incnt_stmt_individual_months_ytd
-- variables: v_current_period_id=219904071958242 (String), v_participant=Xun Cao (61236471) (String), v_target_actuals_indicator=CNY (String), v_target_payment_currency=EUR (String), v_year_number=2025 (String)
CREATE VIEW exincst.incnt_stmt_individual_months_ytd AS
SELECT 
    1 AS type, 
    'Original Payment' as Payment_Name,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('JAN-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS jan,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('FEB-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS feb,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('MAR-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS mar,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('APR-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS apr,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('MAY-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS may,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('JUN-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS jun,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('JUL-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS jul,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('AUG-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS aug,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('SEP-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS sep,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('OCT-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS oct,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('NOV-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS nov,
    Nvl(FormatNumber(SUM(CASE WHEN p.name LIKE Concat('DEC-', :v_year_number) THEN pay.amount ELSE 0 END), '#,##0.00'), '0.00') AS dec,
    Nvl(FormatNumber(SUM(Nvl(pay.amount, 0)), '#,##0.00'), '0.00') AS ytd_total,
    MAX(LookupUnitTypeNameById(pay.amount_unit_type_id)) AS Payment_currency
FROM xactly.xc_payment pay
INNER JOIN xactly.xc_period p ON p.name = pay.period_name
WHERE pay.participant_name = :v_participant
  AND p.name LIKE Concat('%-', :v_year_number)
  AND p.end_date <= (SELECT end_date FROM xactly.xc_period WHERE period_id = :v_current_period_id)

UNION  

SELECT 
    2 AS type, 
    'Actual Payment' AS  Payment_Name,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('JAN-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS jan,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('FEB-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS feb,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('MAR-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS mar,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('APR-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS apr,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('MAY-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS may,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('JUN-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS jun,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('JUL-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS jul,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('AUG-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS aug,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('SEP-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS sep,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('OCT-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS oct,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('NOV-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS nov,
    Nvl(FormatNumber(SUM(CASE WHEN pay.period_name LIKE Concat('DEC-', :v_year_number) THEN pay.amount_paid ELSE 0 END), '#,##0.00'), '0.00') AS dec,
    Nvl(FormatNumber(SUM(Nvl(pay.amount, 0)), '#,##0.00'), '0.00') AS ytd_total,
    pay.currency_code AS Payment_currency
FROM exincst.incnt_stmt_actual_payment_ftp pay
WHERE pay.participant_name = :v_participant
  AND pay.period_name LIKE Concat('%-', :v_year_number)
UNION ALL

SELECT 
    3 AS type, 
    '' AS Payment_Name,
    '0.00' AS jan,
    '0.00' AS feb,
    '0.00' AS mar,
    '0.00' AS apr,
    '0.00' AS may,
    '0.00' AS jun,
    '0.00' AS jul,
    '0.00' AS aug,
    '0.00' AS sep,
    '0.00' AS oct,
    '0.00' AS nov,
    '0.00' AS `dec`,
    '0.00' AS ytd_total,
    '0.00' AS Payment_currency
FROM Empty() 
ORDER BY 1 
LIMIT 2;

-- incnt_stmt_job_family
-- variables: v_participant=Xun Cao (61236471) (String), v_period=DEC-2025 (String)
CREATE VIEW exincst.incnt_stmt_job_family AS
select job_family  from xactly.xc_participant  where participant_id=:v_master_participant_id;

-- incnt_stmt_kpi_credits_by_measure
-- variables: v_master_position_id=219907528482333 (String), v_period=APR-2025 (String), v_year_number=2025 (String)
CREATE VIEW exincst.incnt_stmt_kpi_credits_by_measure AS
SELECT
    q.name AS kpi_metric,
    Nvl(FormatNumber(tg.tgt, '#,##0.00'), '0.00') AS kpi_quota,
    Nvl(FormatNumber(Nvl(b.cred_ytd, 0), '#,##0.00'), '0.00') AS kpi_py,
    Nvl(FormatNumber(Nvl(b.jan, 0), '#,##0.00'), '0.00') AS kpi_jan,
    Nvl(FormatNumber(Nvl(b.feb, 0), '#,##0.00'), '0.00') AS kpi_feb,
    Nvl(FormatNumber(Nvl(b.mar, 0), '#,##0.00'), '0.00') AS kpi_mar,
    Nvl(FormatNumber(Nvl(b.apr, 0), '#,##0.00'), '0.00') AS kpi_apr,
    Nvl(FormatNumber(Nvl(b.may, 0), '#,##0.00'), '0.00') AS kpi_may,
    Nvl(FormatNumber(Nvl(b.jun, 0), '#,##0.00'), '0.00') AS kpi_jun,
    Nvl(FormatNumber(Nvl(b.jul, 0), '#,##0.00'), '0.00') AS kpi_jul,
    Nvl(FormatNumber(Nvl(b.aug, 0), '#,##0.00'), '0.00') AS kpi_aug,
    Nvl(FormatNumber(Nvl(b.sep, 0), '#,##0.00'), '0.00') AS kpi_sep,
    Nvl(FormatNumber(Nvl(b.oct, 0), '#,##0.00'), '0.00') AS kpi_oct,
    Nvl(FormatNumber(Nvl(b.nov, 0), '#,##0.00'), '0.00') AS kpi_nov,
    Nvl(FormatNumber(Nvl(b.dec, 0), '#,##0.00'), '0.00') AS kpi_dec
FROM (
    SELECT qa.quota_id, Max(qa.amount) AS tgt
    FROM xactly.xc_quota_assignment qa
    JOIN xactly.xc_period yp ON yp.period_id = qa.period_id
    WHERE qa.assignment_id = :v_master_position_id
      AND yp.name LIKE Concat('%-', :v_year_number)
    GROUP BY qa.quota_id
) tg
JOIN xactly.xc_quota q ON q.quota_id = tg.quota_id
LEFT JOIN (
    SELECT
        cq.quota_id,
        SUM(cr.amount) AS cred_ytd,
        SUM(CASE WHEN ps.name LIKE Concat('JAN-', :v_year_number) THEN cr.amount ELSE 0 END) AS jan,
        SUM(CASE WHEN ps.name LIKE Concat('FEB-', :v_year_number) THEN cr.amount ELSE 0 END) AS feb,
        SUM(CASE WHEN ps.name LIKE Concat('MAR-', :v_year_number) THEN cr.amount ELSE 0 END) AS mar,
        SUM(CASE WHEN ps.name LIKE Concat('APR-', :v_year_number) THEN cr.amount ELSE 0 END) AS apr,
        SUM(CASE WHEN ps.name LIKE Concat('MAY-', :v_year_number) THEN cr.amount ELSE 0 END) AS may,
        SUM(CASE WHEN ps.name LIKE Concat('JUN-', :v_year_number) THEN cr.amount ELSE 0 END) AS jun,
        SUM(CASE WHEN ps.name LIKE Concat('JUL-', :v_year_number) THEN cr.amount ELSE 0 END) AS jul,
        SUM(CASE WHEN ps.name LIKE Concat('AUG-', :v_year_number) THEN cr.amount ELSE 0 END) AS aug,
        SUM(CASE WHEN ps.name LIKE Concat('SEP-', :v_year_number) THEN cr.amount ELSE 0 END) AS sep,
        SUM(CASE WHEN ps.name LIKE Concat('OCT-', :v_year_number) THEN cr.amount ELSE 0 END) AS oct,
        SUM(CASE WHEN ps.name LIKE Concat('NOV-', :v_year_number) THEN cr.amount ELSE 0 END) AS nov,
        SUM(CASE WHEN ps.name LIKE Concat('DEC-', :v_year_number) THEN cr.amount ELSE 0 END) AS dec
    FROM (
        SELECT DISTINCT cm.quota_id, cm.credit_id
        FROM xactly.xc_commission cm
        WHERE cm.position_id = :v_master_position_id
    ) cq
    JOIN xactly.xc_credit cr ON cr.credit_id = cq.credit_id
    JOIN (
        SELECT period_id, name FROM xactly.xc_period
        WHERE name LIKE Concat('%-', :v_year_number)
          AND end_date <= ( SELECT end_date FROM xactly.xc_period WHERE name = :v_period )
    ) ps ON ps.period_id = cr.period_id
    GROUP BY cq.quota_id
) b ON b.quota_id = tg.quota_id
ORDER BY q.name;

-- incnt_stmt_manager_name
-- variables: v_master_participant_id=219903990060522 (String), v_master_position_id=219913421947169 (String), v_month_start_date=2025-04-01 (Date)
CREATE VIEW exincst.incnt_stmt_manager_name AS
select 1 as type,Nvl(ppa.participant_name,'No Manager') AS manager_name from xactly.xc_pos_hierarchy ph inner join xactly.xc_pos_hierarchy_type pht
on ph.pos_hierarchy_type_id = pht.pos_hierarchy_type_id
inner join xactly.xc_position pos on
pos.master_position_id = ph.from_pos_id
inner join xactly.xc_pos_part_assignment ppa
on ppa.position_id = pos.position_id
where :v_month_start_date between pht.effective_start_date and pht.effective_end_date
and :v_month_start_date between pos.effective_start_date and pos.effective_end_date
and to_pos_id = :v_master_position_id
union 
select 2 as type, 'No Manager' as manager_name from Empty() order by type limit 1;

-- incnt_stmt_month_start_date
CREATE VIEW exincst.incnt_stmt_month_start_date AS
select per.start_date as month_start_date from xactly.xc_period per where per.period_id = :v_current_period_id;

-- incnt_stmt_monthly_period_list_till_curr_month
CREATE VIEW exincst.incnt_stmt_monthly_period_list_till_curr_month AS
select p.name from xactly.xc_period p 
inner join xactly.xc_period_type pt 
on p.period_type_id_fk = pt.period_type_id
and pt.name = 'MONTHLY'
and p.period_id <= (select per.period_id from xactly.xc_period per 
					inner join  xactly.xc_period_type pt 
					on per.period_type_id_fk = pt.period_type_id
					and pt.name = 'MONTHLY'
					where CurDate() between per.start_date And per.end_date
                   )
and p.name not in ('SOT','EOT')
order by p.period_id desc;

-- incnt_stmt_ordertype_values_totalyear
CREATE VIEW exincst.incnt_stmt_ordertype_values_totalyear AS
SELECT 
    ot.name, Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('%-',:v_year_number) THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_ytd,
          Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('JAN-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_jan,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('FEB-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_feb,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('MAR-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_mar,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('APR-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_apr,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('MAY-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_may,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('JUN-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_jun,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('JUL-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_jul,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('AUG-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_aug,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('SEP-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_sep,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('OCT-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_oct,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('NOV-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_nov,                                                        
      Nvl(FormatNumber(SUM(CASE WHEN op.name LIKE Concat('DEC-', :v_year_number)        THEN o.amount ELSE 0 END), '#,##0.00'), '0.00') AS act_oi_dec
FROM xactly.xc_order_stage o 
JOIN xactly.xc_order_type ot ON o.order_type_id = ot.order_type_id 
JOIN xactly.xc_period op ON o.period_id = op.period_id 
JOIN xactly.xc_order_stage_asgnmt osa ON osa.order_stage_id = o.order_stage_id
WHERE 
   osa.participant_id = :v_master_participant_id
    AND ot.name NOT LIKE '%Trigger%' and ot.name not in ('CNS Deal Award - SaaS',
'CNS SPIFF - Security',
'CNS SPIFF - CCS',
'CNS SPIFF - NaC',
'CNS Special Incentive',
'NI Growth Booster',
'Holiday Pay',
'100% of PITA',
'NI SPIFF - Infinera',
'Negative Balance',
'Payment Adjustment',
'Payment Hold',
'Recoverable Draw',
'Non-Recoverable Draw',
'NI Q1 Fast Start')
    AND op.start_date <= (SELECT start_date FROM xactly.xc_period WHERE period_id = :v_current_period_id)
GROUP BY 
    ot.name;

-- incnt_stmt_overall_controlled_score_tile
-- variables: v_master_participant_id=219903990063372 (String), v_period=NOV-2025 (String), v_year_number=2025 (String)
CREATE VIEW exincst.incnt_stmt_overall_controlled_score_tile AS
SELECT
      Concat(Replace(Replace(ct.name,' - Weighting',''),' - Score',''),' (%)')                                  AS credit_type,
      Nvl(FormatNumber(MAX(CASE WHEN ct.name LIKE '%Weighting'
                                 AND p.end_date <= curr.end_date
                            THEN c.amount END),'#,##0.00'),'0.00') AS weighting,

      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('JAN-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS jan,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('FEB-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS feb,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('MAR-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS mar,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('APR-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS apr,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('MAY-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS may,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('JUN-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS jun,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('JUL-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS jul,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('AUG-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS aug,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('SEP-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS sep,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('OCT-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS oct,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('NOV-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS nov,
      Nvl(FormatNumber(MAX(CASE WHEN (ct.name LIKE '%Score' OR ct.name='OCS') AND p.name LIKE Concat('DEC-',:v_year_number) AND p.end_date <= curr.end_date THEN c.amount END),'#,##0.00'),'0.00') AS dec
  FROM xactly.xc_credit c
  JOIN xactly.xc_credit_type ct ON ct.credit_type_id = c.credit_type_id
  JOIN xactly.xc_period      p  ON p.period_id = c.period_id
                                AND p.name LIKE Concat('%-', :v_year_number)
  JOIN xactly.xc_period      curr ON curr.name = :v_period
  WHERE c.participant_id = :v_master_participant_id
    AND (ct.name LIKE '%Weighting' OR ct.name LIKE '%Score' OR ct.name = 'OCS')
  GROUP BY Replace(Replace(ct.name,' - Weighting',''),' - Score','')
  ORDER BY credit_type;

-- incnt_stmt_personal_details_bggroup
-- variables: v_participant=A.S.M. Zakir Hossain (62092353) (String)
CREATE VIEW exincst.incnt_stmt_personal_details_bggroup AS
select bg.name as bggroup                                                                                                                                                                                                                                                    
  from xactly.xc_position pos
  join xactly.xc_period curr on 1=1                                                                                                                                                                                                                                            
  join xactly.xc_business_group bg                                                                                                                                                                                                                                             
      on bg.business_group_id = pos.business_group_id
  where pos.name = :v_position_name                                                                                                                                                                                                                        
    and curr.name = :v_period                                                                                                                                                                                                                                                  
    and pos.effective_start_date < curr.end_date
    and pos.effective_end_date > curr.start_date;

-- incnt_stmt_personal_details_current
-- variables: v_participant=A.S.M. Zakir Hossain (62092353) (String)
CREATE VIEW exincst.incnt_stmt_personal_details_current AS
select  pt.employee_id AS nokia_id
 FROM xactly.xc_participant pt
INNER JOIN (
    SELECT Max(version) AS max_version, employee_id,name
    FROM xactly.xc_participant
    WHERE name = :v_participant 
    GROUP BY employee_id
) latest
    ON  latest.employee_id = pt.employee_id
    AND latest.max_version = pt.version;

-- incnt_stmt_personal_details_incentive_dates
CREATE VIEW exincst.incnt_stmt_personal_details_incentive_dates AS
SELECT DISTINCT 
     FormatDateTime(pos.incent_st_date,'dd/MM/yyyy') as incent_st_date,
      Nvl(FormatDateTime(pos.incent_end_date,'dd/MM/yyyy'),'31/12/2025') AS incent_end_date
  FROM xactly.xc_position pos                                                                                                                                                                                                                       
  JOIN xactly.xc_period curr ON 1 = 1
  WHERE pos.name  = :v_position_name                                                                                                                                                                                           
    AND curr.name               = :v_period
    AND pos.effective_start_date < curr.end_date                                                                                                                                                                                                    
    AND pos.effective_end_date   > curr.start_date
    AND pos.incent_st_date       < curr.end_date                                                                                                                                                                                                    
    AND (pos.incent_end_date IS NULL OR pos.incent_end_date > curr.start_date) limit 1;

-- incnt_stmt_personal_details_PaymentFreq
CREATE VIEW exincst.incnt_stmt_personal_details_PaymentFreq AS
select  pt.payment_frequency

 FROM xactly.xc_participant pt
-- ── Logic to grab ONLY the absolute latest version ──────────
INNER JOIN (
    SELECT Max(version) AS max_version, employee_id,name
    FROM xactly.xc_participant
    WHERE name = :v_participant 
    GROUP BY employee_id
) latest
    ON  latest.employee_id = pt.employee_id
    AND latest.max_version = pt.version
inner JOIN (select * from xactly.xc_pos_part_assignment where participant_name=:v_participant order by version desc LIMIT 1) ppa
    ON  ppa.participant_name = pt.name and 
ppa.is_active=1
INNER JOIN xactly.xc_position pos
    ON  pos.position_id = ppa.position_id
AND pos.is_active = 1 
INNER JOIN xactly.xc_business_group bg
    ON  bg.business_group_id = pos.business_group_id
LEFT JOIN xactly.xc_pos_title_assignment pta
    ON  pta.position_id = pos.position_id
LEFT JOIN xactly.xc_title t
    ON  t.title_id = pta.title_id
LEFT JOIN xactly.xc_pos_hierarchy ph
    ON  ph.to_pos_id = pos.position_id
LEFT JOIN xactly.xc_pos_part_assignment ppa_mgr
    ON  ppa_mgr.position_id = ph.from_pos_id
LEFT JOIN xactly.xc_participant mgr_pt
    ON  mgr_pt.participant_id = ppa_mgr.participant_id
    AND mgr_pt.is_active = 1
WHERE pt.name = :v_participant;

-- incnt_stmt_personal_details_Personaltarget
CREATE VIEW exincst.incnt_stmt_personal_details_Personaltarget AS
SELECT FormatNumber(pt.personal_target, '#,##0.00') as personal_target
  FROM xactly.xc_participant pt
  JOIN xactly.xc_period po
    ON pt.effective_start_date <  po.end_date
   AND pt.effective_end_date   >  po.start_date
  WHERE po.name = :v_period
    AND pt.name = :v_participant;

-- incnt_stmt_personal_details_plantype
CREATE VIEW exincst.incnt_stmt_personal_details_plantype AS
select   t.descr                                             AS plan_type
/*pt.employee_id                                      AS nokia_id,
   latest.name                                           AS participant_name,
 t.name                                              AS sip_role,
    bg.name                                             AS bggroup,
    Coalesce(mgr_pt.name, 'No Manager')                 AS manager_name,
    pos.name                                            AS position_name,
    pt.payment_frequency,
    pos.incent_st_date,
    Coalesce(pos.incent_end_date, '2035-12-31')         AS incent_end_date,
    pt.personal_target,
    CurDate()                                           AS curdate,
    LookupUnitTypeNameById(pt.salary_unit_type_id)      AS salary_unit_type*/

 FROM xactly.xc_participant pt
-- ── Logic to grab ONLY the absolute latest version ──────────
INNER JOIN (
    SELECT Max(version) AS max_version, employee_id,name
    FROM xactly.xc_participant
    WHERE name = :v_participant 
    GROUP BY employee_id
) latest
    ON  latest.employee_id = pt.employee_id
    AND latest.max_version = pt.version
inner JOIN (select * from xc_pos_part_assignment where participant_name=:v_participant order by version desc LIMIT 1) ppa
    ON  ppa.participant_name = pt.name and 
ppa.is_active=1
INNER JOIN xactly.xc_position pos
    ON  pos.position_id = ppa.position_id
AND pos.is_active = 1 
INNER JOIN xactly.xc_business_group bg
    ON  bg.business_group_id = pos.business_group_id
LEFT JOIN xactly.xc_pos_title_assignment pta
    ON  pta.position_id = pos.position_id
LEFT JOIN xactly.xc_title t
    ON  t.title_id = pta.title_id
LEFT JOIN xactly.xc_pos_hierarchy ph
    ON  ph.to_pos_id = pos.position_id
LEFT JOIN xactly.xc_pos_part_assignment ppa_mgr
    ON  ppa_mgr.position_id = ph.from_pos_id
LEFT JOIN xactly.xc_participant mgr_pt
    ON  mgr_pt.participant_id = ppa_mgr.participant_id
    AND mgr_pt.is_active = 1
WHERE pt.name = :v_participant;

-- incnt_stmt_personal_details_position_name
-- variables: v_participant=A.S.M. Zakir Hossain (62092353) (String)
CREATE VIEW exincst.incnt_stmt_personal_details_position_name AS
select pos.name as position_name                                                                                                                                                                                                                                             
  from xactly.xc_position pos
  join xactly.xc_period curr on 1=1                                                                                                                                                                                                                                            
  where pos.master_position_id = :v_master_position_id
    and curr.name = :v_period                                                                                                                                                                                                                                                  
    and pos.effective_start_date < curr.end_date
    and pos.effective_end_date > curr.start_date;

-- incnt_stmt_personal_details_sip_role
-- variables: v_period=APR-2025 (String), v_position_name=61235350_14042025 (String)
CREATE VIEW exincst.incnt_stmt_personal_details_sip_role AS
select distinct t.name as sip_role
  from xactly.xc_position pos                                                                                                                                                                                                                                                  
  join xactly.xc_period curr on 1=1                                                                                                                                                                                                                                            
  join xactly.xc_pos_title_assignment pta                                                                                                                                                                                                                                      
      on pta.position_id = pos.position_id
      and pta.is_active = 1                                                                                                                                                                                                                                                    
  join xactly.xc_title t
      on t.title_id = pta.title_id                                                                                                                                                                                                                                             
  where pos.name = :v_position_name
    and curr.name = :v_period                                                                                                                                                                                                                                                  
    and pos.effective_start_date < curr.end_date
    and pos.effective_end_date > curr.start_date;

-- incnt_stmt_personal_details_target_unittytpe
CREATE VIEW exincst.incnt_stmt_personal_details_target_unittytpe AS
select   pt.target_currency
  FROM xactly.xc_participant pt
  JOIN xactly.xc_period po
    ON pt.effective_start_date <  po.end_date
   AND pt.effective_end_date   >  po.start_date
  WHERE po.name = :v_period
    AND pt.name = :v_participant;

-- incnt_stmt_personal_details_unittytpe
CREATE VIEW exincst.incnt_stmt_personal_details_unittytpe AS
select   LookupUnitTypeNameById(pt.salary_unit_type_id)      AS salary_unit_type
  FROM xactly.xc_participant pt
  JOIN xactly.xc_period po
    ON pt.effective_start_date <  po.end_date
   AND pt.effective_end_date   >  po.start_date
  WHERE po.name = :v_period
    AND pt.name = :v_participant;

-- incnt_stmt_plan_doc_ackstatus_date
CREATE VIEW exincst.incnt_stmt_plan_doc_ackstatus_date AS
select 1 as type, FormatDateTime(ToDate(SubString(per_acpt_date, 0, 10), 'yyyy-MM-dd'),'dd/MM/yyyy') AS per_acpt_date  from xactly.xc_plan_approval where person_id=:v_master_participant_id
union 
select 2 as type, 'Data Not Found' as per_acpt_date from Empty() order by type limit 1;

-- incnt_stmt_plan_doc_status
CREATE VIEW exincst.incnt_stmt_plan_doc_status AS
select 1 as type, status from xactly.xc_plan_approval where person_id=:v_master_participant_id
union 
select 2 as type, 'Data Not Found' as status from Empty() order by type limit 1;

-- incnt_stmt_qtr_name_dynamic
-- variables: v_period=MAR-2025 (String)
CREATE VIEW exincst.incnt_stmt_qtr_name_dynamic AS
select name as qtr_name from xactly.xc_period per where period_id in 
(select p.parent_period_id from xactly.xc_period p  
			where p.name = :v_period);

-- incnt_stmt_quota_attainment_ranked
CREATE VIEW exincst.incnt_stmt_quota_attainment_ranked AS
SELECT                                                                                                                                                                                                                                                                       
      quota_name,                                                                                                                                                                                                                                                              
      attainment_pct,                                                                                                                                                                                                                                                          
      arc_pct,                                                                                                                                                                                                                                                                 
      total_credit,                                                                                                                                                                                                                                                            
      quota_amount,                                                                                                                                                                                                                                                            
      disp,                                                                                                                                                                                                                                                                    
      SeqNum() AS ord                                                                                                                                                                                                                                                          
  FROM (                                                                                                                                                                                                                                                                       
      SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw                                                                                                                                                                                    
      FROM exincst.incnt_stmt_quota_base                                                                                                                                                                                                                                               
      ORDER BY tgt_raw,quota_name DESC                                                                                                                                                                                                                                                    
  );

-- incnt_stmt_quota_base
CREATE VIEW exincst.incnt_stmt_quota_base AS
SELECT                                                                                                                                                                                                                                                                       
      quota_name,                                                                                                                                                                                                                                                              
      Nvl(FormatNumber(Round(att, 2), '#,##0.00'), '0.00') || '%' AS attainment_pct,                                                                                                                                                                                           
      Nvl(FormatNumber(Round(CASE WHEN att > 100 THEN 50 ELSE att / 2 END, 2), '#,##0.00'), '0.00') || '%' AS arc_pct,                                                                                                                                                         
      Nvl(FormatNumber(cred, '#,##0.00'), '0.00') AS total_credit,                                                                                                                                                                                                             
      Nvl(FormatNumber(tgt,  '#,##0.00'), '0.00') AS quota_amount,                                                                                                                                                                                                             
      'block' AS disp,                                                                                                                                                                                                                                                         
      tgt AS tgt_raw                                                                                                                                                                                                                                                           
  FROM (                                                                                                                                                                                                                                                                       
      SELECT                                                                                                                                                                                                                                                                   
          q.name AS quota_name,                                                                                                                                                                                                                                                
          Nvl(b.cred, 0) AS cred,                                                                                                                                                                                                                                              
          tg.tgt AS tgt,                                                                                                                                                                                                                                                       
          CASE WHEN tg.tgt > 0 THEN Nvl(b.cred, 0) / tg.tgt * 100 ELSE 0 END AS att                                                                                                                                                                                            
      FROM (                                                                                                                                                                                                                                                                   
          SELECT qa.quota_id, Max(qa.amount) AS tgt                                                                                                                                                                                                                            
          FROM xactly.xc_quota_assignment qa                                                                                                                                                                                                                                   
          JOIN xactly.xc_period yp ON yp.period_id = qa.period_id                                                                                                                                                                                                              
          WHERE qa.assignment_id = :v_master_position_id                                                                                                                                                                                                                       
            AND yp.name LIKE Concat('%-', :v_year_number)                                                                                                                                                                                                                      
          GROUP BY qa.quota_id                                                                                                                                                                                                                                                 
      ) tg                                                                                                                                                                                                                                                                     
      JOIN xactly.xc_quota q ON q.quota_id = tg.quota_id                                                                                                                                                                                                                       
      LEFT JOIN (                                                                                                                                                                                                                                                              
          SELECT cq.quota_id, SUM(cr.amount) AS cred                                                                                                                                                                                                                           
          FROM (                                                                                                                                                                                                                                                               
              SELECT DISTINCT cm.quota_id, cm.credit_id                                                                                                                                                                                                                        
              FROM xactly.xc_commission cm                                                                                                                                                                                                                                     
              WHERE cm.position_id = :v_master_position_id                                                                                                                                                                                                                     
          ) cq                                                                                                                                                                                                                                                                 
          JOIN xactly.xc_credit cr ON cr.credit_id = cq.credit_id                                                                                                                                                                                                              
          JOIN (                                                                                                                                                                                                                                                               
              SELECT period_id FROM xactly.xc_period                                                                                                                                                                                                                           
              WHERE name LIKE Concat('%-', :v_year_number)                                                                                                                                                                                                                     
                AND end_date <= ( SELECT end_date FROM xactly.xc_period WHERE name = :v_period )                                                                                                                                                                               
          ) ps ON ps.period_id = cr.period_id                                                                                                                                                                                                                                  
          GROUP BY cq.quota_id                                                                                                                                                                                                                                                 
      ) b ON b.quota_id = tg.quota_id                                                                                                                                                                                                                                          
  );

-- incnt_stmt_quota_slot_1
CREATE VIEW exincst.incnt_stmt_quota_slot_1 AS
SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp
FROM (
    SELECT 1 AS t, quota_name, attainment_pct, arc_pct, total_credit, quota_amount, 'block' AS disp
    FROM (
        SELECT
            quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp,
            SeqNum() AS ord
        FROM (
            SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw
            FROM exincst.incnt_stmt_quota_base
            ORDER BY tgt_raw, quota_name DESC
        )
    )
    WHERE ord = 1
    UNION ALL
    SELECT 2 AS t, '' AS quota_name, '0%' AS attainment_pct, '0%' AS arc_pct, '0.00' AS total_credit, '0.00' AS quota_amount, 'none' AS disp
    FROM Empty()
)
ORDER BY t
LIMIT 1;

-- incnt_stmt_quota_slot_2
CREATE VIEW exincst.incnt_stmt_quota_slot_2 AS
SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp
FROM (
    SELECT 1 AS t, quota_name, attainment_pct, arc_pct, total_credit, quota_amount, 'block' AS disp
    FROM (
        SELECT
            quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp,
            SeqNum() AS ord
        FROM (
            SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw
            FROM exincst.incnt_stmt_quota_base
            ORDER BY tgt_raw, quota_name DESC
        )
    )
    WHERE ord = 2
    UNION ALL
    SELECT 2 AS t, '' AS quota_name, '0%' AS attainment_pct, '0%' AS arc_pct, '0.00' AS total_credit, '0.00' AS quota_amount, 'none' AS disp
    FROM Empty()
)
ORDER BY t
LIMIT 1;

-- incnt_stmt_quota_slot_3
CREATE VIEW exincst.incnt_stmt_quota_slot_3 AS
SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp
FROM (
    SELECT 1 AS t, quota_name, attainment_pct, arc_pct, total_credit, quota_amount, 'block' AS disp
    FROM (
        SELECT
            quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp,
            SeqNum() AS ord
        FROM (
            SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw
            FROM exincst.incnt_stmt_quota_base
            ORDER BY tgt_raw, quota_name DESC
        )
    )
    WHERE ord = 3
    UNION ALL
    SELECT 2 AS t, '' AS quota_name, '0%' AS attainment_pct, '0%' AS arc_pct, '0.00' AS total_credit, '0.00' AS quota_amount, 'none' AS disp
    FROM Empty()
)
ORDER BY t
LIMIT 1;

-- incnt_stmt_quota_slot_4
CREATE VIEW exincst.incnt_stmt_quota_slot_4 AS
SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp
FROM (
    SELECT 1 AS t, quota_name, attainment_pct, arc_pct, total_credit, quota_amount, 'block' AS disp
    FROM (
        SELECT
            quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp,
            SeqNum() AS ord
        FROM (
            SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw
            FROM exincst.incnt_stmt_quota_base
            ORDER BY tgt_raw, quota_name DESC
        )
    )
    WHERE ord = 4
    UNION ALL
    SELECT 2 AS t, '' AS quota_name, '0%' AS attainment_pct, '0%' AS arc_pct, '0.00' AS total_credit, '0.00' AS quota_amount, 'none' AS disp
    FROM Empty()
)
ORDER BY t
LIMIT 1;

-- incnt_stmt_quota_slot_5
CREATE VIEW exincst.incnt_stmt_quota_slot_5 AS
SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp
FROM (
    SELECT 1 AS t, quota_name, attainment_pct, arc_pct, total_credit, quota_amount, 'block' AS disp
    FROM (
        SELECT
            quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp,
            SeqNum() AS ord
        FROM (
            SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw
            FROM exincst.incnt_stmt_quota_base
            ORDER BY tgt_raw, quota_name DESC
        )
    )
    WHERE ord = 5
    UNION ALL
    SELECT 2 AS t, '' AS quota_name, '0%' AS attainment_pct, '0%' AS arc_pct, '0.00' AS total_credit, '0.00' AS quota_amount, 'none' AS disp
    FROM Empty()
)
ORDER BY t
LIMIT 1;

-- incnt_stmt_quota_slot_6
CREATE VIEW exincst.incnt_stmt_quota_slot_6 AS
SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp
FROM (
    SELECT 1 AS t, quota_name, attainment_pct, arc_pct, total_credit, quota_amount, 'block' AS disp
    FROM (
        SELECT
            quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp,
            SeqNum() AS ord
        FROM (
            SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw
            FROM exincst.incnt_stmt_quota_base
            ORDER BY tgt_raw, quota_name DESC
        )
    )
    WHERE ord = 6
    UNION ALL
    SELECT 2 AS t, '' AS quota_name, '0%' AS attainment_pct, '0%' AS arc_pct, '0.00' AS total_credit, '0.00' AS quota_amount, 'none' AS disp
    FROM Empty()
)
ORDER BY t
LIMIT 1;

-- incnt_stmt_quota_slot_7
CREATE VIEW exincst.incnt_stmt_quota_slot_7 AS
SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp
FROM (
    SELECT 1 AS t, quota_name, attainment_pct, arc_pct, total_credit, quota_amount, 'block' AS disp
    FROM (
        SELECT
            quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp,
            SeqNum() AS ord
        FROM (
            SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw
            FROM exincst.incnt_stmt_quota_base
            ORDER BY tgt_raw, quota_name DESC
        )
    )
    WHERE ord = 7
    UNION ALL
    SELECT 2 AS t, '' AS quota_name, '0%' AS attainment_pct, '0%' AS arc_pct, '0.00' AS total_credit, '0.00' AS quota_amount, 'none' AS disp
    FROM Empty()
)
ORDER BY t
LIMIT 1;

-- incnt_stmt_quota_slot_8
CREATE VIEW exincst.incnt_stmt_quota_slot_8 AS
SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp
FROM (
    SELECT 1 AS t, quota_name, attainment_pct, arc_pct, total_credit, quota_amount, 'block' AS disp
    FROM (
        SELECT
            quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp,
            SeqNum() AS ord
        FROM (
            SELECT quota_name, attainment_pct, arc_pct, total_credit, quota_amount, disp, tgt_raw
            FROM exincst.incnt_stmt_quota_base
            ORDER BY tgt_raw, quota_name DESC
        )
    )
    WHERE ord = 8
    UNION ALL
    SELECT 2 AS t, '' AS quota_name, '0%' AS attainment_pct, '0%' AS arc_pct, '0.00' AS total_credit, '0.00' AS quota_amount, 'none' AS disp
    FROM Empty()
)
ORDER BY t
LIMIT 1;

-- incnt_stmt_select_default_period
CREATE VIEW exincst.incnt_stmt_select_default_period AS
SELECT p.name
  FROM xactly.xc_period p
  INNER JOIN xactly.xc_period_type pt
      ON p.period_type_id_fk = pt.period_type_id
      AND pt.name = 'MONTHLY'
  WHERE p.end_date < CurDate()
  AND p.name NOT IN ('SOT', 'EOT')
  ORDER BY p.period_id DESC
  LIMIT 3;

-- incnt_stmt_total_commission_by_period
-- variables: v_participant=Xun Cao (61236471) (String), v_period=DEC-2025 (String)
CREATE VIEW exincst.incnt_stmt_total_commission_by_period AS
select 
FormatNumber(comm.rate_amount,'#,##0.00')||'%' as rate_amount_ft,
FormatNumber(comm.measure_value,'#,##0.00') as measure_value_ft,
FormatNumber(comm.attainment_value,'#,##0.00')||'%' as attainment_value_ft,
comm.* from xactly.xc_commission comm 
where comm.period_name = :v_period
--and comm.order_code not like 'Trigger%'
and comm.participant_name = :v_participant;

-- incnt_stmt_total_credits_by_period
-- variables: v_participant=Xun Cao (61236471) (String), v_period=DEC-2025 (String)
CREATE VIEW exincst.incnt_stmt_total_credits_by_period AS
select FormatNumber(cred.amount,'#,##0.00') as credit_amount_ft,
  cred.period_name||cred.participant_name||cred.position_name||cred.order_item_id as key_column,
  cred.* from xactly.xc_credit cred 
where cred.period_name = :v_period
and cred.participant_name = :v_participant
and cred.credit_type_name in (select credit_type from incnt_stmt_credit_types_visibility where is_include = 'true')
and cred.order_code not like 'Trigger%'
and LookupUnitTypeNameById(cred.amount_unit_type_id) = :v_target_payment_currency;

-- incnt_stmt_total_manual_adjustments
CREATE VIEW exincst.incnt_stmt_total_manual_adjustments AS
select Nvl (Adjustment_amount,'0.00') Adjustment_amount from 
(select 1) dummy left join (
select CASE WHEN max(LookupUnitTypeNameById(pay.amount_unit_type_id)) = 'USD' THEN FormatNumber(sum(pay.amount),'$#,##0.00')
    	 	WHEN max(LookupUnitTypeNameById(pay.amount_unit_type_id)) = 'EUR' THEN FormatNumber(sum(pay.amount),'?#,##0.00')
    else
    FormatNumber(sum(pay.amount),'#,##0.00')||' '||LookupUnitTypeNameById(pay.amount_unit_type_id)  end as Adjustment_amount from xactly.xc_payment pay
where pay.src_type = 'MANUAL_PAYMENT'
and pay.period_name = :v_period
and pay.participant_name = :v_participant
group by LookupUnitTypeNameById(pay.amount_unit_type_id)
  )
on 1=1;

-- incnt_stmt_total_ordersby_period
CREATE VIEW exincst.incnt_stmt_total_ordersby_period AS
select FormatNumber(Round(ord.amount, 2), '#,##0.00') AS ord_amount_ft, 
LookupUnitTypeNameById(ord.amount_unit_type_id) as amount_display_symbol, 
LookupOrderTypeNameById(ord.order_type_id) as order_type_name,
ord.* from xactly.xc_comp_order_item ord 
inner join xactly.xc_co_item_asgnmt orda 
on ord.comp_order_item_id = orda.comp_order_item_id
where ord.period_id = LookupPeriodIdByName(:v_period) and ord.order_type_id not in (219903956371184,219903956371185,219903956371186)
and orda.participant_name =:v_participant;

-- incnt_stmt_total_payment
CREATE VIEW exincst.incnt_stmt_total_payment AS
select Nvl (payment_amount,0.00) payment_amount from 
(select 1) dummy left join (
select CASE WHEN max(LookupUnitTypeNameById(pay.amount_unit_type_id)) = 'USD' THEN FormatNumber(sum(pay.amount),'$#,##0.00')
    	 	WHEN max(LookupUnitTypeNameById(pay.amount_unit_type_id)) = 'EUR' THEN FormatNumber(sum(pay.amount),'?#,##0.00')
    		else FormatNumber(sum(pay.amount),'#,##0.00')||' '||LookupUnitTypeNameById(pay.amount_unit_type_id) end as payment_amount 
from xactly.xc_payment pay		
where
	pay.period_name = :v_period   and
		 pay.participant_name = :v_participant 
group by LookupUnitTypeNameById(pay.amount_unit_type_id)
)
on 1=1;

-- incnt_stmt_total_payment_Incentives_drilldown
-- variables: v_participant=Ajay Arya (61235350) (String), v_period=APR-2025 (String)
CREATE VIEW exincst.incnt_stmt_total_payment_Incentives_drilldown AS
select FormatNumber(pay.amount,'#,##0.00') as payment_amount_ft, pay.period_name||pay.participant_name||pay.position_name||pay.order_item_id as key_column, pay.*, LookupUnitTypeNameById(pay.amount_unit_type_id) as currency_type
from xactly.xc_payment pay		
where
	pay.period_name = :v_period   and
		 pay.participant_name = :v_participant  and
            	pay.src_type in ('Incentive');

-- incnt_stmt_total_payment_previous_period
-- variables: v_master_participant_id=219903990060522 (String), v_previous_period_id=219904071958232 (String)
CREATE VIEW exincst.incnt_stmt_total_payment_previous_period AS
select                                                                                                                                                                                                                                                                       
    Nvl(CASE      
      WHEN LookupUnitTypeNameById(pay.amount_unit_type_id) = 'USD'                                                                                                                                                                                                             
        THEN FormatNumber(SUM(pay.amount),'$#,##0.00')
      WHEN LookupUnitTypeNameById(pay.amount_unit_type_id) = 'EUR'                                                                                                                                                                                                             
        THEN FormatNumber(SUM(pay.amount),'€#,##0.00')
      ELSE FormatNumber(SUM(pay.amount),'#,##0.00') || ' ' || LookupUnitTypeNameById(pay.amount_unit_type_id)                                                                                                                                                                  
    END, '0.00') as payment_amount                                                                                                                                                                                                                                             
  from xactly.xc_payment pay
  where pay.period_id = :v_previous_period_id                                                                                                                                                                                                                                  
    and pay.participant_id = :v_master_participant_id
  group by LookupUnitTypeNameById(pay.amount_unit_type_id);

-- incnt_stmt_year_name_dynamic
CREATE VIEW exincst.incnt_stmt_year_name_dynamic AS
SELECT 
    p.name AS period_label,
    SubString(p.name, 3, 7) AS period_year
FROM xactly.xc_period p 
INNER JOIN xactly.xc_period_type pt 
    ON p.period_type_id_fk = pt.period_type_id 
INNER JOIN xactly.xc_period per
    ON per.start_date BETWEEN p.start_date AND p.end_date
WHERE pt.name = 'YEARLY'
  AND per.name = :v_period;

-- incnt_stmt_year_number_dynamic
-- variables: v_period=MAY-2025 (String)
CREATE VIEW exincst.incnt_stmt_year_number_dynamic AS
SELECT 
    SubString(p.name, 3, 7) AS period_year
FROM xactly.xc_period p 
INNER JOIN xactly.xc_period_type pt 
    ON p.period_type_id_fk = pt.period_type_id 
INNER JOIN xactly.xc_period per
    ON per.start_date BETWEEN p.start_date AND p.end_date
WHERE pt.name = 'YEARLY'
  AND per.name = :v_period;

-- incnt_stmt_year_period_id
-- variables: v_year_name=PY-2025 (String)
CREATE VIEW exincst.incnt_stmt_year_period_id AS
select period_id from xactly.xc_period where name=:v_year_name;

-- incnt_stmt_ytd_total_payment
-- variables: v_period=MAR-2026 (String)
CREATE VIEW exincst.incnt_stmt_ytd_total_payment AS
select Nvl (ytd_payment_amount,0.00) ytd_payment_amount from 
(select 1) dummy left join (
Select CASE WHEN max(LookupUnitTypeNameById(pay.amount_unit_type_id)) = 'USD' THEN FormatNumber(sum(pay.amount),'$#,##0.00')
    	 	WHEN max(LookupUnitTypeNameById(pay.amount_unit_type_id)) = 'EUR' THEN FormatNumber(sum(pay.amount),'?#,##0.00')
    		else FormatNumber(Sum(pay.amount),'#,##0.00')||' '||LookupUnitTypeNameById(pay.amount_unit_type_id) end as ytd_payment_amount 
From xactly.xc_payment pay 
inner join xactly.xc_period per 
on pay.period_id = per.period_id 
Where per.start_date >= :v_year_start_date
and per.start_date <= :v_month_start_date
and pay.participant_name =  :v_participant
and (pay.earning_group_name = :v_earning_group_name or :v_earning_group_name = 'All' or :v_earning_group_name is null)
group by LookupUnitTypeNameById(pay.amount_unit_type_id)
)
on 1=1;

-- inct_stmt_months_names
-- variables: v_period=APR-2025 (String), v_year_number=2025 (String)
CREATE VIEW exincst.inct_stmt_months_names AS
SELECT
      CASE
          WHEN p.name LIKE Concat('JAN-', :v_year_number) THEN 'jan'
          WHEN p.name LIKE Concat('FEB-', :v_year_number) THEN 'feb'
          WHEN p.name LIKE Concat('MAR-', :v_year_number) THEN 'mar'
          WHEN p.name LIKE Concat('APR-', :v_year_number) THEN 'apr'
          WHEN p.name LIKE Concat('MAY-', :v_year_number) THEN 'may'
          WHEN p.name LIKE Concat('JUN-', :v_year_number) THEN 'jun'
          WHEN p.name LIKE Concat('JUL-', :v_year_number) THEN 'jul'
          WHEN p.name LIKE Concat('AUG-', :v_year_number) THEN 'aug'
          WHEN p.name LIKE Concat('SEP-', :v_year_number) THEN 'sep'
          WHEN p.name LIKE Concat('OCT-', :v_year_number) THEN 'oct'
          WHEN p.name LIKE Concat('NOV-', :v_year_number) THEN 'nov'
          WHEN p.name LIKE Concat('DEC-', :v_year_number) THEN 'dec'
      END AS month_col
  FROM xactly.xc_period p
  WHERE p.name = :v_period;

-- inct_stmt_plan_doc_data
CREATE VIEW exincst.inct_stmt_plan_doc_data AS
SELECT 
 1 as type, FormatDateTime(ToDate(SubString(route_date, 0, 10), 'yyyy-MM-dd'),'dd/MM/yyyy') AS sent_date 
FROM xactly.xc_plan_approval
WHERE person_id = :v_master_participant_id 
union 
select 2 as type , 'Data Not Found' as sent_date from Empty() order by type limit 1;

-- inctn_stmt_date_metadata
-- variables: v_master_participant_id=219903990060522 (String), v_master_position_id=219913421947169 (String), v_month_start_date=2025-04-01 (Date)
CREATE VIEW exincst.inctn_stmt_date_metadata AS
SELECT                                                                                                                                                                                                                                                                       
      p.name           AS current_period, 
      LookupPeriodIdByName(p.name) as current_period_id,
      prev.period_id   AS previous_period_id,
      prev.name        AS previous_period_name,                                                                                                                                                                                                                                
      MIN(yr.start_date) AS year_start_date,
      MAX(yr.end_date)   AS year_end_date,                                                                                                                                                                                                                                     
      p.start_date     AS month_start_date                                                                                                                                                                                                                                     
  FROM xactly.xc_period p
  LEFT JOIN xactly.xc_period prev                                                                                                                                                                                                                                              
      ON prev.end_date = AddDays(p.start_date, -1)                                                                                                                                                                                                                           
      AND AddDays(prev.start_date, 32) > prev.end_date                                                                                                                                                                                                                         
  LEFT JOIN xactly.xc_period yr
      ON Year(yr.start_date) = Year(p.start_date)                                                                                                                                                                                                                              
  WHERE p.name = :v_period                                                                                                                                                                                                                                                   
  GROUP BY                                                                                                                                                                                                                                                                     
      p.name,
      prev.period_id,                                                                                                                                                                                                                                                          
      prev.name,                                                                                                                                                                                                                                                             
      p.start_date;

-- inctn_stmt_session_id
CREATE VIEW exincst.inctn_stmt_session_id AS
SELECT UUID() as session_id from dual;

-- Master_participant_id
CREATE VIEW exincst.Master_participant_id AS
select pa.name,master_pa.participant_id as master_participant_id from xactly.xc_participant pa 
inner join 
xactly.xc_period p 
on pa.effective_start_date < p.end_date 
and pa.effective_end_date > p.start_date
join xactly.xc_participant master_pa on pa.employee_id=master_pa.employee_id and master_pa.is_master=1
where p.name = :v_period and pa.name=:v_participant
order by pa.name asc;

-- Master_Position_id
-- variables: v_master_participant_id=219906345600427 (String), v_period=DEC-2025 (String)
CREATE VIEW exincst.Master_Position_id AS
SELECT pos.master_position_id,                                                                                                                                                                                                                                               
         MIN(pos.name) AS position_name
  FROM xactly.xc_participant master_part
  JOIN xactly.xc_period curr ON 1 = 1                                                                                                                                                                                                                                          
  LEFT JOIN xactly.xc_pos_part_assignment ppa
    ON ppa.participant_id = master_part.participant_id                                                                                                                                                                                                                         
  JOIN xactly.xc_position pos
    ON pos.position_id            = ppa.position_id                                                                                                                                                                                                                            
    AND pos.effective_start_date  < curr.end_date
    AND pos.effective_end_date    > curr.start_date                                                                                                                                                                                                                            
   -- AND pos.incent_st_date        < curr.end_date                                                                                                                                                                                                                              
    --AND pos.incent_end_date       > curr.start_date
  WHERE master_part.participant_id = :v_master_participant_id                                                                                                                                                                                                                  
    AND master_part.is_master      = 1
    AND curr.name                  = :v_period                                                                                                                                                                                                                                 
  GROUP BY pos.master_position_id;

-- q_get_name_from_participant
-- variables: v_participant=AHMAD RAZMAN MOHD RASHID(69055291) (String), v_period=MAY-2025 (String)
CREATE VIEW exincst.q_get_name_from_participant AS
Select SubString(pa.name, 0, IndexOf(pa.name, '(')) As participant_name_only 
from xactly.xc_participant pa 
inner join 
xactly.xc_period p 
on pa.effective_start_date < p.end_date 
and pa.effective_end_date > p.start_date
where p.name = :v_period
and pa.name = :v_participant
order by pa.name asc;
