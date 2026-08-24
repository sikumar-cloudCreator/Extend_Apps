-- =============================================================================
-- Process: p_hold_release_commissions_iSolved
-- FRD:     FRD_iSolved_2026_v2  §5.2 Hold and Release Commissions <SFTP>
--          §4.2 / §6.1–6.2  50% immediate / 50% held until SFTP release
--
-- Adapted from kickoff-date release pattern (tmp_held_commission →
-- tmp_final_comm_release → prestage_release_commission), but:
--   * Trigger = SFTP CommissionsRelease<MMYYYY>.csv (NOT SFDC Kickoff_Date)
--   * Match   = Order_Number + Item_Number (FRD §5.2.3)
--   * Rate    = fixed 100% of the Held commission line
--              (calc already applied *0.50 into Held earning groups)
--   * EG filter = Background Checks / Managed Garnishments Held Commissions
--
-- Processing order (FRD §5.3.2): Load Orders → Hold and Release Commissions
-- Paste each block into the named Connect step.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- p_o_set_custom_variables_iSolved_Hold_Release
-- -----------------------------------------------------------------------------

-- s_o_set_process_name_iSolved_Hold_Release
set v_process_name_iSolved_Hold_Release *= 'iSolved_Hold_Release_Commissions'

-- s_o_set_period_dates_iSolved_Hold_Release
set v_period_start_date *= (select start_date from xactly.xc_period where name = :v_period_name)
set v_period_end_date   *= (select end_date   from xactly.xc_period where name = :v_period_name)

-- Processing window for release staging (open / current period end)
set v_processing_start_date *= :v_period_start_date
set v_processing_end_date   *= :v_period_end_date

-- FRD file name: CommissionsRelease<MMYYYY>.csv  (e.g. JAN-2026 → 012026)
-- s_o_set_mmYYYY_iSolved_Hold_Release
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

-- s_o_set_release_filename_iSolved_Hold_Release
set v_filename_CommissionsRelease *= 'CommissionsRelease' || :v_mmYYYY || '.csv'

-- Held earning groups (FRD §5.2.4) — only these are released by this process
set v_eg_bg_held *= 'Background Checks Held Commissions'
set v_eg_mg_held *= 'Managed Garnishments Held Commissions'

-- Release % of the Held commission line. Calc rules already wrote 50% into
-- these Held EGs; SFTP match releases that held line in full → 100.
set v_release_pct_of_held *= 100.0

-- Optional: Incent release composite id segment (tenant-specific). Confirm
-- against existing release imports before go-live.
set v_release_id_token *= '1581'

-- s_o_set_start_email_subject_iSolved_Hold_Release
set v_email_subject *= :v_shared_customer_name
  || ' - Process ' || :v_process_name_iSolved_Hold_Release
  || ' STARTED for period ' || :v_period_name
-- send email e_generic_email


-- -----------------------------------------------------------------------------
-- p_o_file_presence_iSolved_Hold_Release
-- INBOUND-REL-01 missing file / INBOUND-REL-02 more than one file = FAIL (abort)
-- -----------------------------------------------------------------------------

-- s_o_list_inbound_release_files_iSolved
insert into Delta(TableName='delta.inbound_release_files', Unlogged=true, Overwrite=true)
select name as name
from DirList(Directory='/inbound/', Filter='CommissionsRelease*.csv')

-- s_o_count_release_files_iSolved
set v_release_file_count *= (
  select count(*)
  from delta.inbound_release_files
  where name = :v_filename_CommissionsRelease
)

set v_release_file_any_count *= (
  select count(*) from delta.inbound_release_files
)

-- Connect conditions (configure On Condition False → Abort + error email):
--   INBOUND-REL-01: v_release_file_count = 1   (exact period file present)
--   INBOUND-REL-02: v_release_file_any_count <= 1
--     OR only the expected filename is present for the run


-- -----------------------------------------------------------------------------
-- p_o_read_release_file_iSolved_Hold_Release
-- FRD §5.2.2 Source Fields
-- -----------------------------------------------------------------------------

