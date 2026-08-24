-- =============================================================================
-- Process: p_load_orders_iSolved
-- FRD:     FRD_iSolved_2026_v2  §5.1 Load Orders <SFTP>
--          §6.1–6.2 credit/commission qualifiers (Credit_Type, Commission_Eligible)
--
-- File:    iSolvedOrders<MMYYYY>.csv  →  /inbound
-- Batch:   Orders_<periodName> / Batch Type = Orders
--
-- Processing order (FRD §5.3.2): Load Orders → Hold and Release Commissions
-- Paste each block into the named Connect step.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- p_o_set_custom_variables_iSolved_Load_Orders
-- -----------------------------------------------------------------------------

-- s_o_set_process_name_iSolved_Load_Orders
set v_process_name_iSolved_Load_Orders *= 'iSolved_Load_Orders'

-- s_o_set_period_dates_iSolved_Load_Orders
set v_period_start_date *= (select start_date from xactly.xc_period where name = :v_period_name)
set v_period_end_date   *= (select end_date   from xactly.xc_period where name = :v_period_name)

-- FRD file name: iSolvedOrders<MMYYYY>.csv
-- s_o_set_mmYYYY_iSolved_Load_Orders
set v_mmYYYY *= (
  select
    case Uppercase(SubString(name, 1, 3))
      when 'JAN' then '01'
      when 'FEB' then '02'
      when 'MAR' then '03'
      when 'APR' then '04'
      when 'MAY' then '05'
      when 'JUN' then '06'
      when 'JUL' then '07'
      when 'AUG' then '08'
      when 'SEP' then '09'
      when 'OCT' then '10'
      when 'NOV' then '11'
      when 'DEC' then '12'
      else SubString('0' || ToString(Month(end_date)), -2, 2)
    end
    || SubString(name, Length(name) - 3, 4)
  from xactly.xc_period
  where name = :v_period_name
)

-- s_o_set_orders_filename_iSolved
set v_filename_iSolvedOrders *= 'iSolvedOrders' || :v_mmYYYY || '.csv'

-- FRD §5.1.3 mapping
set v_batch_type_orders *= 'Orders'
set v_order_type_orders *= 'Orders'
set v_batch_name_orders *= 'Orders_' || :v_period_name

set v_batch_size *= 20000
set v_seq *= '001'

-- Allowed Credit_Type values (FRD §5.1.2 / INBOUND-ORD-05)
set v_credit_type_bg *= 'Background Checks'
set v_credit_type_mg *= 'Managed Garnishments'

-- s_o_set_start_email_subject_iSolved_Load_Orders
set v_email_subject *= :v_shared_customer_name
  || ' - Process ' || :v_process_name_iSolved_Load_Orders
  || ' STARTED for period ' || :v_period_name
-- send email e_generic_email


-- -----------------------------------------------------------------------------
-- p_o_file_presence_iSolved_Load_Orders
-- INBOUND-ORD-01 missing / INBOUND-ORD-02 more than one = FAIL (abort)
-- -----------------------------------------------------------------------------

-- s_o_list_inbound_order_files_iSolved
insert into Delta(TableName='delta.inbound_order_files', Unlogged=true, Overwrite=true)
select name as name
from DirList(Directory='/inbound/', Filter='iSolvedOrders*.csv')

set v_orders_file_count *= (
  select count(*)
  from delta.inbound_order_files
  where name = :v_filename_iSolvedOrders
)

set v_orders_file_any_count *= (
  select count(*) from delta.inbound_order_files
)

-- Connect conditions (On Condition False → Abort):
--   INBOUND-ORD-01: v_orders_file_count = 1
--   INBOUND-ORD-02: v_orders_file_any_count <= 1


-- -----------------------------------------------------------------------------
-- p_o_read_orders_file_iSolved
-- FRD §5.1.2 Source Fields
-- -----------------------------------------------------------------------------

-- s_o_read_isolved_orders_dump
insert into Delta(TableName='delta.iSolvedOrders_dump', Unlogged=true, Overwrite=true)
select
  :v_filename_iSolvedOrders as source_file,
  Trim("Order_Number")       as Order_Number,
  Trim("Item_Number")        as Item_Number,
  Trim("Employee_ID")        as Employee_ID,
  Trim("Customer_Name")      as Customer_Name,
  Trim("Product_Name")       as Product_Name,
  Trim("Credit_Type")        as Credit_Type,
  Trim("Amount")             as Amount_raw,
  ToDecimal(Nvl(Trim("Amount"), '0')) as Amount,
  Trim("Amount_UnitType")    as Amount_UnitType,
  ToDecimal(Nvl(Trim("Quantity"), '1')) as Quantity,
  case
    when "Incentive_Date" is null or Trim("Incentive_Date") = '' then null
    else ToDate("Incentive_Date", 'yyyy-MM-dd')
  end as Incentive_Date,
  case
    when "Order_Date" is null or Trim("Order_Date") = '' then null
    else ToDate("Order_Date", 'yyyy-MM-dd')
  end as Order_Date,
  Trim("Order_Type")         as Order_Type,
  Trim("Commission_Eligible") as Commission_Eligible,
  ToDecimal(Nvl(Trim("Split_Percentage"), '100')) as Split_Percentage,
  SeqNum() as row_no
