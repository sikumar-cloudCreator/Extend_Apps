-- =============================================================================
-- Process: p_o_upload_process_UploadKerecis_Credit_Invoices
-- FRD:     Coloplast SOW67 FRD Incent V5  §4.7  Load Order Data (Credit Sales)
-- Schema:  ~/Documents/xc_tables ; staging flex on xc_order_stage
--
-- Paste each block into the named Connect step. Iterator body is
-- s_o_read_one_qtd_file_Upload_Credit_KerecisInvoices.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- p_o_set_dynamic_variables  (keep existing shared email / period binds)
-- Then p_o_set_custom_variables_UploadKerecis_Credit_Invoices
-- -----------------------------------------------------------------------------

-- s_o_set_processname_UploadKerecis_Credit_Invoices
-- Set this BEFORE the start email (current process emails the unbound name).
set v_process_name_UploadKerecis_Credit_Invoices *= 'UploadKerecis_Credit_Invoices'
set v_process_name_Upload_Credit_KerecisInvoices *= 'UploadKerecis_Credit_Invoices'

-- s_o_set_batch_size_Upload_Credit_KerecisInvoices
set v_batch_size *= 20000

-- s_o_set_seq_Upload_Credit_KerecisInvoices
set v_seq *= '001'

-- s_o_set_source_file_name_Upload_Credit_KerecisInvoices
set v_filename_Upload_Credit_KerecisInvoices *= 'Invoices_' || :v_period_name || '.csv'

-- s_o_set_reference_file_name_Upload_Credit_KerecisInvoices
set v_reference_file_name *= 'Kerecis_Exceptions_File.xlsx'

-- Mapping table = 'Kerecis Invoices'. Data summary also says 'Kerecis Credit Sales'.
-- Must equal xactly.xc_batch_type.name as configured on the tenant.
set v_credit_batch_type *= 'Kerecis Invoices'

-- s_o_period_start_date / s_o_period_end_date  (already dates — never ToDate these)
set v_period_start_date *= (select start_date from xactly.xc_period where name = :v_period_name)
set v_period_end_date   *= (select end_date   from xactly.xc_period where name = :v_period_name)

-- s_o_set_qtr_start_date_Upload_Credit_KerecisInvoices
set v_qtr_start_date *= (
  select qp.start_date
  from xactly.xc_period mp
  join xactly.xc_period qp on mp.parent_period_id = qp.period_id
  where mp.name = :v_period_name
)

-- s_o_set_year_start_date
set v_year_start_date *= (
  select start_date
  from xactly.xc_period
  where LookupPeriodTypeById(period_type_id_fk) = 'YEARLY'
    and :v_period_start_date between start_date and end_date
)

-- s_o_set_start_email_subject_Upload_Credit_KerecisInvoices
set v_email_subject *= :v_shared_customer_name
  || ' - Process ' || :v_process_name_UploadKerecis_Credit_Invoices
  || ' STARTED for period ' || :v_period_name

-- s_o_send_start_email_Upload_Credit_KerecisInvoices
-- send email e_generic_email


-- -----------------------------------------------------------------------------
-- p_o_reference_structure_check_Upload_Credit_KerecisInvoices
-- Missing file / wrong columns = INBOUND-Invoice-01 FAIL. Abort in Connect.
-- -----------------------------------------------------------------------------

-- s_o_get_reference_columns_Upload_Credit_KerecisInvoices
insert into Delta(TableName='delta.kerecis_exceptions_columns', Unlogged=true, Overwrite=true)
select Uppercase(name) as name
from (describe select * from ReadExcelFile(FilePath='/inbound/reference/' || :v_reference_file_name))

-- s_o_set_reference_actual_cols_Upload_Credit_KerecisInvoices
set v_exc_actual_cols *= (select GatherString(name, ', ') from delta.kerecis_exceptions_columns)