-- s_o_read_commissions_release_dump_iSolved
insert into Delta(TableName='delta.CommissionsRelease_dump', Unlogged=true, Overwrite=true)
select
  :v_filename_CommissionsRelease as source_file,
  Trim("Order_Number")  as Order_Number,
  Trim("Item_Number")   as Item_Number,
  Trim("Employee_ID")   as Employee_ID,
  Trim("Credit_Type")   as Credit_Type,
  ToDecimal(Nvl(Trim("Release_Flag"), '0')) as Release_Flag,
  case
    when "Release_Date" is null or Trim("Release_Date") = '' then null
    when "Release_Date" like '%-%' then ToDate("Release_Date", 'yyyy-MM-dd')
    else ToDate("Release_Date", 'MM/dd/yyyy')
  end as Release_Date,
  SeqNum() as row_no
from ReadFile(
  FilePath='/inbound/' || :v_filename_CommissionsRelease,
  FirstLineNames=true,
  Separator=',',
  TextQualifier='"',
  Trim=true
)


-- -----------------------------------------------------------------------------
-- p_o_validate_release_file_iSolved_Hold_Release
-- FRD §5.2.5  INBOUND-REL-03 / 04 / 05
-- -----------------------------------------------------------------------------

-- s_o_init_validation_errors_iSolved_Hold_Release
insert into Delta(TableName='delta.validation_errors_iSolved_Hold_Release', Unlogged=true, Overwrite=true)
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

-- s_o_validate_release_flag_iSolved  (INBOUND-REL-05 WARNING — skip row)
insert into Delta(TableName='delta.validation_errors_iSolved_Hold_Release', Unlogged=true, Overwrite=false)
select
  d.source_file,
  d.row_no,
  'WARNING' as category,
  'INBOUND-REL-05' as reject_reason_no,
  d.Order_Number as order_code,
  d.Item_Number  as item_code,
  'Release_Flag' as error_field,
  ToString(d.Release_Flag) as field_value,
  'WARNING: Release_Flag is not equal to 1; record skipped.' as error_message
from delta.CommissionsRelease_dump d
where Nvl(d.Release_Flag, 0) <> 1

-- s_o_clean_release_rows_iSolved
-- Keep only Release_Flag = 1 for matching / staging
insert into Delta(TableName='delta.CommissionsRelease_clean', Unlogged=true, Overwrite=true)
select
  d.source_file,
  d.Order_Number,
  d.Item_Number,
  d.Employee_ID,
  d.Credit_Type,
  d.Release_Flag,
  Nvl(d.Release_Date, :v_processing_end_date) as Release_Date,
  d.row_no
from delta.CommissionsRelease_dump d
where Nvl(d.Release_Flag, 0) = 1


-- -----------------------------------------------------------------------------
-- p_o_load_held_commissions_iSolved_Hold_Release
-- Mirror of sample s_kickoff_date_load_held_commission — Incent held rows only
-- -----------------------------------------------------------------------------

-- s_o_load_held_commission_iSolved
insert into Delta(TableName='delta.tmp_held_commission', Overwrite=true, Unlogged=true)
select
  coi.batch_name,
  comm.order_code,
  comm.item_code,
  comm.commission_id,
  comm.earning_group_name,
  comm.participant_id,
  part.employee_id,
  comm.incentive_date,
  coi.deal_type,
  comm.release_date,
  part.termination_date as termdate,
  comm.customer_name,
  comm.held_amount,
  ut.name as held_amount_unit_type,
  comm.amount as commission_amount,
  comm.amount_display_symbol,
  comm.released_amount,
  comm.credit_amount as incentive_amount,
  comm.order_item_id,
  part.name as participant_name,
  comm.reason_code_name,
  per.end_date,
  per.name as period_name,
  comm.estimated_rel_date,
  coi.business_unit,
  coi.Original_Opportunity_ID
from xactly.xc_commission comm
join xactly.xc_participant part
  on comm.participant_id = part.participant_id