from ReadFile(
  FilePath='/inbound/' || :v_filename_iSolvedOrders,
  FirstLineNames=true,
  Separator=',',
  TextQualifier='"',
  Trim=true
)


-- -----------------------------------------------------------------------------
-- p_o_validate_orders_iSolved
-- FRD §5.1.4 Error Identification
-- -----------------------------------------------------------------------------

-- s_o_init_validation_errors_iSolved_Load_Orders
insert into Delta(TableName='delta.validation_errors_iSolved_Load_Orders', Unlogged=true, Overwrite=true)
select
  '' as source_file,
  0  as row_no,
  '' as category,
  '' as reject_reason_no,
  '' as order_code,
  '' as item_code,
  '' as error_field,
  '' as field_value,
  '' as error_message
from Empty()
where '1' = '2'

-- s_o_validate_employee_id_iSolved  (INBOUND-ORD-03 REJECT)
insert into Delta(TableName='delta.validation_errors_iSolved_Load_Orders', Unlogged=true, Overwrite=false)
select
  d.source_file,
  d.row_no,
  'REJECT' as category,
  'INBOUND-ORD-03' as reject_reason_no,
  d.Order_Number as order_code,
  d.Item_Number  as item_code,
  'Employee_ID'  as error_field,
  Nvl(d.Employee_ID, 'NULL') as field_value,
  'ERROR: Employee_ID not found in Incent and order will not be loaded to Incent.' as error_message
from delta.iSolvedOrders_dump d
where d.Employee_ID is null
   or Trim(d.Employee_ID) = ''
   or not exists (
     select 1 from xactly.xc_participant p
     where p.employee_id = d.Employee_ID
   )

-- s_o_validate_amount_iSolved  (INBOUND-ORD-04 REJECT)
insert into Delta(TableName='delta.validation_errors_iSolved_Load_Orders', Unlogged=true, Overwrite=false)
select
  d.source_file,
  d.row_no,
  'REJECT' as category,
  'INBOUND-ORD-04' as reject_reason_no,
  d.Order_Number as order_code,
  d.Item_Number  as item_code,
  'Amount' as error_field,
  Nvl(d.Amount_raw, 'NULL') as field_value,
  'ERROR: Amount is NULL or non-numeric and order will not be loaded to Incent.' as error_message
from delta.iSolvedOrders_dump d
where d.Amount_raw is null
   or Trim(d.Amount_raw) = ''
   or d.Amount is null

-- s_o_validate_credit_type_iSolved  (INBOUND-ORD-05 REJECT)
insert into Delta(TableName='delta.validation_errors_iSolved_Load_Orders', Unlogged=true, Overwrite=false)
select
  d.source_file,
  d.row_no,
  'REJECT' as category,
  'INBOUND-ORD-05' as reject_reason_no,
  d.Order_Number as order_code,
  d.Item_Number  as item_code,
  'Credit_Type' as error_field,
  Nvl(d.Credit_Type, 'NULL') as field_value,
  'ERROR: Credit_Type is not in (Background Checks, Managed Garnishments).' as error_message
from delta.iSolvedOrders_dump d
where Nvl(d.Credit_Type, '') not in (:v_credit_type_bg, :v_credit_type_mg)

-- s_o_validate_commission_eligible_iSolved  (INBOUND-ORD-06 WARNING)
insert into Delta(TableName='delta.validation_errors_iSolved_Load_Orders', Unlogged=true, Overwrite=false)
select
  d.source_file,
  d.row_no,
  'WARNING' as category,
  'INBOUND-ORD-06' as reject_reason_no,
  d.Order_Number as order_code,
  d.Item_Number  as item_code,
  'Commission_Eligible' as error_field,
  'NULL' as field_value,
  'WARNING: Commission_Eligible is NULL.' as error_message
from delta.iSolvedOrders_dump d
where d.Commission_Eligible is null or Trim(d.Commission_Eligible) = ''