-- s_o_set_exc_cols_present_Upload_Credit_KerecisInvoices
set v_exc_cols_present *= (
  select count(name)
  from delta.kerecis_exceptions_columns
  where name in (
    'SALESPERSON_ID','SALESPERSON_NAME','ROLE','EXCEPTION TYPE','EXCEPTION_RULE',
    'INVOICE','INVOICE_DATE','CUSTOMER_ID','CUSTOMER_NAME','RATE','AMOUNT',
    'COMM AMOUNT','PRODUCT_VOLUME','EFFECTIVE_START_DATE','EFFECTIVE_END_DATE',
    'REASSIGNMENT FROM','REASSIGNMENT TO','EXCEPTION_CUSTOM_FIELD_1','EXCEPTION_CUSTOM_FIELD_2'
  )
)

-- Abort when v_exc_cols_present < 19 (Connect On Condition False → Abort)


-- -----------------------------------------------------------------------------
-- p_o_load_sourcedata_UploadKerecis_Credit_Invoices
-- QTD: customer sends current-month Invoices_<period>.csv; Connect keeps prior
-- months already in delta.CreditSales_Invoice_dump and re-reads any QTD file
-- still on /inbound. Do NOT Overwrite the dump between iterator iterations.
-- -----------------------------------------------------------------------------

-- s_o_create_validation_errorlog_UploadKerecis_Credit_Invoices
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices', Unlogged=true, Overwrite=true)
select
  '' as source_file,
  0  as row_no,
  '' as category,
  '' as data_field,
  '' as field_value,
  '' as error_message
from Empty()
where '1' = '2'

-- s_o_build_qtd_period_list_Upload_Credit_KerecisInvoices
insert into Delta(TableName='delta.qtd_period_list', Unlogged=true, Overwrite=true)
select
  mp.name       as period_name,
  mp.start_date as start_date,
  mp.end_date   as end_date
from xactly.xc_period mp
where mp.parent_period_id = (select parent_period_id from xactly.xc_period where name = :v_period_name)
  and LookupPeriodTypeById(mp.period_type_id_fk) = 'MONTHLY'
  and mp.start_date <= :v_period_end_date

-- s_o_list_inbound_invoice_files_Upload_Credit_KerecisInvoices
insert into Delta(TableName='delta.inbound_invoice_files', Unlogged=true, Overwrite=true)
select name as name
from DirList(Directory='/inbound/', Filter='Invoices_*.csv')

-- Current-period file is mandatory (INBOUND-Invoice-01). Prior months: use file
-- if present, else keep rows already in the dump.
-- s_o_build_qtd_files_to_read_Upload_Credit_KerecisInvoices
insert into Delta(TableName='delta.qtd_files_to_read', Unlogged=true, Overwrite=true)
select q.period_name as period_name
from delta.qtd_period_list q
join delta.inbound_invoice_files f
  on f.name = 'Invoices_' || q.period_name || '.csv'

-- s_o_delete_qtd_periods_being_reread
delete from delta.CreditSales_Invoice_dump
where source_period in (select period_name from delta.qtd_files_to_read)

-- If the dump table does not exist yet, create an empty shell once:
-- insert into Delta(TableName='delta.CreditSales_Invoice_dump', Unlogged=true, Overwrite=true)
-- select ... from Empty() where '1'='2'
-- Do not run that Overwrite on subsequent months — it wipes prior-quarter rows.

-- s_o_create_i_read_qtd_files_Upload_Credit_KerecisInvoices
-- create iterator if not exists i_read_qtd_files_Upload_Credit_KerecisInvoices
--   for step s_o_read_one_qtd_file_Upload_Credit_KerecisInvoices
--   over select distinct period_name as v_file_period from delta.qtd_files_to_read

