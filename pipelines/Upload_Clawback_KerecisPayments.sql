-- =============================================================================
-- Process: p_o_upload_process_Upload_Clawback_KerecisPayments
-- FRD:     Coloplast SOW67 FRD Incent V5  §4.8  Load Payment Data
-- Schema:  ~/Documents/xc_tables  (no invented *_name columns on xc_comp_order_item)
--
-- Step order is the Connect object order. Paste each block into the named step.
-- First validation insert Overwrite=true wipes the prior run; later inserts append.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- p_o_set_dynamic_variables
-- -----------------------------------------------------------------------------

-- s_o_set_processname_Upload_Clawback_KerecisPayments
set v_process_name_Upload_Clawback_KerecisPayments *= 'Upload_Clawback_KerecisPayments'

-- s_o_set_batch_size_Upload_Clawback_KerecisPayments
set v_batch_size *= 20000

-- s_o_set_seq_Upload_Clawback_KerecisPayments
set v_seq *= '001'

-- s_o_set_reference_file_name_Upload_Clawback_KerecisPayments
set v_reference_file_name *= 'Kerecis_Exceptions_File.xlsx'

-- s_o_set_commission_batch_type_Upload_Clawback_KerecisPayments
set v_commission_batch_type *= 'Kerecis Commission Data'

-- s_o_set_aging_days_Upload_Clawback_KerecisPayments
set v_aging_days *= 100

-- s_o_set_clawback_lookback_Upload_Clawback_KerecisPayments
set v_clawback_lookback_days *= 1500

-- s_o_set_clawback_order_types_Upload_Clawback_KerecisPayments
set v_clawback_order_types *= 'Commission Sales Clawback,Historical Commission Sales Clawback'

-- s_o_set_period_dates_Upload_Clawback_KerecisPayments
set v_period_start_date *= (select start_date from xactly.xc_period where name = :v_period_name)
set v_period_end_date   *= (select end_date   from xactly.xc_period where name = :v_period_name)

-- s_o_seed_processing_date_map_Upload_Clawback_KerecisPayments
insert into Delta(TableName='delta.Clawback_processing_date_map', Unlogged=true, Overwrite=true)
select 'JAN-2026' as period_name, ToDate('02/10/2026','MM/dd/yyyy') as processing_date from Empty()
union all select 'FEB-2026', ToDate('03/10/2026','MM/dd/yyyy')
union all select 'OCT-2026', ToDate('11/10/2026','MM/dd/yyyy')
union all select 'NOV-2026', ToDate('12/10/2026','MM/dd/yyyy')
union all select 'DEC-2026', ToDate('01/10/2027','MM/dd/yyyy')

-- s_o_set_processing_date_Upload_Clawback_KerecisPayments
set v_processing_date *= Nvl(
  (select processing_date from delta.Clawback_processing_date_map where period_name = :v_period_name),
  CurDate()
)

-- s_o_set_start_email_subject_Upload_Clawback_KerecisPayments
set v_email_subject *= :v_shared_customer_name
  || ' - Process ' || :v_process_name_Upload_Clawback_KerecisPayments
  || ' STARTED for period ' || :v_period_name

-- s_o_send_start_email_Upload_Clawback_KerecisPayments
-- send email e_generic_email


-- -----------------------------------------------------------------------------
-- p_o_load_source_Upload_Clawback_KerecisPayments
-- INBOUND-Payment-01 (missing / wrong file) is a Connect file-exists check, not SQL.
-- -----------------------------------------------------------------------------

-- s_o_set_source_file_name_Upload_Clawback_KerecisPayments
set v_filename_Upload_Clawback_KerecisPayments *= 'Payments_' || :v_period_name || '.csv'

