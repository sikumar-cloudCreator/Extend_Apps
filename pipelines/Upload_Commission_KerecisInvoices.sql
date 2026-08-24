-- =============================================================================
-- Process: p_o_upload_process_Upload_Commission_KerecisInvoices
-- FRD:     Coloplast SOW67 FRD Incent V5  §4.7.4  Load Commission Order Data
-- Schema:  ~/Documents/xc_tables
--
-- There is no xc_batch, xc_order_item, xc_order_item_assignment, or
-- xc_calculated_rates_view. Credits, rates, and prior stamps are read from
-- xc_credit, xc_comp_order_item, xc_commission, xc_user_batch, xc_batch_type,
-- xc_order_type, xc_participant, xc_unit_type, xc_order_stage (flex only).
-- =============================================================================


-- -----------------------------------------------------------------------------
-- p_o_set_custom_variables_UploadKerecis_Commission_Invoices
-- -----------------------------------------------------------------------------

set v_process_name_Upload_Commission_KerecisInvoices *= 'Upload_Commission_KerecisInvoices'
set v_batch_size *= 20000
set v_seq *= '001'
set v_reference_file_name *= 'Kerecis_Exceptions_File.xlsx'

-- Credit Sales batch type as configured on the tenant (mapping vs data summary).
set v_credit_batch_type *= 'Kerecis Invoices'
set v_commission_batch_type *= 'Kerecis Commission Data'

-- Mapping table names. Exception text says Commissionable Sales / Prior — those
-- must be the same xc_order_type rows. Confirm tenant names before go-live.
set v_ot_commission_current *= 'Commission Sales'
set v_ot_commission_prior   *= 'Commission Sales Prior'

-- Trigger1 commission rules that write QTD / YTD rate onto xc_commission.
set v_rule_qtd_rate *= 'C - Total Sales QTD Rate'
set v_rule_ytd_rate *= 'C - Total Sales YTD Rate'

set v_period_start_date *= (select start_date from xactly.xc_period where name = :v_period_name)
set v_period_end_date   *= (select end_date   from xactly.xc_period where name = :v_period_name)
set v_qtr_start_date *= (
  select qp.start_date
  from xactly.xc_period mp
  join xactly.xc_period qp on mp.parent_period_id = qp.period_id
  where mp.name = :v_period_name
)

set v_email_subject *= :v_shared_customer_name
  || ' - Process ' || :v_process_name_Upload_Commission_KerecisInvoices
  || ' STARTED for period ' || :v_period_name
-- send email e_generic_email


-- -----------------------------------------------------------------------------
-- p_o_read_credits_and_explode_Upload_Commission_KerecisInvoices
-- -----------------------------------------------------------------------------

-- s_o_extract_credited_orders_from_incent
-- Grain: one row per (order, credited employee). Employee_ID from xc_participant,
-- not xc_credit.participant_id. Amount = xc_credit.amount. Currency via unit type.
-- Prefer xc_comp_order_item (processed Credit Sales). Stage used only for flex.
insert into Delta(TableName='delta.credited_orders_dump', Unlogged=true, Overwrite=true)
select
  c.order_code                         as order_code,
  c.item_code                          as credit_item_code,
  p.employee_id                        as employee_id,
  c.amount                             as amount,
  Nvl(ut.name, 'USD')                  as currency,
  coi.customer_name                    as customer_name,
  Nvl(os.SOLD_TO_ID, coi.CustomerID)   as customer_id_ext,
  coi.order_date                       as order_date,
  coi.incentive_date                   as incentive_date,
  Nvl(os.Segment, '')                  as segment,
  Nvl(os.Order_Custom_Field1, '')      as order_custom_field1,
  Nvl(os.Order_Custom_Field2, '')      as order_custom_field2,
  ot.name                              as credit_sales_order_type,
  c.credit_id                          as credit_id
from xactly.xc_credit c
join xactly.xc_comp_order_item coi
  on coi.comp_order_item_id = c.order_item_id
join xactly.xc_user_batch ub
  on ub.batch_id = coi.batch_id