-- s_o_read_one_qtd_file_Upload_Credit_KerecisInvoices  (iterator body, Overwrite=false)
insert into Delta(TableName='delta.CreditSales_Invoice_dump', Unlogged=true, Overwrite=false)
select
  'Invoices_' || :v_file_period || '.csv' as source_file,
  "Invoice_Number" as Invoice_Number,
  "Invoice_Date"   as Invoice_Date,
  case
    when "Invoice_Date" is null or Trim("Invoice_Date") = '' then null
    when "Invoice_Date" like '%-%' then ToDate("Invoice_Date", 'yyyy-MM-dd')
    else ToDate("Invoice_Date", 'MM/dd/yyyy')
  end as invoice_date_dt,
  "Customer_ID"         as Customer_ID,
  "Customer_Name"       as Customer_Name,
  "Salesperson_ID"      as Salesperson_ID,
  "Salesperson_Name"    as Salesperson_Name,
  "Amount"              as Amount,
  "Currency"            as Currency,
  "Segment"             as Segment,
  "Region"              as Region,
  "Regional_Director"   as Regional_Director,
  "Area"                as Area,
  "Associate"           as Associate,
  "Order_Custom_Field1" as Order_Custom_Field1,
  "Order_Custom_Field2" as Order_Custom_Field2,
  :v_file_period        as source_period,
  SeqNum()              as row_no
from ReadFile(
  FilePath='/inbound/Invoices_' || :v_file_period || '.csv',
  FirstLineNames=true,
  Separator=',',
  Quote='"',
  Trim=true
)

-- s_o_invoke_i_read_qtd_files_Upload_Credit_KerecisInvoices
-- invoke iterator i_read_qtd_files_Upload_Credit_KerecisInvoices

-- Drop the extra dump table UploadKerecis_..._dump — validate/transform the QTD dump only.

-- s_o_read_reference_dump_Upload_Credit_KerecisInvoices
insert into Delta(TableName='delta.kerecis_exceptions_dump', Unlogged=true, Overwrite=true)
select
  "Salesperson_ID"    as Salesperson_ID,
  "Exception Type"    as Exception_Type,
  "Exception_Rule"    as Exception_Rule,
  "Invoice"           as Invoice,
  "Customer_ID"       as Customer_ID,
  "Customer_Name"     as Customer_Name,
  "Reassignment From" as Reassignment_From,
  "Reassignment To"   as Reassignment_To,
  Nvl(ToDate("Effective_Start_Date", 'MM/dd/yyyy'), ToDate('01/01/1900', 'MM/dd/yyyy')) as eff_start,
  Nvl(ToDate("Effective_End_Date",   'MM/dd/yyyy'), ToDate('12/31/2035', 'MM/dd/yyyy')) as eff_end
from ReadExcelFile(FilePath='/inbound/reference/' || :v_reference_file_name)
-- On Error → missing file FAIL INBOUND-Invoice-01

-- s_o_load_valid_employees_Upload_Credit_KerecisInvoices
insert into Delta(TableName='delta.kerecis_valid_employees', Unlogged=true, Overwrite=true)
select distinct p.employee_id as employee_id, p.name as participant_name
from xactly.xc_participant p
where p.employee_id is not null
  and Nvl(p.is_master, '1') = '1'


-- -----------------------------------------------------------------------------
-- p_o_validate_source_file_UploadKerecis_Credit_Invoices_Kerecis_Credit_Invoices
-- REJECT rows are dropped. WARNING rows still load. Do not put WARNs in the
-- same exclusion as REJECT (current clean used row_no from ALL errors).
-- -----------------------------------------------------------------------------

-- s_o_validate_mandatory_invoice_number  INBOUND-Invoice-03 FAIL
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'REJECT', 'Invoice_Number', Nvl(d.Invoice_Number, 'NULL'),
  'INBOUND-Invoice-03: Invoice_Number is null'
from delta.CreditSales_Invoice_dump d
where d.Invoice_Number is null or Trim(d.Invoice_Number) = ''

-- s_o_validate_duplicate_invoice_number  INBOUND-Invoice-03 FAIL (across QTD dump)
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'REJECT', 'Invoice_Number', Nvl(d.Invoice_Number, 'NULL'),
  'INBOUND-Invoice-03: Duplicate Invoice_Number found across QTD period'
from delta.CreditSales_Invoice_dump d
where d.Invoice_Number is not null
  and d.Invoice_Number in (
    select Invoice_Number
    from delta.CreditSales_Invoice_dump
    where Invoice_Number is not null
    group by Invoice_Number
    having count(*) > 1
  )