-- s_o_read_source_dump_Upload_Clawback_KerecisPayments
-- FRD columns only. Invoice_Date: FRD = MM/dd/yyyy; also accept yyyy-MM-dd.
insert into Delta(TableName='delta.Clawback_Payments_dump', Unlogged=true, Overwrite=true)
select
  :v_filename_Upload_Clawback_KerecisPayments as source_file,
  "Invoice_Number" as Invoice_Number,
  "Invoice_Date"   as Invoice_Date,
  case
    when "Invoice_Date" is null or Trim("Invoice_Date") = '' then null
    when "Invoice_Date" like '%-%' then ToDate("Invoice_Date", 'yyyy-MM-dd')
    else ToDate("Invoice_Date", 'MM/dd/yyyy')
  end as invoice_date_dt,
  ToDecimal(Nvl("Amount", '0'))        as amount_n,
  ToDecimal(Nvl("Unpaid_Amount", '0')) as unpaid_amount_n,
  "Date_Invoice_Closed" as Date_Invoice_Closed,
  "Order_Custom_Field1" as Order_Custom_Field1,
  "Order_Custom_Field2" as Order_Custom_Field2,
  SeqNum() as row_no
from ReadFile(
  FilePath='/inbound/' || :v_filename_Upload_Clawback_KerecisPayments,
  FirstLineNames=true,
  Separator=',',
  Trim=true
)

-- s_o_read_reference_dump_Upload_Clawback_KerecisPayments
-- Required file. Process must stop if missing (Connect file check + error email).
insert into Delta(TableName='delta.kerecis_exceptions_dump', Unlogged=true, Overwrite=true)
select
  "Salesperson_ID"   as Salesperson_ID,
  "Exception Type"   as Exception_Type,
  "Exception_Rule"   as Exception_Rule,
  "Invoice"          as Invoice,
  "Customer_ID"      as Customer_ID,
  "Customer_Name"    as Customer_Name,
  ToDecimal(Nvl("Rate", '0')) as Rate,
  case
    when ToDecimal(Nvl("Rate", '0')) > 1 then ToDecimal("Rate") / 100.0
    else ToDecimal(Nvl("Rate", '0'))
  end as rate_pct,
  "Reassignment From" as Reassignment_From,
  "Reassignment To"   as Reassignment_To,
  Nvl(ToDate("Effective_Start_Date", 'MM/dd/yyyy'), ToDate('01/01/1900', 'MM/dd/yyyy')) as eff_start,
  Nvl(ToDate("Effective_End_Date",   'MM/dd/yyyy'), ToDate('12/31/2035', 'MM/dd/yyyy')) as eff_end
from ReadFile(
  FilePath='/inbound/reference/' || :v_reference_file_name,
  FirstLineNames=true,
  Trim=true
)

-- s_o_load_active_employees_Upload_Clawback_KerecisPayments
-- FRD HR: incentive end date lives on the POSITION, not the person.
insert into Delta(TableName='delta.Clawback_active_employees', Unlogged=true, Overwrite=true)
select distinct
  p.employee_id as employee_id
from xactly.xc_participant p
join xactly.xc_position pos
  on pos.participant_id = p.participant_id
 and Nvl(pos.is_master, '0') = '1'
where Nvl(pos.incent_end_date, ToDate('12/31/2035', 'MM/dd/yyyy')) >= :v_period_end_date
  and Nvl(pos.incent_st_date,  ToDate('01/01/1900', 'MM/dd/yyyy')) <= :v_period_end_date

-- s_o_load_commission_paid_dump_Upload_Clawback_KerecisPayments
-- Commission Sales only. Do NOT union Historical clawbacks here.
-- Names: join xc_user_batch / xc_batch_type / xc_order_type / xc_unit_type.
-- Rate / attainment: xc_commission columns (flex Segment/Highest_Rate are NOT on xc_comp_order_item).
insert into Delta(TableName='delta.Clawback_commission_paid_dump', Unlogged=true, Overwrite=true)
select
  paid.order_code,
  paid.employee_id,
  paid.orig_item_code,
  paid.customer_id_pk,
  Nvl(os.SOLD_TO_ID, paid.customer_id_flex) as customer_id_ext,
  paid.customer_name,
  paid.order_amount,
  paid.commission_amount,
  paid.amount_unit_type_name,
  paid.orig_incentive_date,
  paid.orig_order_date,
  Nvl(os.Segment, '') as segment,
  paid.highest_rate,
  paid.att_qtd,
  paid.att_ytd