join xactly.xc_comp_order_item coi
  on comm.order_code = coi.order_code
 and comm.item_code  = coi.item_code
join xactly.xc_period per
  on comm.period_id = per.period_id
join xactly.xc_unit_type ut
  on comm.amount_unit_type_id = ut.unit_type_id
where comm.is_held = '1'
  and comm.held_amount > 0
  and per.end_date <= :v_processing_end_date
  and per.name not like 'Q%'
  and comm.earning_group_name in (:v_eg_bg_held, :v_eg_mg_held)


-- -----------------------------------------------------------------------------
-- p_o_match_release_to_held_iSolved
-- FRD §5.2.3: Order Code = Order_Number AND Item Code = Item_Number
-- -----------------------------------------------------------------------------

-- s_o_match_held_to_release_iSolved
insert into Delta(TableName='delta.tmp_held_matched_release', Overwrite=true, Unlogged=true)
select distinct
  hc.*,
  rel.Release_Date as file_release_date,
  rel.Employee_ID  as file_employee_id,
  rel.Credit_Type  as file_credit_type,
  rel.row_no       as release_row_no
from delta.tmp_held_commission hc
join delta.CommissionsRelease_clean rel
  on hc.order_code = rel.Order_Number
 and hc.item_code  = rel.Item_Number
-- Optional Employee_ID on file: when present, tighten match
where (rel.Employee_ID is null or Trim(rel.Employee_ID) = '' or hc.employee_id = rel.Employee_ID)

-- s_o_validate_order_item_not_found_iSolved  (INBOUND-REL-03 REJECT)
insert into Delta(TableName='delta.validation_errors_iSolved_Hold_Release', Unlogged=true, Overwrite=false)
select
  rel.source_file,
  rel.row_no,
  'REJECT' as category,
  'INBOUND-REL-03' as reject_reason_no,
  rel.Order_Number as order_code,
  rel.Item_Number  as item_code,
  'Order_Number+Item_Number' as error_field,
  rel.Order_Number || '|' || rel.Item_Number as field_value,
  'ERROR: Order Number + Item Number combination not found in Incent.' as error_message
from delta.CommissionsRelease_clean rel
where not exists (
  select 1
  from xactly.xc_comp_order_item coi
  where coi.order_code = rel.Order_Number
    and coi.item_code  = rel.Item_Number
)

-- s_o_validate_not_held_iSolved  (INBOUND-REL-04 REJECT)
-- Order+Item exists in Incent but no matching held commission in scope
insert into Delta(TableName='delta.validation_errors_iSolved_Hold_Release', Unlogged=true, Overwrite=false)
select
  rel.source_file,
  rel.row_no,
  'REJECT' as category,
  'INBOUND-REL-04' as reject_reason_no,
  rel.Order_Number as order_code,
  rel.Item_Number  as item_code,
  'Held status' as error_field,
  rel.Order_Number || '|' || rel.Item_Number as field_value,
  'ERROR: Matching commission is not in Held status.' as error_message
from delta.CommissionsRelease_clean rel
where exists (
  select 1
  from xactly.xc_comp_order_item coi
  where coi.order_code = rel.Order_Number
    and coi.item_code  = rel.Item_Number
)
and not exists (
  select 1
  from delta.tmp_held_commission hc
  where hc.order_code = rel.Order_Number
    and hc.item_code  = rel.Item_Number
    and (rel.Employee_ID is null or Trim(rel.Employee_ID) = '' or hc.employee_id = rel.Employee_ID)
)


-- -----------------------------------------------------------------------------
-- p_o_build_final_comm_release_iSolved
-- Mirror of sample s_tmp_final_comm_release_kickoff_date — fixed 50/50 release
-- -----------------------------------------------------------------------------