-- s_o_validate_invoice_date_null_or_future  INBOUND-Invoice-07 FAIL
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'REJECT', 'Invoice_Date', Nvl(d.Invoice_Date, 'NULL'),
  'INBOUND-Invoice-07: Invoice_Date is null, unparseable, or greater than current date'
from delta.CreditSales_Invoice_dump d
where d.invoice_date_dt is null
   or d.invoice_date_dt > CurDate()

-- s_o_validate_mandatory_customer  (Customer_Name + Customer_ID are required)
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'REJECT', 'Customer_Name', Nvl(d.Customer_Name, 'NULL'),
  'Mandatory Data missing: Customer_Name'
from delta.CreditSales_Invoice_dump d
where d.Customer_Name is null or Trim(d.Customer_Name) = ''
union all
select
  d.source_file, d.row_no, 'REJECT', 'Customer_ID', Nvl(d.Customer_ID, 'NULL'),
  'Mandatory Data missing: Customer_ID'
from delta.CreditSales_Invoice_dump d
where d.Customer_ID is null or Trim(d.Customer_ID) = ''

-- s_o_validate_outside_quarter  INBOUND-Invoice-05 WARN + skip
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'SKIP', 'Invoice_Date', Nvl(d.Invoice_Date, 'NULL'),
  'INBOUND-Invoice-05: Invoice_Date is outside the current quarter; row skipped'
from delta.CreditSales_Invoice_dump d
where d.invoice_date_dt is not null
  and (d.invoice_date_dt < :v_qtr_start_date or d.invoice_date_dt > :v_period_end_date)

-- s_o_validate_salesperson_blank  INBOUND-Invoice-06 WARN (Salesperson_ID is NOT mandatory)
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'WARNING', 'Salesperson_ID', Nvl(d.Salesperson_ID, 'NULL'),
  'INBOUND-Invoice-06: Salesperson_ID in Order file is blank'
from delta.CreditSales_Invoice_dump d
where d.Salesperson_ID is null or Trim(d.Salesperson_ID) = ''

-- s_o_validate_salesperson_invalid  INBOUND-Invoice-02 WARN
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'WARNING', 'Salesperson_ID', Nvl(d.Salesperson_ID, 'NULL'),
  'INBOUND-Invoice-02: Salesperson_ID ' || d.Salesperson_ID || ' not found in Incent'
from delta.CreditSales_Invoice_dump d
where d.Salesperson_ID is not null
  and Trim(d.Salesperson_ID) <> ''
  and d.Salesperson_ID not in (select employee_id from delta.kerecis_valid_employees)

-- s_o_validate_segment  INBOUND-Invoice-04 WARN
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'WARNING', 'Segment', Nvl(d.Segment, 'NULL'),
  'INBOUND-Invoice-04: Segment ' || Nvl(d.Segment, 'NULL') || ' is not a valid code (311, 312, 313)'
from delta.CreditSales_Invoice_dump d
where d.Segment is null
   or Trim(d.Segment) not in ('311', '312', '313')

-- s_o_validate_currency  INBOUND-Invoice-08 WARN (default USD at transform)
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'WARNING', 'Currency', Nvl(d.Currency, 'NULL'),
  'INBOUND-Invoice-08: Currency ' || Nvl(d.Currency, 'NULL') || ' not a valid Incent unit type; defaulted to USD'
from delta.CreditSales_Invoice_dump d
where d.Currency is not null
  and Trim(d.Currency) <> ''
  and d.Currency not in (select distinct name from xactly.xc_unit_type)

-- s_o_validate_regional_director  INBOUND-Invoice-09 WARN
-- File example is a name ("Billy Bob"), mapping also treats it as Employee ID.
insert into Delta(TableName='delta.validation_errors_UploadKerecis_Credit_Invoices')
select
  d.source_file, d.row_no, 'WARNING', 'Regional_Director', Nvl(d.Regional_Director, 'NULL'),
  'INBOUND-Invoice-09: Regional_Director ' || Nvl(d.Regional_Director, 'NULL')
    || ' not found in Incent; Regional Director assignment skipped'