from (
  select
    coi.order_code              as order_code,
    p.employee_id               as employee_id,
    coi.item_code               as orig_item_code,
    coi.customer_id             as customer_id_pk,
    coi.CustomerID              as customer_id_flex,
    coi.customer_name           as customer_name,
    coi.amount                  as order_amount,
    Sum(cm.amount)              as commission_amount,
    ut.name                     as amount_unit_type_name,
    coi.incentive_date          as orig_incentive_date,
    coi.order_date              as orig_order_date,
    Nvl(Max(cm.calculated_rate), Max(cm.rate_amount)) as highest_rate,
    Max(cm.attainment_value)    as att_qtd,
    Max(cm.roll_attainment_value) as att_ytd
  from xactly.xc_comp_order_item coi
  join xactly.xc_user_batch ub
    on ub.batch_id = coi.batch_id
  join xactly.xc_batch_type bt
    on bt.batch_type_id = ub.batch_type_id
  join xactly.xc_unit_type ut
    on ut.unit_type_id = coi.amount_unit_type_id
  join xactly.xc_commission cm
    on cm.order_item_id = coi.comp_order_item_id
   and Nvl(cm.is_active, '1') = '1'
   and Nvl(cm.is_held,   '0') = '0'
  join xactly.xc_participant p
    on p.participant_id = cm.participant_id
  where bt.name = :v_commission_batch_type
    and Nvl(coi.is_active, '1') = '1'
    and DiffTime(:v_processing_date, coi.incentive_date, 'DAYS') <= :v_clawback_lookback_days
  group by
    coi.order_code,
    p.employee_id,
    coi.item_code,
    coi.customer_id,
    coi.CustomerID,
    coi.customer_name,
    coi.amount,
    ut.name,
    coi.incentive_date,
    coi.order_date
) paid
left join (
  select
    order_code,
    item_code,
    Max(SOLD_TO_ID) as SOLD_TO_ID,
    Max(Segment)    as Segment
  from xactly.xc_order_stage
  group by order_code, item_code
) os
  on os.order_code = paid.order_code
 and os.item_code  = paid.orig_item_code

-- s_o_load_existing_clawback_dump_Upload_Clawback_KerecisPayments
-- Employee from credit when present; else from still-staged assignment (historical not calculated).
insert into Delta(TableName='delta.Clawback_existing_dump', Unlogged=true, Overwrite=true)
select distinct
  src.order_code,
  src.employee_id,
  src.item_code,
  src.customer_id_pk,
  src.customer_id_ext,
  src.customer_name,
  src.clawback_amount,
  src.amount_unit_type_name,
  src.related_order_code,
  src.orig_order_date,
  src.segment,
  src.highest_rate,
  src.att_qtd,
  src.att_ytd