join xactly.xc_batch_type bt
  on bt.batch_type_id = ub.batch_type_id
join xactly.xc_order_type ot
  on ot.order_type_id = coi.order_type_id
join xactly.xc_participant p
  on p.participant_id = c.participant_id
left join xactly.xc_unit_type ut
  on ut.unit_type_id = Nvl(c.amount_unit_type_id, coi.amount_unit_type_id)
left join (
  select
    order_code,
    item_code,
    Max(Segment)             as Segment,
    Max(SOLD_TO_ID)          as SOLD_TO_ID,
    Max(Order_Custom_Field1) as Order_Custom_Field1,
    Max(Order_Custom_Field2) as Order_Custom_Field2
  from xactly.xc_order_stage
  group by order_code, item_code
) os
  on os.order_code = coi.order_code
 and os.item_code  = coi.item_code
where bt.name = :v_credit_batch_type
  and Nvl(c.is_active, '1') = '1'
  and Nvl(coi.is_active, '1') = '1'
  and ot.name <> 'NON-Commissionable Sales'
  and coi.incentive_date >= :v_qtr_start_date
  and coi.incentive_date <= :v_period_end_date

-- s_o_init_comm_validation_log
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Commission_Invoices', Unlogged=true, Overwrite=true)
select
  '' as order_code, '' as employee_id, '' as category, '' as error_message
from Empty()
where '1' = '2'

-- s_o_val_comm_invoice_01  credits with no Credit Sales order already excluded by inner join.
-- If Credit Sales dump still has QTD invoices with zero credits, log them.
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Commission_Invoices')
select
  d.Invoice_Number as order_code,
  '' as employee_id,
  'REJECT' as category,
  'COMM-Invoice-01: No matching Credit Sales credit found for Order Code ' || d.Invoice_Number
from delta.CreditSales_Invoice_dump d
where d.Invoice_Number not in (select distinct order_code from delta.credited_orders_dump)
  and d.invoice_date_dt >= :v_qtr_start_date
  and d.invoice_date_dt <= :v_period_end_date

-- s_o_val_comm_invoice_04
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Commission_Invoices')
select
  c.order_code, c.employee_id, 'WARNING',
  'COMM-Invoice-04: Segment ' || Nvl(c.segment, 'NULL') || ' is not a valid code (311, 312, 313)'
from delta.credited_orders_dump c
where c.segment is null or Trim(c.segment) not in ('311', '312', '313')

-- s_o_val_comm_invoice_05  skip non-commissionable (no overlapping plan assignment)
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Commission_Invoices')
select
  c.order_code, c.employee_id, 'SKIP',
  'COMM-Invoice-05: Credited employee ' || c.employee_id || ' is not commissionable; credit row skipped'
from delta.credited_orders_dump c
where c.employee_id not in (
  select distinct p.employee_id
  from xactly.xc_plan_assignment pa
  join xactly.xc_participant p
    on (pa.assignment_id = p.participant_id or pa.assignment_name = p.employee_id)
  where Nvl(pa.is_active, '1') = '1'
    and Nvl(pa.active_start_date, ToDate('01/01/1900', 'MM/dd/yyyy')) <= :v_period_end_date
    and Nvl(pa.active_end_date,   ToDate('12/31/2035', 'MM/dd/yyyy')) >= :v_period_start_date
)

-- s_o_read_reference_dump_Upload_Commission_KerecisInvoices
insert into Delta(TableName='delta.kerecis_exceptions_dump', Unlogged=true, Overwrite=true)
select
  "Salesperson_ID"    as Salesperson_ID,
  "Exception Type"    as Exception_Type,
  "Exception_Rule"    as Exception_Rule,
  "Invoice"           as Invoice,
  "Customer_ID"       as Customer_ID,
  "Customer_Name"     as Customer_Name,
  ToDecimal(Nvl("Rate", '0')) as Rate,
  "Reassignment From" as Reassignment_From,
  "Reassignment To"   as Reassignment_To,
  Nvl(ToDate("Effective_Start_Date", 'MM/dd/yyyy'), ToDate('01/01/1900', 'MM/dd/yyyy')) as eff_start,
  Nvl(ToDate("Effective_End_Date",   'MM/dd/yyyy'), ToDate('12/31/2035', 'MM/dd/yyyy')) as eff_end