from delta.CreditSales_Invoice_dump d
where d.Regional_Director is not null
  and Trim(d.Regional_Director) <> ''
  and d.Regional_Director not in (select employee_id from delta.kerecis_valid_employees)
  and Uppercase(d.Regional_Director) not in (
    select Uppercase(participant_name) from delta.kerecis_valid_employees where participant_name is not null
  )

-- Abort only on REJECT (03 / 07 / mandatory customer). Warnings do not abort.
-- set v_abort_ondata_error *= (select if count(*) > 0 then true else false end
--   from delta.validation_errors_UploadKerecis_Credit_Invoices where category = 'REJECT')

-- s_o_load_clean_UploadKerecis_Credit_Invoices
-- Binds v_qtr_start_date / v_period_end_date are already dates. Do not ToDate them.
insert into Delta(TableName='delta.UploadKerecis_Credit_Invoices_Kerecis_Credit_Invoices_clean', Unlogged=true, Overwrite=true)
select
  d.Invoice_Number,
  d.invoice_date_dt as Invoice_Date,
  d.Customer_ID,
  d.Customer_Name,
  d.Salesperson_ID,
  d.Salesperson_Name,
  ToDecimal(Nvl(d.Amount, '0')) as Amount,
  d.Currency,
  d.Segment,
  d.Region,
  d.Regional_Director,
  d.Area,
  d.Associate,
  d.Order_Custom_Field1,
  d.Order_Custom_Field2,
  d.source_period,
  d.source_file,
  d.row_no
from delta.CreditSales_Invoice_dump d
where d.invoice_date_dt is not null
  and d.invoice_date_dt >= :v_qtr_start_date
  and d.invoice_date_dt <= :v_period_end_date
  and (d.source_file || '_' || d.row_no) not in (
    select distinct source_file || '_' || row_no
    from delta.validation_errors_UploadKerecis_Credit_Invoices
    where category in ('REJECT', 'SKIP')
  )


-- -----------------------------------------------------------------------------
-- prestaging shells (unchanged)
-- -----------------------------------------------------------------------------

-- s_o_create_prestage_order_item
insert into Delta(TableName='delta.prestage_order_item', Unlogged=true, Overwrite=true)
select * from staging.order_item where '1' = '2'

-- s_o_create_prestage_order_item_assignment
insert into Delta(TableName='delta.prestage_order_item_assignment', Unlogged=true, Overwrite=true)
select * from staging.order_item_assignment where '1' = '2'

-- s_o_shared_create_archive_error_log
insert into Delta(TableName='delta.archive_order_item_validation_error', Overwrite=true, Unlogged=true)
select * from staging.order_item_validation_error where '1' = '2'

-- s_o_shared_create_process_log
insert into Delta(TableName='delta.process_log', Unlogged=true, Overwrite=true)
select
  CurDate() as process_log_creation_date,
  :v_period_name as processing_period,
  '' as category, '' as order_code, '' as item_code, '' as error_field, '' as reject_reason
from Empty()
where '1' = '2'


-- -----------------------------------------------------------------------------
-- p_o_transform_UploadKerecis_Credit_Invoices
-- Exception order: 02 realign employee → 01 split on resolved employee → 03 hold.
-- Exception 02 FRD: match Reassignment_From, NEW employee = Reference.Salesperson_ID
--   (current code used Reassignment_To — that is the discrepancy).
-- Quantity left blank per mapping. Batch SEQ is appended only at staging insert.
-- -----------------------------------------------------------------------------