from (
  select
    coi.order_code                    as order_code,
    p.employee_id                     as employee_id,
    coi.item_code                     as item_code,
    coi.customer_id                   as customer_id_pk,
    Nvl(os.SOLD_TO_ID, coi.CustomerID) as customer_id_ext,
    coi.customer_name                 as customer_name,
    coi.amount                        as clawback_amount,
    ut.name                           as amount_unit_type_name,
    coi.related_order_code            as related_order_code,
    coi.order_date                    as orig_order_date,
    Nvl(os.Segment, '')               as segment,
    Nvl(os.Highest_Rate, 0)           as highest_rate,
    Nvl(os.att_qtd, 0)                as att_qtd,
    Nvl(os.att_ytd, 0)                as att_ytd
  from xactly.xc_comp_order_item coi
  join xactly.xc_order_type ot
    on ot.order_type_id = coi.order_type_id
  join xactly.xc_unit_type ut
    on ut.unit_type_id = coi.amount_unit_type_id
  join xactly.xc_credit c
    on c.order_item_id = coi.comp_order_item_id
   and Nvl(c.is_active, '1') = '1'
  join xactly.xc_participant p
    on p.participant_id = c.participant_id
  left join xactly.xc_order_stage os
    on os.order_code = coi.order_code
   and os.item_code  = coi.item_code
  where ot.name in ('Commission Sales Clawback', 'Historical Commission Sales Clawback')
    and Nvl(coi.is_active, '1') = '1'
    and DiffTime(:v_processing_date, coi.incentive_date, 'DAYS') <= :v_clawback_lookback_days

  union

  select
    coi.order_code                    as order_code,
    p.employee_id                     as employee_id,
    coi.item_code                     as item_code,
    coi.customer_id                   as customer_id_pk,
    Nvl(os.SOLD_TO_ID, coi.CustomerID) as customer_id_ext,
    coi.customer_name                 as customer_name,
    coi.amount                        as clawback_amount,
    ut.name                           as amount_unit_type_name,
    coi.related_order_code            as related_order_code,
    coi.order_date                    as orig_order_date,
    Nvl(os.Segment, '')               as segment,
    Nvl(os.Highest_Rate, 0)           as highest_rate,
    Nvl(os.att_qtd, 0)                as att_qtd,
    Nvl(os.att_ytd, 0)                as att_ytd
  from xactly.xc_comp_order_item coi
  join xactly.xc_order_type ot
    on ot.order_type_id = coi.order_type_id
  join xactly.xc_unit_type ut
    on ut.unit_type_id = coi.amount_unit_type_id
  join xactly.xc_order_stage os
    on os.order_code = coi.order_code
   and os.item_code  = coi.item_code
  join xactly.xc_order_stage_asgnmt osa
    on osa.order_stage_id = os.order_stage_id
  join xactly.xc_participant p
    on p.participant_id = osa.participant_id
  where ot.name in ('Commission Sales Clawback', 'Historical Commission Sales Clawback')
    and Nvl(coi.is_active, '1') = '1'
    and DiffTime(:v_processing_date, coi.incentive_date, 'DAYS') <= :v_clawback_lookback_days
) src
where src.employee_id is not null

-- s_o_load_existing_correction_dump_Upload_Clawback_KerecisPayments
insert into Delta(TableName='delta.Clawback_correction_existing_dump', Unlogged=true, Overwrite=true)
select distinct
  coi.order_code as order_code,
  p.employee_id  as employee_id
from xactly.xc_comp_order_item coi
join xactly.xc_order_type ot
  on ot.order_type_id = coi.order_type_id
join xactly.xc_credit c
  on c.order_item_id = coi.comp_order_item_id
 and Nvl(c.is_active, '1') = '1'
join xactly.xc_participant p
  on p.participant_id = c.participant_id
where ot.name = 'Commission Sales Clawback Correction'
  and Nvl(coi.is_active, '1') = '1'


-- -----------------------------------------------------------------------------
-- p_validate_source_file_clawback_Kerecis
-- -----------------------------------------------------------------------------

-- s_o_init_validation_errors_Upload_Clawback_KerecisPayments
insert into Delta(TableName='delta.validation_errors_clawback', Unlogged=true, Overwrite=true)
select
  CurDate() as process_date,
  '' as source_file,
  0  as row_no,
  '' as period_name,
  '' as category,
  '' as invoice_number,
  '' as item_code,
  '' as error_field,
  '' as reject_reason
from Empty()
where '1' = '2'

-- s_o_val_invoicenum_null_Upload_Clawback_KerecisPayments
-- INBOUND-Payment-03 FAIL: Invoice_Number is null
insert into Delta(TableName='delta.validation_errors_clawback', Unlogged=true, Overwrite=false)
select
  CurDate() as process_date,
  :v_filename_Upload_Clawback_KerecisPayments as source_file,
  row_no,
  :v_period_name as period_name,
  'REJECT' as category,
  Invoice_Number as invoice_number,
  '' as item_code,
  'Invoice_Number' as error_field,
  'INBOUND-Payment-03: Invoice_Number is null' as reject_reason
from delta.Clawback_Payments_dump
where Invoice_Number is null or Trim(Invoice_Number) = ''