-- -----------------------------------------------------------------------------
-- p_o_stage_orders_iSolved
-- FRD §5.1.3 Data Mapping → prestage_order_item / assignment
-- REJECT rows dropped; WARNING rows still load
-- -----------------------------------------------------------------------------

-- s_o_create_prestage_shells_iSolved
insert into Delta(TableName='delta.prestage_order_item', Unlogged=true, Overwrite=true)
select
  '' as order_code,
  '' as item_code,
  '' as batch_name,
  '' as batch_type,
  '' as product_name,
  '' as customer_name,
  0  as quantity,
  0  as amount,
  '' as amount_unit_type,
  Cast(null as date) as incentive_date,
  Cast(null as date) as order_date,
  '' as order_type,
  '' as credit_type,
  '' as commission_eligible
from Empty()
where '1' = '2'

insert into Delta(TableName='delta.prestage_order_item_assignment', Unlogged=true, Overwrite=true)
select
  '' as order_code,
  '' as item_code,
  '' as employee_id,
  0  as split_amount_pct
from Empty()
where '1' = '2'

-- s_o_build_reject_keys_iSolved
insert into Delta(TableName='delta.iSolvedOrders_reject_keys', Unlogged=true, Overwrite=true)
select distinct order_code || '|' || item_code as oi_key
from delta.validation_errors_iSolved_Load_Orders
where category = 'REJECT'

-- s_o_insert_prestage_order_item_iSolved
insert into delta.prestage_order_item (
  order_code, item_code, batch_name, batch_type, product_name, customer_name,
  quantity, amount, amount_unit_type, incentive_date, order_date, order_type,
  credit_type, commission_eligible
)
select
  d.Order_Number,
  d.Item_Number,
  :v_batch_name_orders,
  :v_batch_type_orders,
  d.Product_Name,
  d.Customer_Name,
  d.Quantity,
  d.Amount,
  Nvl(d.Amount_UnitType, 'USD'),
  d.Incentive_Date,
  d.Order_Date,
  Nvl(NullIf(Trim(d.Order_Type), ''), :v_order_type_orders),
  d.Credit_Type,
  d.Commission_Eligible
from delta.iSolvedOrders_dump d
where d.Order_Number || '|' || d.Item_Number not in (
  select oi_key from delta.iSolvedOrders_reject_keys
)

-- s_o_insert_prestage_order_item_assignment_iSolved
insert into delta.prestage_order_item_assignment (
  order_code, item_code, employee_id, split_amount_pct
)
select
  d.Order_Number,
  d.Item_Number,
  d.Employee_ID,
  Nvl(d.Split_Percentage, 100)
from delta.iSolvedOrders_dump d
where d.Order_Number || '|' || d.Item_Number not in (
  select oi_key from delta.iSolvedOrders_reject_keys
)


-- -----------------------------------------------------------------------------
-- p_o_load_to_incent_staging_iSolved
-- Shared staging insert pattern (same as other Connect order loads)
-- -----------------------------------------------------------------------------

-- s_o_insert_into_staging_valid_prestage_order_assignments
-- insert into staging.order_item_assignment (...)
-- select ... from delta.prestage_order_item_assignment

-- s_o_insert_into_staging_valid_prestage_order
-- insert into staging.order_item (...)
-- select ... from delta.prestage_order_item

-- Flex / custom fields for plan rules (Credit_Type, Commission_Eligible):
-- Map into the tenant's xc_order_stage / order custom fields used by
-- C_004_Background_Checks(_Hold) and C_004_Managed_Garnishments(_Hold).
-- Confirm field names on the tenant before go-live.


-- -----------------------------------------------------------------------------
-- p_o_error_log_and_complete_iSolved_Load_Orders
-- -----------------------------------------------------------------------------

-- s_o_write_process_log_iSolved_Load_Orders
insert into Delta(TableName='delta.process_log_iSolved_Load_Orders', Unlogged=true, Overwrite=true)
select
  source_file, row_no, category, reject_reason_no,
  order_code, item_code, error_field, field_value, error_message
from delta.validation_errors_iSolved_Load_Orders

-- s_o_set_end_email_subject_iSolved_Load_Orders
set v_email_subject *= :v_shared_customer_name
  || ' - Process ' || :v_process_name_iSolved_Load_Orders
  || ' COMPLETED for period ' || :v_period_name
  || ' | staged_orders='
  || (select count(*) from delta.prestage_order_item)
  || ' | reject_warn='
  || (select count(*) from delta.validation_errors_iSolved_Load_Orders)
-- send email e_generic_email


-- =============================================================================
-- After this process: run Incent calc so 50% immediate + 50% Held EG lines exist.
-- Then run p_hold_release_commissions_iSolved when CommissionsRelease file arrives.
-- =============================================================================