-- s_o_transform_UploadKerecis_Credit_Invoices_Kerecis_Credit_Invoices
insert into Delta(TableName='delta.UploadKerecis_Credit_Invoices_Kerecis_Credit_Invoices_transform', Unlogged=true, Overwrite=true)
select
  x.Invoice_Number as order_code,
  x.Customer_Name || '_' || Nvl(x.Salesperson_ID, 'NA') as item_code,
  'C_' || :v_period_name || '_Kerecis_Data' as batch_name,
  :v_credit_batch_type as batch_type_name,
  x.Amount as amount,
  case
    when x.Currency is not null
     and x.Currency in (select distinct name from xactly.xc_unit_type)
    then x.Currency
    else 'USD'
  end as amount_unit_type_name,
  x.Invoice_Date as incentive_date,
  x.Invoice_Date as order_date,
  case
    when e3.Exception_Type is not null then 'NON-Commissionable Sales'
    else 'Credit Sales'
  end as order_type_name,
  x.Customer_ID as CustomerID,
  x.resolved_employee_id as employee_id,
  case
    when x.resolved_employee_id is not null
     and e1.Exception_Type is not null then 50
    when x.resolved_employee_id is not null then 100
    else null
  end as split_amount_pct,
  x.resolved_rd_id as employee_id1,
  case when x.resolved_rd_id is not null then 100 else null end as split_amount_pct1,
  x.Customer_Name as customer_name,
  x.Segment as Segment,
  x.Region as Ker_Region,
  x.Regional_Director as regional_director,
  x.Area as Area,
  x.Associate as associate,
  x.Order_Custom_Field1 as Order_Custom_Field1,
  x.Order_Custom_Field2 as Order_Custom_Field2,
  :v_period_name as period_name
from (
  select
    I.*,
    case
      when e2.Salesperson_ID is not null
       and e2.Salesperson_ID in (select employee_id from delta.kerecis_valid_employees)
      then e2.Salesperson_ID
      when I.Salesperson_ID in (select employee_id from delta.kerecis_valid_employees)
      then I.Salesperson_ID
      else null
    end as resolved_employee_id,
    case
      when I.Regional_Director in (select employee_id from delta.kerecis_valid_employees)
      then I.Regional_Director
      else (
        select Max(v.employee_id)
        from delta.kerecis_valid_employees v
        where Uppercase(v.participant_name) = Uppercase(I.Regional_Director)
      )
    end as resolved_rd_id
  from delta.UploadKerecis_Credit_Invoices_Kerecis_Credit_Invoices_clean I
  left join delta.kerecis_exceptions_dump e2
    on e2.Invoice = I.Invoice_Number
   and e2.Reassignment_From = I.Salesperson_ID
   and e2.Exception_Type = 'Invoice Realignment'
   and I.Invoice_Date >= e2.eff_start
   and I.Invoice_Date <= e2.eff_end
) x
left join delta.kerecis_exceptions_dump e1
  on e1.Invoice = x.Invoice_Number
 and e1.Salesperson_ID = x.resolved_employee_id
 and e1.Customer_Name = x.Customer_Name
 and e1.Exception_Type = 'Commission Split'
 and x.Invoice_Date >= e1.eff_start
 and x.Invoice_Date <= e1.eff_end
left join delta.kerecis_exceptions_dump e3
  on e3.Customer_Name = x.Customer_Name
 and e3.Exception_Type = 'Credit Hold'
 and x.Invoice_Date >= e3.eff_start
 and x.Invoice_Date <= e3.eff_end


-- -----------------------------------------------------------------------------
-- p_o_insert_orders_UploadKerecis_Credit_Invoices
-- Flex names from xc_order_stage: Segment, Ker_Region, regional_director, Area,
-- associate, Order_Custom_Field1/2. CustomerID = source Customer_ID (string).
-- Include order_date (current insert omitted it). Quantity left blank.
-- -----------------------------------------------------------------------------

-- s_o_insert_to_prestage_order_item_UploadKerecis_Credit_Invoices
insert into delta.prestage_order_item (
  order_code, item_code, batch_name, batch_type_name, customer_name,
  amount, amount_unit_type_name, incentive_date, order_date, order_type_name,
  Segment, Ker_Region, regional_director, Area, associate,
  Order_Custom_Field1, Order_Custom_Field2, CustomerID, period_name
)
select distinct
  order_code, item_code, batch_name, batch_type_name, customer_name,
  amount, amount_unit_type_name, incentive_date, order_date, order_type_name,
  Segment, Ker_Region, regional_director, Area, associate,
  Order_Custom_Field1, Order_Custom_Field2, CustomerID, period_name