-- s_o_val_invoicenum_dup_Upload_Clawback_KerecisPayments
-- INBOUND-Payment-03 FAIL: Invoice_Number duplicated (all copies rejected)
insert into Delta(TableName='delta.validation_errors_clawback', Unlogged=true, Overwrite=false)
select
  CurDate() as process_date,
  :v_filename_Upload_Clawback_KerecisPayments as source_file,
  d.row_no,
  :v_period_name as period_name,
  'REJECT' as category,
  d.Invoice_Number as invoice_number,
  '' as item_code,
  'Invoice_Number' as error_field,
  'INBOUND-Payment-03: Invoice_Number is duplicated' as reject_reason
from delta.Clawback_Payments_dump d
where d.Invoice_Number is not null
  and Trim(d.Invoice_Number) <> ''
  and d.Invoice_Number in (
    select Invoice_Number
    from delta.Clawback_Payments_dump
    where Invoice_Number is not null
      and Trim(Invoice_Number) <> ''
    group by Invoice_Number
    having count(*) > 1
  )

-- s_o_val_invoicedate_null_Upload_Clawback_KerecisPayments
insert into Delta(TableName='delta.validation_errors_clawback', Unlogged=true, Overwrite=false)
select
  CurDate() as process_date,
  :v_filename_Upload_Clawback_KerecisPayments as source_file,
  row_no,
  :v_period_name as period_name,
  'REJECT' as category,
  Invoice_Number as invoice_number,
  '' as item_code,
  'Invoice_Date' as error_field,
  'INBOUND-Payment-03: Invoice_Date is null or unparseable' as reject_reason
from delta.Clawback_Payments_dump
where invoice_date_dt is null

-- s_o_val_unpaid_neg_Upload_Clawback_KerecisPayments
-- INBOUND-Payment-04 WARN
insert into Delta(TableName='delta.validation_errors_clawback', Unlogged=true, Overwrite=false)
select
  CurDate() as process_date,
  :v_filename_Upload_Clawback_KerecisPayments as source_file,
  row_no,
  :v_period_name as period_name,
  'WARNING' as category,
  Invoice_Number as invoice_number,
  '' as item_code,
  'Unpaid_Amount' as error_field,
  'INBOUND-Payment-04: Unpaid_Amount is negative' as reject_reason
from delta.Clawback_Payments_dump
where unpaid_amount_n < 0

-- s_o_val_invoicenum_notfound_Upload_Clawback_KerecisPayments
-- INBOUND-Payment-02 WARN
insert into Delta(TableName='delta.validation_errors_clawback', Unlogged=true, Overwrite=false)
select
  CurDate() as process_date,
  :v_filename_Upload_Clawback_KerecisPayments as source_file,
  P.row_no,
  :v_period_name as period_name,
  'WARNING' as category,
  P.Invoice_Number as invoice_number,
  '' as item_code,
  'Invoice_Number' as error_field,
  'INBOUND-Payment-02: Invoice_Number ' || P.Invoice_Number || ' not found among Incent orders' as reject_reason
from delta.Clawback_Payments_dump P
where P.Invoice_Number is not null
  and P.unpaid_amount_n > 0
  and P.Invoice_Number not in (
    select distinct order_code from delta.Clawback_commission_paid_dump
  )

-- s_o_val_no_active_emp_Upload_Clawback_KerecisPayments
-- INBOUND-Payment-05 WARN  (does not reference transform — that table does not exist yet)
insert into Delta(TableName='delta.validation_errors_clawback', Unlogged=true, Overwrite=false)
select
  CurDate() as process_date,
  :v_filename_Upload_Clawback_KerecisPayments as source_file,
  P.row_no,
  :v_period_name as period_name,
  'WARNING' as category,
  cp.order_code as invoice_number,
  cp.orig_item_code as item_code,
  'Employee' as error_field,
  'INBOUND-Payment-05: No active employee found for clawback on ' || cp.order_code as reject_reason
from delta.Clawback_Payments_dump P
join delta.Clawback_commission_paid_dump cp
  on cp.order_code = P.Invoice_Number