from ReadExcelFile(
  FilePath='/inbound/reference/' || :v_reference_file_name,
  FirstLineNames=true,
  Trim=true
)

-- s_o_fetch_att_and_rates_from_incent
-- Trigger1 writes two xc_commission rows per employee in the period:
--   'C - Total Sales QTD Rate'  → qtd_rate + att_qtd
--   'C - Total Sales YTD Rate'  → ytd_rate + att_ytd
-- FRD Highest_Rate = MAX(QTD rate, YTD rate). Stamp both attainments.
insert into Delta(TableName='delta.employee_rates_dump', Unlogged=true, Overwrite=true)
select
  r.employee_id,
  r.qtd_rate,
  r.ytd_rate,
  r.att_qtd,
  r.att_ytd,
  case
    when Nvl(r.qtd_rate, 0) >= Nvl(r.ytd_rate, 0) then r.qtd_rate
    else r.ytd_rate
  end as calculated_rate
from (
  select
    p.employee_id as employee_id,
    Max(case
          when cm.rule_name = :v_rule_qtd_rate
          then Nvl(cm.calculated_rate, cm.rate_amount)
        end) as qtd_rate,
    Max(case
          when cm.rule_name = :v_rule_ytd_rate
          then Nvl(cm.calculated_rate, cm.rate_amount)
        end) as ytd_rate,
    Max(case
          when cm.rule_name = :v_rule_qtd_rate
          then cm.attainment_value
        end) as att_qtd,
    Max(case
          when cm.rule_name = :v_rule_ytd_rate
          then cm.attainment_value
        end) as att_ytd
  from xactly.xc_commission cm
  join xactly.xc_participant p
    on p.participant_id = cm.participant_id
  join xactly.xc_period per
    on per.period_id = cm.period_id
  where per.name = :v_period_name
    and Nvl(cm.is_active, '1') = '1'
    and cm.rule_name in (:v_rule_qtd_rate, :v_rule_ytd_rate)
  group by p.employee_id
) r

-- s_o_calculate_prior_paid_rates
-- Sum Highest_Rate already stamped on Commission Sales lines earlier in the quarter.
-- Flex Highest_Rate is not on xc_comp_order_item — use Connect history plus stage.
insert into Delta(TableName='delta.prior_paid_rates_summary', Unlogged=true, Overwrite=true)
select
  h.order_code,
  h.employee_id,
  Sum(Nvl(h.highest_rate, 0)) as total_prior_paid_rate
from delta.commission_rate_history h
where h.incentive_date >= :v_qtr_start_date
  and h.incentive_date <  :v_period_start_date
group by h.order_code, h.employee_id

-- If history is empty (first ever run after a prior month already uploaded in Incent),
-- fall back to xc_order_stage.Highest_Rate on prior commission batches:
-- union
-- select coi.order_code, p.employee_id, Sum(Nvl(os.Highest_Rate, 0))
-- from xc_comp_order_item coi
-- join xc_order_type ot ... ot.name in (:v_ot_commission_current, :v_ot_commission_prior)
-- join xc_user_batch / xc_batch_type bt.name = :v_commission_batch_type
-- join xc_credit c / xc_participant p
-- left join xc_order_stage os
-- where coi.incentive_date >= :v_qtr_start_date and coi.incentive_date < :v_period_start_date
-- group by ...

-- s_o_val_comm_invoice_03
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Commission_Invoices')
select
  c.order_code, c.employee_id, 'WARNING',
  'COMM-Invoice-03: Prior-period paid rate not found; full current rate applied'
from delta.credited_orders_dump c
where c.order_date < :v_period_start_date
  and (c.order_code || '_' || c.employee_id) not in (
    select distinct order_code || '_' || employee_id from delta.prior_paid_rates_summary
  )