from delta.UploadKerecis_Credit_Invoices_Kerecis_Credit_Invoices_transform

-- s_o_insert_to_prestage_order_item_assignment_UploadKerecis_Credit_Invoices
-- Two overlapping 100% directs: selling rep + Regional Director (FRD).
-- Invalid / blank IDs are already null — assignment is skipped, order still loads.
insert into delta.prestage_order_item_assignment (order_code, item_code, employee_id, split_amount_pct)
select distinct order_code, item_code, employee_id, split_amount_pct
from delta.UploadKerecis_Credit_Invoices_Kerecis_Credit_Invoices_transform
where employee_id is not null
  and split_amount_pct is not null
union
select distinct order_code, item_code, employee_id1, split_amount_pct1
from delta.UploadKerecis_Credit_Invoices_Kerecis_Credit_Invoices_transform
where employee_id1 is not null
  and split_amount_pct1 is not null
-- On Error → p_o_shared_delete_staging_tables


-- -----------------------------------------------------------------------------
-- p_o_order_validations_UploadKerecis_Credit_Invoices
-- Replace every "not inn" with NOT IN. Employee check is WARN-path at source;
-- remaining invalid assignment IDs still REJECT here.
-- -----------------------------------------------------------------------------

-- s_o_set_order_item_field_list
set v_order_item_field_list *= select GatherString(name, ',')
from (describe select * from staging.order_item)
where name <> 'batch_name'

-- s_o_order_validate_mandatory_fields  (unchanged logic)
-- s_o_order_validate_batch_type        vs xactly.xc_batch_type.name
-- s_o_order_validate_amount_unit_type  vs xactly.xc_unit_type.name
-- s_o_order_validate_order_type        vs xactly.xc_order_type.name

-- s_o_order_validate_employee_id
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

-- s_o_order_validate_duplicates
insert into Delta(TableName='delta.process_log')
select
  CurDate() as process_log_creation_date,
  :v_period_name as processing_period,
  'REJECT' as category,
  order_code, item_code,
  '' as error_field,
  'Duplicate orders' as reject_reason
from delta.prestage_order_item
group by order_code, item_code
having count(*) > 1

-- s_o_order_validate_missing_assignments
insert into Delta(TableName='delta.process_log')
select
  CurDate() as process_log_creation_date,
  :v_period_name as processing_period,
  'REJECT' as category,
  order_code, item_code,
  '' as error_field,
  'Assignment missing' as reject_reason
from delta.prestage_order_item
where order_code || item_code not in (
  select distinct order_code || item_code
  from delta.prestage_order_item_assignment
  where order_code || item_code not in (
    select distinct order_code || item_code from delta.process_log where category = 'REJECT'
  )
)
-- FRD: order still loads with no assignment when salesperson AND RD are both invalid.
-- If that is required, delete this step or restrict it to rows that had a resolvable ID.

-- s_o_insert_into_staging_valid_prestage_order_assignments
insert into staging.order_item_assignment (order_code, item_code, employee_id, split_amount_pct)
select order_code, item_code, employee_id, split_amount_pct
from delta.prestage_order_item_assignment
where order_code || item_code not in (
  select distinct order_code || item_code from delta.process_log where category = 'REJECT'
)

-- s_o_insert_into_staging_valid_prestage_order
-- SEQ once here. Transform batch_name must NOT already contain _001.
insert into staging.order_item ({:v_order_item_field_list}, batch_name)
select {:v_order_item_field_list}, batch_name || '_' || :v_seq as batch_name
from delta.prestage_order_item
where order_code || item_code not in (
  select distinct order_code || item_code from delta.process_log where category = 'REJECT'
)

-- p_o_shared_upload_orders  (keep; fix remaining not inn in archive/copy temps)
-- s_o_copy_valid_stage_order_item_temp
--   ... where order_code||item_code not in (select distinct order_code||item_code from staging.order_item_validation_error)
-- s_o_copy_valid_stage_order_item_assignment_temp  same NOT IN