where P.unpaid_amount_n > 0
  and P.invoice_date_dt is not null
  and DiffTime(:v_processing_date, P.invoice_date_dt, 'DAYS') > :v_aging_days
  and DiffTime(:v_processing_date, P.invoice_date_dt, 'DAYS') <= :v_clawback_lookback_days
  and cp.order_code not in (
    select distinct cp2.order_code
    from delta.Clawback_commission_paid_dump cp2
    where cp2.employee_id in (select employee_id from delta.Clawback_active_employees)
  )

-- s_load_clean_clawback_Kerecis
insert into Delta(TableName='delta.Clawback_Payments_Clean', Unlogged=true, Overwrite=true)
select *
from delta.Clawback_Payments_dump d
where (d.source_file || '_' || d.row_no) not in (
  select distinct source_file || '_' || row_no
  from delta.validation_errors_clawback
  where category = 'REJECT'
)


-- -----------------------------------------------------------------------------
-- shared prestaging shells
-- -----------------------------------------------------------------------------

-- s_o_create_prestage_order_item
insert into Delta(TableName='delta.prestage_order_item', Unlogged=true, Overwrite=true)
select * from staging.order_item where '1' = '2'

-- s_o_create_prestage_order_item_assignment
insert into Delta(TableName='delta.prestage_order_item_assignment', Unlogged=true, Overwrite=true)
select * from staging.order_item_assignment where '1' = '2'

-- s_o_shared_create_archive_error_log
insert into Delta(TableName='delta.archive_order_item_validation_error', Unlogged=true, Overwrite=true)
select * from staging.order_item_validation_error where '1' = '2'

-- s_o_shared_create_process_log
insert into Delta(TableName='delta.process_log', Unlogged=true, Overwrite=true)
select
  CurDate() as process_log_creation_date,
  :v_period_name as processing_period,
  '' as category,
  '' as order_code,
  '' as item_code,
  '' as error_field,
  '' as reject_reason
from Empty()
where '1' = '2'


-- -----------------------------------------------------------------------------
-- p_o_transform_Upload_Clawback_KerecisPayments
-- -----------------------------------------------------------------------------

-- s_o_classify_payments_Upload_Clawback_KerecisPayments
insert into Delta(TableName='delta.Clawback_Payments_classified', Unlogged=true, Overwrite=true)
select
  P.*,
  DiffTime(:v_processing_date, P.invoice_date_dt, 'DAYS') as aging_days,
  case when P.unpaid_amount_n > 0 then 'UNPAID' else 'PAID' end as pay_set
from delta.Clawback_Payments_Clean P
where P.invoice_date_dt is not null
  and DiffTime(:v_processing_date, P.invoice_date_dt, 'DAYS') > :v_aging_days
  and DiffTime(:v_processing_date, P.invoice_date_dt, 'DAYS') <= :v_clawback_lookback_days

-- s_o_build_clawback_drops_Upload_Clawback_KerecisPayments
-- Exception 02 MAC – Exclude Invoices: Customer_Name
-- Exception 01 Clawback Adjustment: business Customer_ID, Unpaid < Rate * original amount
insert into Delta(TableName='delta.Clawback_drops', Unlogged=true, Overwrite=true)
select distinct cp.order_code as order_code
from delta.Clawback_commission_paid_dump cp
join delta.kerecis_exceptions_dump e
  on e.Customer_Name = cp.customer_name
 and e.Exception_Type = 'MAC – Exclude Invoices'
 and :v_period_end_date between e.eff_start and e.eff_end

union

select distinct cp.order_code as order_code
from delta.Clawback_commission_paid_dump cp
join delta.Clawback_Payments_classified P
  on P.Invoice_Number = cp.order_code
join delta.kerecis_exceptions_dump e
  on e.Customer_ID = cp.customer_id_ext
 and e.Exception_Type = 'Clawback Adjustment'
 and :v_period_end_date between e.eff_start and e.eff_end
where P.pay_set = 'UNPAID'
  and P.unpaid_amount_n < (e.rate_pct * cp.order_amount)