-- s_o_tmp_final_comm_release_iSolved
insert into Delta(TableName='delta.tmp_final_comm_release', Overwrite=true)
select distinct
  hc.order_item_id
    || '-' || hc.participant_id
    || '-' || :v_release_id_token
    || '-' || hc.commission_id                        as commission_id,
  Round(:v_release_pct_of_held, 4)                    as perc_original_to_release,
  hc.earning_group_name                               as earning_group,
  hc.participant_name                                 as person,
  hc.order_code                                       as order_code,
  hc.item_code                                        as item_code,
  hc.customer_name                                    as customer,
  hc.incentive_amount                                 as order_item_amount,
  hc.amount_display_symbol                            as commission_unit_type,
  if hc.commission_amount is not null then hc.commission_amount else 0 end
                                                      as original_commission,
  (Nvl(hc.commission_amount, 0) * :v_release_pct_of_held) / 100.0
                                                      as released_commission,
  hc.held_amount                                      as held_commission,
  Nvl(hc.file_release_date, :v_processing_end_date)   as releaseDate
from delta.tmp_held_matched_release hc


-- -----------------------------------------------------------------------------
-- p_o_split_and_stage_release_iSolved
-- Mirror of sample split_filenumber + prestage_release_commission
-- -----------------------------------------------------------------------------

-- s_o_tmp_final_comm_release_split_filenumber_iSolved
insert into Delta(TableName='delta.tmp_final_comm_release_split_filenumber', Overwrite=true, Unlogged=true)
select
  distinct
  fcr.commission_id,
  MinValue(SUM(fcr.perc_original_to_release), 100) as perc_original_to_release,
  fcr.earning_group,
  fcr.person,
  fcr.order_code,
  fcr.item_code,
  fcr.customer,
  fcr.order_item_amount,
  fcr.commission_unit_type,
  fcr.original_commission,
  fcr.released_commission,
  fcr.held_commission,
  fcr.releaseDate,
  (((SeqNum() - 1) / 10000) + 1) as filenumber
from delta.tmp_final_comm_release fcr

-- s_o_prestage_release_commission_iSolved
insert into Delta(TableName='delta.prestage_release_commission', Unlogged=true, Overwrite=true)
select distinct
  commission_id,
  if (perc_original_to_release >= 100) then 100.00 else perc_original_to_release end
    as percent_original_to_release,
  earning_group,
  person as person,
  order_code,
  item_code,
  customer,
  order_item_amount,
  commission_unit_type,
  original_commission,
  released_commission,
  held_commission
from delta.tmp_final_comm_release_split_filenumber


-- -----------------------------------------------------------------------------
-- p_o_error_log_and_archive_iSolved_Hold_Release
-- Unmatched / not-held / bad flag rows land in validation_errors (FRD §5.2.3)
-- -----------------------------------------------------------------------------

-- s_o_write_process_log_iSolved_Hold_Release
insert into Delta(TableName='delta.process_log_iSolved_Hold_Release', Unlogged=true, Overwrite=true)
select
  source_file,
  row_no,
  category,
  reject_reason_no,
  order_code,
  item_code,
  error_field,
  field_value,
  error_message
from delta.validation_errors_iSolved_Hold_Release

-- Optional: export error log to /outbound for ops review
-- SaveCSV(
--   select * from delta.process_log_iSolved_Hold_Release,
--   FilePath='/outbound/iSolved_Hold_Release_errors_' || :v_period_name || '.csv'
-- )

-- s_o_set_end_email_subject_iSolved_Hold_Release
set v_email_subject *= :v_shared_customer_name
  || ' - Process ' || :v_process_name_iSolved_Hold_Release
  || ' COMPLETED for period ' || :v_period_name
  || ' | released_rows='
  || (select count(*) from delta.prestage_release_commission)
  || ' | reject_warn='
  || (select count(*) from delta.validation_errors_iSolved_Hold_Release)
-- send email e_generic_email


-- =============================================================================
-- Connect follow-on (tenant standard — not rewritten here):
--   1. Load delta.prestage_release_commission into Incent Release Commission
--      staging / import (same shared step used by kickoff release).
--   2. Archive / move CommissionsRelease<MMYYYY>.csv off /inbound.
-- =============================================================================