-- -----------------------------------------------------------------------------
-- p_o_transform_UploadKerecis_Commission_Invoices
-- Order type is by ORDER DATE (FRD), not incentive_date.
-- Exception 01 Rate Override (invoice) wins over Rate Cap (customer).
-- Transform joins kerecis_exceptions_dump — not kerecis_comm_exceptions_dump.
-- SEQ is appended only at staging insert.
-- -----------------------------------------------------------------------------

-- s_o_transform_UploadKerecis_Commission_Invoices
insert into Delta(TableName='delta.UploadKerecis_Commission_Invoices_transform', Unlogged=true, Overwrite=true)
select
  c.order_code as order_code,
  c.customer_name || '_' || c.employee_id as item_code,
  'C_' || :v_period_name || '_Kerecis_Comm' as batch_name,
  :v_commission_batch_type as batch_type_name,
  c.amount as amount,
  Nvl(c.currency, 'USD') as amount_unit_type_name,
  c.incentive_date as incentive_date,
  c.order_date as order_date,
  case
    when c.order_date >= :v_period_start_date then :v_ot_commission_current
    else :v_ot_commission_prior
  end as order_type_name,
  c.customer_id_ext as CustomerID,
  c.employee_id as employee_id,
  100 as split_amount_pct,
  case
    when c.order_date >= :v_period_start_date and e_ov.Exception_Type is not null
      then e_ov.Rate
    when c.order_date >= :v_period_start_date and e_cap.Exception_Type is not null
      then e_cap.Rate
    when c.order_date >= :v_period_start_date
      then Nvl(r.calculated_rate, 0)
    when c.order_date < :v_period_start_date and e_ov.Exception_Type is not null
      then (e_ov.Rate - Nvl(p.total_prior_paid_rate, 0))
    when c.order_date < :v_period_start_date and e_cap.Exception_Type is not null
      then (e_cap.Rate - Nvl(p.total_prior_paid_rate, 0))
    else (Nvl(r.calculated_rate, 0) - Nvl(p.total_prior_paid_rate, 0))
  end as highest_rate,
  r.att_qtd as att_qtd,
  r.att_ytd as att_ytd,
  c.customer_name as customer_name,
  c.segment as Segment,
  c.order_custom_field1 as Order_Custom_Field1,
  c.order_custom_field2 as Order_Custom_Field2,
  :v_period_name as period_name
from delta.credited_orders_dump c
left join delta.employee_rates_dump r
  on r.employee_id = c.employee_id
left join delta.prior_paid_rates_summary p
  on p.order_code = c.order_code
 and p.employee_id = c.employee_id
left join delta.kerecis_exceptions_dump e_cap
  on e_cap.Customer_Name = c.customer_name
 and e_cap.Exception_Type = 'Rate Cap'
 and c.incentive_date >= e_cap.eff_start
 and c.incentive_date <= e_cap.eff_end
left join delta.kerecis_exceptions_dump e_ov
  on e_ov.Invoice = c.order_code
 and e_ov.Exception_Type = 'Rate Override'
 and c.incentive_date >= e_ov.eff_start
 and c.incentive_date <= e_ov.eff_end
where (c.order_code || '_' || c.employee_id) not in (
  select distinct order_code || '_' || employee_id
  from delta.validation_errors_UploadKerecis_Commission_Invoices
  where category = 'SKIP'
)

-- s_o_val_comm_invoice_02
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Commission_Invoices')
select
  t.order_code, t.employee_id, 'WARNING',
  'COMM-Invoice-02: No Rate returned from Incent for Employee '
    || t.employee_id || ' (rules C - Total Sales QTD Rate / C - Total Sales YTD Rate)'
from delta.UploadKerecis_Commission_Invoices_transform t
where t.highest_rate is null

-- s_o_append_commission_rate_history
-- Persist stamps so next month's difference does not need xc_comp_order_item flex.
insert into Delta(TableName='delta.commission_rate_history', Unlogged=true, Overwrite=false)
select
  t.order_code,
  t.employee_id,
  t.highest_rate,
  t.incentive_date,
  t.order_date,
  :v_period_name as period_name,
  CurDate() as loaded_date