-- s_o_transform_clawback_Upload_Clawback_KerecisPayments
-- UNPAID + aged + active employee + no existing clawback/historical + not dropped
insert into Delta(TableName='delta.Clawback_order_transform', Unlogged=true, Overwrite=true)
select distinct
  cp.order_code as order_code,
  cp.orig_item_code || '_CB' as item_code,
  'C_' || :v_period_name || '_Kerecis_Clawback' as batch_name,
  'Kerecis Clawback Data' as batch_type_name,
  1 as quantity,
  (0 - cp.commission_amount) as amount,
  cp.amount_unit_type_name as amount_unit_type_name,
  :v_period_start_date as incentive_date,
  cp.orig_order_date as order_date,
  'Commission Sales Clawback' as order_type_name,
  cp.order_code as related_order_code,
  cp.employee_id as employee_id,
  cp.customer_name as customer_name,
  cp.segment as segment,
  cp.highest_rate as highest_rate,
  cp.att_qtd as att_qtd,
  cp.att_ytd as att_ytd,
  P.Order_Custom_Field1 as order_custom_field1,
  P.Order_Custom_Field2 as order_custom_field2,
  :v_period_name as period_name
from delta.Clawback_commission_paid_dump cp
join delta.Clawback_Payments_classified P
  on P.Invoice_Number = cp.order_code
 and P.pay_set = 'UNPAID'
where cp.employee_id in (select employee_id from delta.Clawback_active_employees)
  and cp.order_code not in (select distinct order_code from delta.Clawback_drops)
  and (cp.order_code || '_' || cp.employee_id) not in (
    select distinct order_code || '_' || employee_id
    from delta.Clawback_existing_dump
  )

-- s_o_transform_correction_Upload_Clawback_KerecisPayments
-- PAID + aged + existing clawback/historical + no existing correction + active employee
-- Amount = 0 - clawback_amount (positive when clawback_amount is negative) so net is 0.
-- Item code = original clawback item || '_CBC' (FRD).
insert into Delta(TableName='delta.Correction_order_transform', Unlogged=true, Overwrite=true)
select distinct
  ce.order_code as order_code,
  ce.item_code || '_CBC' as item_code,
  'C_' || :v_period_name || '_Kerecis_ClawbackCorr' as batch_name,
  'Kerecis Clawback Correction Data' as batch_type_name,
  1 as quantity,
  (0 - ce.clawback_amount) as amount,
  ce.amount_unit_type_name as amount_unit_type_name,
  :v_period_start_date as incentive_date,
  ce.orig_order_date as order_date,
  'Commission Sales Clawback Correction' as order_type_name,
  ce.order_code as related_order_code,
  ce.employee_id as employee_id,
  ce.customer_name as customer_name,
  ce.segment as segment,
  ce.highest_rate as highest_rate,
  ce.att_qtd as att_qtd,
  ce.att_ytd as att_ytd,
  '' as order_custom_field1,
  '' as order_custom_field2,
  :v_period_name as period_name
from delta.Clawback_existing_dump ce
join delta.Clawback_Payments_classified P
  on P.Invoice_Number = ce.order_code
 and P.pay_set = 'PAID'
where ce.employee_id in (select employee_id from delta.Clawback_active_employees)
  and (ce.order_code || '_' || ce.employee_id) not in (
    select distinct order_code || '_' || employee_id
    from delta.Clawback_correction_existing_dump
  )

-- s_o_transform_assignment_Upload_Clawback_KerecisPayments
insert into Delta(TableName='delta.Clawback_assignment_transform', Unlogged=true, Overwrite=true)
select distinct order_code, item_code, employee_id, 100 as split_amount_pct
from delta.Clawback_order_transform
where employee_id is not null
union all
select distinct order_code, item_code, employee_id, 100 as split_amount_pct
from delta.Correction_order_transform
where employee_id is not null

-- s_o_upsert_invoice_state_Upload_Clawback_KerecisPayments
-- Rebuild from this run + Incent existing dumps. Do not SELECT the same Delta
-- table in the Overwrite=true INSERT (Connect will drop it first).
insert into Delta(TableName='delta.Clawback_invoice_state', Unlogged=true, Overwrite=true)
select
  t.order_code,
  t.employee_id,
  'CLAWED' as status,
  t.amount as last_amount,
  t.highest_rate,
  :v_period_name as last_period,
  CurDate() as last_updated
from delta.Clawback_order_transform t
union all
select
  t.order_code,
  t.employee_id,
  'CORRECTED' as status,
  t.amount as last_amount,
  t.highest_rate,
  :v_period_name as last_period,
  CurDate() as last_updated
from delta.Correction_order_transform t
union all
select
  ce.order_code,
  ce.employee_id,
  'CLAWED' as status,
  ce.clawback_amount as last_amount,
  ce.highest_rate,
  :v_period_name as last_period,
  CurDate() as last_updated
from delta.Clawback_existing_dump ce
where (ce.order_code || '_' || ce.employee_id) not in (
  select distinct order_code || '_' || employee_id from delta.Clawback_order_transform
  union
  select distinct order_code || '_' || employee_id from delta.Correction_order_transform
)
  and (ce.order_code || '_' || ce.employee_id) not in (
    select distinct order_code || '_' || employee_id from delta.Clawback_correction_existing_dump
  )


-- -----------------------------------------------------------------------------
-- p_o_insert_orders_Upload_Clawback_KerecisPayments
-- -----------------------------------------------------------------------------

-- s_o_insert_to_prestage_order_item_Upload_Clawback_KerecisPayments
insert into delta.prestage_order_item (
  order_code, item_code, batch_name, batch_type_name, quantity, amount,
  amount_unit_type_name, incentive_date, order_date, order_type_name,
  related_order_code, period_name, customer_name, segment, highest_rate,
  att_qtd, att_ytd, order_custom_field1, order_custom_field2
)
select distinct
  order_code, item_code, batch_name, batch_type_name, quantity, amount,
  amount_unit_type_name, incentive_date, order_date, order_type_name,
  related_order_code, period_name, customer_name, segment, highest_rate,
  att_qtd, att_ytd, order_custom_field1, order_custom_field2
from delta.Clawback_order_transform
union all
select distinct
  order_code, item_code, batch_name, batch_type_name, quantity, amount,
  amount_unit_type_name, incentive_date, order_date, order_type_name,
  related_order_code, period_name, customer_name, segment, highest_rate,
  att_qtd, att_ytd, order_custom_field1, order_custom_field2
from delta.Correction_order_transform

-- s_o_insert_to_prestage_order_item_assignment_Upload_Clawback_KerecisPayments
insert into delta.prestage_order_item_assignment (
  order_code, item_code, employee_id, split_amount_pct
)
select distinct order_code, item_code, employee_id, split_amount_pct
from delta.Clawback_assignment_transform

-- On Error -> p_o_shared_delete_staging_tables


-- -----------------------------------------------------------------------------
-- p_o_order_validations_Upload_Clawback_KerecisPayments
-- -----------------------------------------------------------------------------

-- s_o_set_order_item_field_list
set v_order_item_field_list *= select GatherString(name, ',')
from (describe select * from staging.order_item)
where name <> 'batch_name'

-- p_o_standard_order_validations

-- s_o_insert_into_staging_valid_prestage_order_assignments
insert into staging.order_item_assignment (order_code, item_code, employee_id, split_amount_pct)
select order_code, item_code, employee_id, split_amount_pct
from delta.prestage_order_item_assignment
where order_code || item_code not in (
  select distinct order_code || item_code
  from delta.process_log
  where category = 'REJECT'
)

-- s_o_insert_into_staging_valid_prestage_order
insert into staging.order_item ({:v_order_item_field_list}, batch_name)
select {:v_order_item_field_list}, batch_name || '_' || :v_seq as batch_name
from delta.prestage_order_item
where order_code || item_code not in (
  select distinct order_code || item_code
  from delta.process_log
  where category = 'REJECT'
)

-- p_o_shared_upload_orders
-- On Error -> p_o_email_invocation_errors