from delta.UploadKerecis_Commission_Invoices_transform t


-- -----------------------------------------------------------------------------
-- prestaging shells
-- -----------------------------------------------------------------------------

insert into Delta(TableName='delta.prestage_order_item', Unlogged=true, Overwrite=true)
select * from staging.order_item where '1' = '2'

insert into Delta(TableName='delta.prestage_order_item_assignment', Unlogged=true, Overwrite=true)
select * from staging.order_item_assignment where '1' = '2'

insert into Delta(TableName='delta.process_log', Unlogged=true, Overwrite=true)
select
  CurDate() as process_log_creation_date,
  :v_period_name as processing_period,
  '' as category, '' as order_code, '' as item_code, '' as error_field, '' as reject_reason
from Empty()
where '1' = '2'


-- -----------------------------------------------------------------------------
-- p_o_insert_orders_UploadKerecis_Commission_Invoices
-- Flex: Highest_Rate, att_qtd, att_ytd, Segment, Order_Custom_Field1/2 on staging.
-- Include order_date and CustomerID. Quantity left blank.
-- -----------------------------------------------------------------------------

-- s_o_insert_to_prestage_order_item_UploadKerecis_Commission_Invoices
insert into delta.prestage_order_item (
  order_code, item_code, batch_name, batch_type_name, customer_name,
  amount, amount_unit_type_name, incentive_date, order_date, order_type_name,
  Segment, Highest_Rate, att_qtd, att_ytd,
  Order_Custom_Field1, Order_Custom_Field2, CustomerID, period_name
)
select distinct
  order_code, item_code, batch_name, batch_type_name, customer_name,
  amount, amount_unit_type_name, incentive_date, order_date, order_type_name,
  Segment, highest_rate, att_qtd, att_ytd,
  Order_Custom_Field1, Order_Custom_Field2, CustomerID, period_name
from delta.UploadKerecis_Commission_Invoices_transform

-- s_o_insert_to_prestage_order_item_assignment_UploadKerecis_Commission_Invoices
insert into delta.prestage_order_item_assignment (order_code, item_code, employee_id, split_amount_pct)
select distinct order_code, item_code, employee_id, split_amount_pct
from delta.UploadKerecis_Commission_Invoices_transform
where employee_id is not null
  and split_amount_pct is not null


-- -----------------------------------------------------------------------------
-- p_o_order_validations_UploadKerecis_Commission_Invoices
-- -----------------------------------------------------------------------------

set v_order_item_field_list *= select GatherString(name, ',')
from (describe select * from staging.order_item)
where name <> 'batch_name'

-- s_o_order_validate_mandatory_fields_commission  (keep existing unions)

-- s_o_order_validate_batch_type / amount_unit_type / order_type  vs xc_* .name

insert into Delta(TableName='delta.process_log')
select
  CurDate() as process_log_creation_date,
  :v_period_name as processing_period,
  'REJECT' as category,
  order_code, item_code,
  employee_id as error_field,
  'Invalid Employee Id' as reject_reason
from delta.prestage_order_item_assignment
where employee_id not in (select distinct employee_id from xactly.xc_participant)

insert into staging.order_item_assignment (order_code, item_code, employee_id, split_amount_pct)
select order_code, item_code, employee_id, split_amount_pct
from delta.prestage_order_item_assignment
where order_code || item_code not in (
  select distinct order_code || item_code from delta.process_log where category = 'REJECT'
)

-- SEQ once here.
insert into staging.order_item ({:v_order_item_field_list}, batch_name)
select {:v_order_item_field_list}, batch_name || '_' || :v_seq as batch_name
from delta.prestage_order_item
where order_code || item_code not in (
  select distinct order_code || item_code from delta.process_log where category = 'REJECT'
)

-- p_o_shared_upload_orders — replace remaining "not inn" with NOT IN on
-- s_o_copy_valid_stage_order_item_temp and assignment temp.
