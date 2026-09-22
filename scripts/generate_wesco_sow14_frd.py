#!/usr/bin/env python3
"""
Generate Wesco SOW-14 Functional Requirements Document (Connect + Incent).

Baseline: Wesco SOW16 FRD v2
- Keep Incent plan design as-is with renames: EES -> Wesco, DDP -> DataLake, 2025 -> 2026, SOW16 -> SOW-14
- Replace Section 4 (DATA) with DataLake SFTP load mapping + Connect UploadDataLake pipeline
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor, Twips


OUT_DIR = Path("/workspace/docs/frd")
ARTIFACT_DIR = Path("/opt/cursor/artifacts")
OUT_NAME = "Wesco_SOW14_FRD_v1_Connect_Incent.docx"

HEADER_FILL = "F5E6D3"
HEADER_FILL_ALT = "D9E2F3"
ACCENT = RGBColor(0x1F, 0x4E, 0x79)


def set_cell_shading(cell, fill: str) -> None:
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def set_run_font(run, size=10, bold=False, color=None, name="Century Gothic"):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def add_para(doc, text="", style=None, size=10, bold=False, space_after=6, align=None):
    p = doc.add_paragraph(style=style) if style else doc.add_paragraph()
    if align is not None:
        p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(0)
    if text:
        run = p.add_run(text)
        set_run_font(run, size=size, bold=bold)
    return p


def add_heading_custom(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        set_run_font(run, size={1: 16, 2: 13, 3: 11}.get(level, 11), bold=True, color=ACCENT)
    return p


def set_table_widths(table, widths):
    for row in table.rows:
        for i, w in enumerate(widths):
            if i < len(row.cells):
                row.cells[i].width = Inches(w)


def fill_table(table, rows, header=True, header_fill=HEADER_FILL, font_size=9):
    for ri, row_data in enumerate(rows):
        row = table.rows[ri]
        for ci, val in enumerate(row_data):
            cell = row.cells[ci]
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.space_before = Pt(0)
            run = p.add_run("" if val is None else str(val))
            is_header = header and ri == 0
            set_run_font(run, size=font_size, bold=is_header)
            if is_header:
                set_cell_shading(cell, header_fill)


def add_table(doc, rows, widths=None, header=True, header_fill=HEADER_FILL, font_size=9):
    cols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    fill_table(table, rows, header=header, header_fill=header_fill, font_size=font_size)
    if widths:
        set_table_widths(table, widths)
    doc.add_paragraph()
    return table


def add_kv_table(doc, pairs, widths=(2.5, 4.5)):
    rows = [[k, v] for k, v in pairs]
    return add_table(doc, rows, widths=list(widths), header=False, font_size=9)


def configure_styles(doc):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Century Gothic"
    normal.font.size = Pt(10)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Century Gothic")


def build_cover(doc):
    for _ in range(4):
        doc.add_paragraph()
    add_para(doc, "Xactly Corporation", size=18, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18)
    add_para(doc, "Functional Requirements", size=22, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=12)
    add_para(doc, "Wesco", size=20, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    add_para(doc, "SOW-14", size=18, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
    add_para(
        doc,
        "Connect & Incent — Plan Year 2026",
        size=12,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=24,
    )
    add_para(
        doc,
        "DataLake Order Load | Flat Rate Commission | Clawback Commission",
        size=10,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        space_after=6,
    )
    doc.add_page_break()


def build_history(doc):
    add_para(doc, "DOCUMENT HISTORY", size=14, bold=True, space_after=10)
    add_table(
        doc,
        [
            ["Version", "Date", "SOW / CO", "Author(s)", "Comments / Summary of Updates"],
            [
                "0.1",
                "09/22/2026",
                "SOW-14",
                "K Sai Kiran / Sireesh Kumar",
                "Initial SOW-14 FRD from Wesco SOW16 baseline. Plan year 2026. "
                "EES renamed to Wesco; DDP renamed to DataLake. "
                "Section 4 (DATA) rewritten for DataLake SFTP load and Connect pipeline "
                "p_o_upload_process_UploadDataLake. People/approvers updated.",
            ],
        ],
        widths=[0.8, 1.0, 1.0, 1.6, 2.8],
    )
    doc.add_page_break()


def build_intro(doc):
    add_heading_custom(doc, "1. INTRODUCTION", 1)
    add_para(
        doc,
        "The purpose of this document is to provide a common understanding between Xactly and "
        "Wesco SOW-14 regarding how the variable incentives are calculated for the 2026 plan year, "
        "and how source order data is loaded from SFTP into Xactly Incent via Xactly Connect.",
    )
    add_para(
        doc,
        "This Functional Requirements Document (FRD) covers both Connect (inbound DataLake file "
        "processing, validation, TMCA crediting prep, and Incent order upload) and Incent "
        "(plan components, crediting, commissions, design objects).",
    )
    add_para(
        doc,
        "The final version of this document will be routed electronically for approval via DocuSign.",
    )


def build_success(doc):
    add_heading_custom(doc, "2. PROJECT SUCCESS FACTORS", 1)
    add_table(
        doc,
        [
            ["Success Factor", "Desired State", "How will it be measured?"],
            [
                "Successfully implement and automate the calculation of the compensation plans",
                "All plans paid from Incent with automated nightly data runs",
                "Successful UAT and rollout to sales rep by date MM/DD/YYYY",
            ],
            [
                "Increase transparency and visibility for sales representatives and sales managers",
                "End users able to view customized reports in Incent",
                "Key metrics include customization of reports and PODs and including a few sales "
                "representatives in the reporting portion of UAT to give feedback.",
            ],
            [
                "Increase auditability of compensations calculations, include effective dating and review / sign-off",
                "Monthly review process of payroll file, use of audit functionality within the system for regular checks",
                "Key metrics include UAT test cases to view audit logs of different objects in Incent and eDoc routings.",
            ],
            [
                "Implement Incent as a “one-stop shop for commissions information”",
                "End users able to review and sign plan documents, see all monthly commissions information, and successfully log into the system",
                "Key metrics include implementing plan doc routing and approval, customizing reports and PODs, and a successful UAT and rollout to the sales reps.",
            ],
            [
                "Automate DataLake order load via Connect from SFTP",
                "Daily DataLake files land on SFTP, are validated, credited via TMCA where applicable, and uploaded to Incent as Order Type DataLake",
                "Successful Connect runs for UploadDataLake with validation error logs and queue of downstream process groups",
            ],
        ],
        widths=[2.2, 2.4, 2.6],
    )


def build_overview(doc):
    add_heading_custom(doc, "3. OVERVIEW", 1)
    add_heading_custom(doc, "3.1 Plan Summary", 2)
    add_para(
        doc,
        "The plan summary represents Wesco’s 2026 plans that are in scope for this project.",
    )
    add_table(
        doc,
        [
            [
                "Plan Number",
                "Plan Name",
                "Title Name(s)",
                "Approximate Number of Payees on Plan",
                "Comments",
            ],
            ["01", "2026 Wesco Flat Rate Plan", "Wesco ISR, Wesco OSR", "", ""],
        ],
        widths=[1.0, 2.0, 1.6, 1.8, 1.0],
    )

    add_heading_custom(doc, "3.2 Plan Component Summary", 2)
    add_para(
        doc,
        "This section defines all of Wesco’s required plan components. Relevant attributes for each "
        "component are listed below.",
    )
    add_table(
        doc,
        [
            [
                "Component Number",
                "Component Name",
                "Data Load Frequency",
                "Commission Calculation Frequency / Level of Detail",
                "Payment Frequency",
                "Holds",
                "Comments / Hold Release Schedule",
            ],
            ["01", "Flat Rate Commission", "Daily", "Monthly / Per Credit", "Monthly", "No", ""],
            ["02", "Clawback Commission", "Weekly", "Monthly / Per Credit", "Monthly", "No", ""],
        ],
        widths=[0.9, 1.4, 1.0, 1.6, 1.0, 0.7, 1.2],
        font_size=8,
    )

    add_heading_custom(doc, "3.3 Crediting Design", 2)
    add_para(
        doc,
        "There are two primary ways to assign a transaction to an employee: directly or indirectly. "
        "Within Xactly Incent, this process of allocating transactions to an employee is referred to "
        "as “crediting” an order.",
    )
    add_para(doc, "Direct Credit Assignment (D)", bold=True, space_after=2)
    add_para(
        doc,
        "Direct assignment is accomplished by tagging the employee’s Employee ID on the transaction "
        "line itself.",
    )
    add_para(doc, "Indirect Credit Assignment via Hierarchy aka “Rollup” (H)", bold=True, space_after=2)
    add_para(
        doc,
        "Indirect assignment uses the employee hierarchy for rollup credit. For instance, a manager "
        "may inherit “credit” for the transaction from an employee below her, in the hierarchy.",
    )
    add_para(
        doc,
        "Indirect Credit Assignment via Named Relationship aka “Rollover” (N)",
        bold=True,
        space_after=2,
    )
    add_para(
        doc,
        "Indirect credits can also be created by rolling revenue to another person via a relationship "
        "other than the hierarchy. This is called a “rollover.”",
    )
    add_para(doc, "Listed below are the Components by Plan and their crediting methods:")
    add_table(
        doc,
        [
            ["Component", "2026 Flat Rate Plan"],
            ["Flat Rate Component", "D"],
            ["Clawback Commission", "D"],
        ],
        widths=[2.5, 2.5],
    )
    add_para(doc, "A indicates Aggregate Credit from an aggregation step")
    add_para(doc, "( ) indicates credits that are not generating commissions on the associated plan")


def build_data_section(doc):
    add_heading_custom(doc, "4. DATA", 1)
    add_para(
        doc,
        "This section defines all of Wesco’s source data that will be loaded into Incent for SOW-14. "
        "The primary inbound order feed is DataLake (replacing the prior DDP feed). Files are placed "
        "on SFTP and processed by Xactly Connect process group UploadDataLake, then mapped into "
        "Incent standard and custom order fields.",
    )

    add_table(
        doc,
        [
            [
                "Data Type",
                "Source",
                "Volume",
                "Upload Frequency",
                "File Period",
                "Currency Type",
                "Order Type Name(s)",
            ],
            [
                "DataLake Orders",
                "SFTP",
                "~60k+ rows / month (sample Jun-2026)",
                "Daily",
                "Daily / MTD",
                "USD",
                "DataLake",
            ],
            [
                "Clawback Orders",
                "SFTP",
                "",
                "Weekly",
                "YTD",
                "USD",
                "Clawback Order",
            ],
        ],
        widths=[1.3, 0.8, 1.5, 1.1, 0.9, 0.9, 1.2],
        font_size=8,
    )

    # ---- 4.1 DataLake inbound ----
    add_heading_custom(doc, "4.1 Inbound Process 1 — Load_DataLake", 2)
    add_para(
        doc,
        "Final SFTP load file format is based on DataLake_YYYY-MM-DD (sample reference: "
        "DataLake_2026-06-30). Connect selects the latest matching file from /inbound/.",
    )
    add_table(
        doc,
        [
            ["Source File: DataLake_YYYY-MM-DD.csv", ""],
            ["Flat File Attribute", "Value"],
            ["File Type", "csv"],
            ["Encoding", "UTF-8"],
            ["Encryption", "No"],
            ["File Name", "DataLake_YYYY-MM-DD.csv"],
            ["File Location", "/inbound"],
            ["Delimiter", "Comma (,)"],
            ["Quote Enclosed Values", "Y"],
            ["Multiple Files Allowed on FTP", "N (process latest by name desc)"],
            ["Archive File on Completion", "N"],
            ["Duration of File Archive", "90 days"],
            ["Remove Leading/Trailing Spaces", "Y"],
            ["File Filter Criteria", "DirList name like 'DataLake_____-__-__.csv'"],
            ["First Line Names", "true"],
        ],
        widths=[3.0, 4.2],
        header=False,
        font_size=9,
    )

    add_para(
        doc,
        "When placed on the SFTP, the DataLake file will have the following columns, headers and "
        "expected format (aligned to DataLake_2026-06-30 final feed):",
    )
    add_table(
        doc,
        [
            ["Field Name", "Required?", "Data Type", "Example Values / Comments"],
            ["FEED_COUNT", "N", "Number", "1"],
            ["datasource_name", "N", "String", "Needham | Hill Country | AED"],
            ["sales_location_id", "N", "String/Number", "1543"],
            ["invoice_number", "Y", "String", "S6437712.001"],
            ["invoice_date", "Y", "Date", "6/26/2026 (M/d/yyyy)"],
            ["invoice_line_number", "Y", "String/Number", "18"],
            ["sku", "N", "String/Number", "714124"],
            ["sku_description", "N", "String", "PVC 100LB 1-IN-TYPE-LB COND FTG"],
            ["customer_account_number", "N", "String/Number", "13165"],
            ["customer_account_name", "N", "String", "ROYAL ELECTRIC COMPANY  I"],
            ["outside_sales_rep_id", "N", "String", "HOUSE | GIUJER (OSR / employee key)"],
            ["inside_sales_rep_id", "N", "String", "AUSWIL (ISR / employee key)"],
            ["sales_amount", "Y", "Number", "4.69"],
            ["cost_amount", "N", "Number", "2.82"],
            ["quantity", "N", "Number", "1"],
            ["standard_cost_amount", "N", "Number", "2.82 (market/standard cost)"],
            ["branch_shipment_type", "N", "String", "S | D"],
            ["outbound_freight_expense_local", "N", "Number", "0"],
        ],
        widths=[2.4, 0.9, 1.2, 2.8],
        font_size=8,
    )

    add_para(doc, "The files detailed above will be mapped into Incent as follows:")
    mapping_rows = [
        ["Record Type", "Billings", ""],
        ["Source", "SFTP: Flat file (DataLake)", ""],
        ["Xactly Standard Order Fields", "Source / Derivation", "NOTES"],
        ["Order Code", "invoice_number || '_' || invoice_date", "e.g. S6437712.001_2026-06-26"],
        [
            "Item Code",
            "invoice_line_number || '_' || branch_shipment_type",
            "e.g. 18_S",
        ],
        [
            "Batch Name",
            "'DataLake_' || Period End Date || '_' || Business Group (at prestage)",
            "Ex. DataLake_2026-06-30_BGName",
        ],
        ["Batch Type", "'DataLake' (plus BG suffix at prestage)", "Order Type / Batch Type family DataLake"],
        ["Product Name", "sku", "Uploaded to xc_product if new"],
        ["Geography Name", "Leave Blank", ""],
        ["Customer Name", "customer_account_name", "Uploaded to xc_customer if new"],
        ["Quantity", "quantity", ""],
        ["Amount", "sales_amount", "ToDecimal; warning if null/zero"],
        ["Amount UnitType", "'USD'", ""],
        ["Incentive Date", "invoice_date", "ToDate"],
        ["Order Date", "invoice_date", "ToDate"],
        ["Order Type", "'DataLake'", "Replaces prior DDP order type"],
        ["Discount", "Leave Blank", ""],
        ["Description", "sku_description", ""],
        ["Related Order Code", "Leave Blank", ""],
        ["Related Item Code", "Leave Blank", ""],
        [
            "Employee ID",
            "Derived via TMCA rules-based crediting (OSR/ISR)",
            "Joined from TMCA credited transactions to participant",
        ],
        ["Split Amount (%)", "From TMCA SPLIT_PERCENTAGE", "Per credited assignment"],
        ["Xactly Custom Order Field Names", "Source / Derivation", "NOTES"],
        ["OSR_Code", "outside_sales_rep_id", "Outside sales rep id from feed"],
        ["ISR_Code", "inside_sales_rep_id", "Inside sales rep id from feed"],
        ["Branch_Code", "sales_location_id", ""],
        ["SIM_NUMBER", "sku", "Stock/item number; same source as Product Name"],
        ["Line_Type", "branch_shipment_type", "S/D (and null handled in clean load)"],
        ["CUSTOMER_NUMBER", "customer_account_number", ""],
        ["COST_AMT", "cost_amount", "Nvl to 0 at prestage when null"],
        ["COST_AMT_UnitTypeName", "'USD'", "When COST_AMT present"],
        ["AMS_SIM", "Leave Blank", "Not present in DataLake feed"],
        ["MARKET_COST", "standard_cost_amount", ""],
        ["MARKET_COST_UnitTypeName", "'USD'", "When MARKET_COST present"],
        ["SUPPLIER", "Leave Blank", "Not present in DataLake feed"],
        ["FREIGHT_COST", "outbound_freight_expense_local", "Nvl to 0 where required"],
        ["FREIGHT_COST_UNITTYPENAME", "'USD'", "When FREIGHT_COST present"],
        ["datasource_name", "datasource_name", "Custom attribute from feed"],
        ["FEED_COUNT", "FEED_COUNT", "Custom attribute from feed"],
    ]
    add_table(doc, mapping_rows, widths=[2.3, 3.0, 2.0], header=False, font_size=8)
    # shade section header rows
    # (already rendered; acceptable)

    add_heading_custom(doc, "4.1.1 Field Derivation Details", 3)
    add_table(
        doc,
        [
            ["Order Field Name", "Derivation", "Example"],
            [
                "Order Code",
                "Concatenate invoice_number, underscore, and invoice_date (normalized date).",
                "S6437712.001_2026-06-26",
            ],
            [
                "Item Code",
                "Concatenate invoice_line_number, underscore, and branch_shipment_type.",
                "18_S",
            ],
            [
                "Amount (GP Credit input)",
                "sales_amount from DataLake. Flat Rate credit uses employee split of Order Amount "
                "minus (COST_AMT * SplitPercentage) per Incent credit rule.",
                "sales_amount=4.69; cost_amount=2.82",
            ],
            [
                "Employee ID / Split %",
                "Load TMCA order items from clean DataLake rows; run incent validate/upload/calculate "
                "TMCA; fetch tmca_raw_transaction, tmca_credited_trans, territory assignments; "
                "build prestage_order_item_assignment by employee_id and SPLIT_PERCENTAGE; "
                "suffix order_code/batch with business group name before Incent order upload.",
                "OSR/ISR codes resolved to participant employee_id via TMCA",
            ],
            [
                "Batch Name",
                "'DataLake_' || period end date; at prestage append '_' || business_group_name; "
                "on staging insert append '_001' sequence suffix for batch create.",
                "DataLake_2026-06-30_BG_001",
            ],
        ],
        widths=[1.6, 3.6, 2.0],
        font_size=8,
    )

    add_heading_custom(doc, "4.1.2 Error Identification / Validations", 3)
    add_para(
        doc,
        "In order for the transactions to be loaded successfully, the following scenarios will be "
        "evaluated for data integrity in Connect before staging to Incent.",
    )
    add_table(
        doc,
        [
            ["Reject / Warning", "Category", "Rule"],
            [
                "Mandatory — invoice_date",
                "REJECT",
                "invoice_date is null → 'Mandatory Data missing'",
            ],
            [
                "Mandatory — sales_amount",
                "REJECT",
                "sales_amount is null → 'Mandatory Data missing'",
            ],
            [
                "Mandatory — invoice_number",
                "REJECT",
                "invoice_number is null → 'Mandatory Data missing'",
            ],
            [
                "Mandatory — invoice_line_number",
                "REJECT",
                "invoice_line_number is null → 'Mandatory Data missing'",
            ],
            [
                "Format — invoice_date",
                "REJECT",
                "Not valid M/d/yyyy (or agreed feed date format) → 'Invalid date'",
            ],
            [
                "Format — sales_amount / cost_amount / quantity / standard_cost_amount / outbound_freight_expense_local",
                "REJECT",
                "Not numeric when present → 'Invalid number'",
            ],
            [
                "Warning — sales_amount",
                "WARNING",
                "sales_amount is NULL or 0 → 'DataLake-Warning: SALES Amt is Null or zero'",
            ],
            [
                "Standard order validations",
                "REJECT",
                "Null order_code/item_code/amount/unit type/incentive_date/period_name/batch_name; "
                "invalid batch type / unit type / order type; invalid employee_id; duplicates; "
                "missing assignments",
            ],
            [
                "TMCA CR assignment missing",
                "REJECT / Email",
                "Raw TMCA transactions without credited_trans → email with attachment error log",
            ],
        ],
        widths=[2.2, 1.0, 4.0],
        font_size=8,
    )

    # ---- Connect pipeline ----
    add_heading_custom(doc, "4.1.3 Connect Pipeline Structure — UploadDataLake", 3)
    add_para(
        doc,
        "Pipeline structure mirrors the proven UploadDDP Connect pattern "
        "(p_o_upload_process_UploadDDP). Object and variable names are updated for DataLake; "
        "field mappings follow Section 4.1. Customer display name uses Wesco.",
    )
    add_para(doc, "Process group / pipeline root: p_o_upload_process_UploadDataLake", bold=True)

    pipeline_outline = [
        (
            "p_o_set_dynamic_variables",
            [
                "s_o_shared_set_params_in_vars — PERIOD_NAME, PG_NAME, PARAM_EXT_TASK_ID, EXT_OBJECT_NAME, "
                "CUST_BUSINESS_ID, Email_Distribution_List; build v_email_to with "
                "delta-notifications@xactlycorp.com; v_customer_name = 'Wesco'; "
                "v_shared_customer_name = customer || '-' || pod suffix",
                "s_o_period_start_date / s_o_period_end_date — from xactly.xc_period",
                "s_o_set_generic_email_body / subject / create e_generic_email",
                "s_set_cur_date — prior calendar day",
            ],
        ),
        (
            "p_o_set_custom_variables_Upload_DataLake",
            [
                "s_o_set_custom_variables_Upload_DataLake — v_seq = NULL",
                "s_o_set_processname_UploadDataLake — v_process_name_UploadDataLake = 'UploadDataLake'",
                "s_o_set_batch_size_UploadDataLake — v_batch_size = 20000",
            ],
        ),
        (
            "p_o_load_sourcedata_UploadDataLake",
            [
                "s_o_create_validation_errorlog_UploadDataLake — delta.validation_errors_UploadDataLake",
                "p_o_load_source_file_UploadDataLake_DataLake / p_o_read_source_file_…",
                "s_o_set_source_file_name — DirList('/inbound/') where name like 'DataLake_____-__-__.csv' "
                "order by name desc",
                "s_o_read_source_dump — ReadFile into delta.UploadDataLake_DataLake_dump with columns: "
                "FEED_COUNT, datasource_name, sales_location_id, invoice_number, invoice_date, "
                "invoice_line_number, sku, sku_description, customer_account_number, customer_account_name, "
                "outside_sales_rep_id, inside_sales_rep_id, sales_amount, cost_amount, quantity, "
                "standard_cost_amount, branch_shipment_type, outbound_freight_expense_local, SeqNum() row_no",
            ],
        ),
        (
            "p_o_validate_source_file_UploadDataLake_DataLake",
            [
                "Datatype / format validation table delta.validate_UploadDataLake_DataLake",
                "Mandatory checks for invoice_date, sales_amount, invoice_number, invoice_line_number",
                "Numeric format checks for amount/cost/qty/standard_cost/freight",
                "s_o_set_abortflag — v_abort_ondata_error_UploadDataLake_DataLake = false (load clean excluding errors)",
                "s_o_load_clean — delta.UploadDataLake_DataLake_clean with ToDate/ToDecimal casts",
            ],
        ),
        (
            "Prestage / shared setup",
            [
                "s_o_create_prestage_order_item / assignment",
                "s_o_shared_create_archive_error_log / process_log",
                "p_Load_Incent_Participant_BG_UploadDataLake — participant + business group dumps; emp_bg join",
            ],
        ),
        (
            "p_o_transform_UploadDataLake / p_transform_CreditAssignment_datalake",
            [
                "Delete staging.tmca_order_item",
                "Build delta.tmca_order_item_dump_datalake from clean DataLake with mappings in 4.1 "
                "(order_type/batch_type = DataLake)",
                "Insert staging.tmca_order_item",
                "p_tmca_upload_geography_customer_product_datalake — insert missing geo/customer/product; "
                "incent upload geographies/customers/products",
                "incent purge tmca(PeriodName); sleep; incent validate tmca orders; write TMCA error log",
                "Clear invalid TMCA stage rows; incent upload tmca orders; sleep; incent calculate tmca",
                "Fetch temp_raw_transaction / credited_trans / territory; build datalake_accrual_order_item_dump "
                "and source assignment dump",
                "Email missing CR assignment orders",
                "Populate delta.prestage_order_item_assignment and delta.prestage_order_item "
                "(order_code/batch suffixed with business_group_name)",
            ],
        ),
        (
            "p_o_shared_delete_staging_tables → p_o_order_validations_UploadDataLake",
            [
                "Custom warning for null/zero sales_amount",
                "Standard mandatory / batch type / unit type / order type / employee / duplicate / "
                "missing assignment validations into delta.process_log",
                "Insert valid prestage rows to staging.order_item(_assignment)",
            ],
        ),
        (
            "p_o_shared_upload_orders → queue PG",
            [
                "incent create batches; upload customers/products/geographies; validate orders; "
                "archive validation errors; rebuild staging with valid rows only",
                "Iterator insert by batch; incent upload orders (Validate=false)",
                "Update delta.pgqueue_mapping_with_period; p_o_shared_queue_pg — QueueIncentProcessGroup",
                "Write QueuePG log; on error p_o_email_invocation_errors",
            ],
        ),
    ]

    for title, bullets in pipeline_outline:
        add_para(doc, title, bold=True, space_after=2)
        for b in bullets:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(b)
            set_run_font(run, size=9)

    add_para(
        doc,
        "Note: Sleep durations (e.g. 420 / 300 / 60 / 30 seconds) and batch size 20000 follow the "
        "baseline UploadDDP pipeline and may be tuned during build/UAT without changing functional mapping.",
        size=9,
    )

    # ---- 4.2 Clawback ----
    add_heading_custom(doc, "4.2 Inbound Process 2 — Load_DataLake_Clawback", 2)
    add_para(
        doc,
        "Clawback inbound processing remains as designed in the prior Wesco SOW16 FRD, with references "
        "to prior DDP orders updated to DataLake order type for lookup of original invoices.",
    )
    add_table(
        doc,
        [
            ["Source File: DataLake_Clawback_<<Period_Name>>.csv", ""],
            ["Flat File Attribute", "Value"],
            ["File Type", "csv"],
            ["Encoding", "UTF-8"],
            ["Encryption", "No"],
            ["File Name", "DataLake_Clawback_<<Period_Name>>.csv"],
            ["File Location", "/inbound"],
            ["Delimiter", "Comma (,)"],
            ["Quote Enclosed Values", "N"],
            ["Multiple Files Allowed on FTP", "N"],
            ["Archive File on Completion", "N"],
            ["Duration of File Archive", "90 days"],
            ["Remove Leading/Trailing Spaces", "Y"],
            ["File Filter Criteria", "None (use all rows)"],
        ],
        widths=[3.0, 4.2],
        header=False,
    )

    add_para(
        doc,
        "When placed on the SFTP, the Clawback file will have the following columns, headers and expected format:",
    )
    clawback_fields = [
        ["Field Name", "Required?", "Data Type", "Example Values / Comments"],
        ["Customer_Account_Number", "N", "String", ""],
        ["Customer_Account_Name", "N", "String", ""],
        ["Transaction_Number", "Y", "String", "Example: 10000006176"],
        ["Transaction_Date", "Y", "Date", ""],
        ["Due_Date", "N", "Date", ""],
        ["Transaction_Type", "N", "String", ""],
        ["Currency_Code", "N", "String", ""],
        ["Original_Transaction_Amount", "N", "Number", ""],
        ["AR_Balance_Remaining", "N", "Number", ""],
        ["1_-_30_Days", "N", "Number", ""],
        ["31_-_60_Days", "N", "Number", ""],
        ["61-_90_Days", "N", "Number", ""],
        ["91-120_Days", "N", "Number", ""],
        ["121-150_Days", "N", "Number", ""],
        ["151-180_Days", "N", "Number", ""],
        ["181-210_Days", "N", "Number", ""],
        ["210+_Days", "N", "Number", ""],
        ["Aged_Days", "N", "Number", ""],
        ["Dispute_Amount", "N", "Number", ""],
        ["Dispute_Code", "N", "String", ""],
        ["Dispute_Date", "N", "Date", ""],
        ["Payment_Terms", "N", "String", ""],
        ["Sales_Location", "N", "String", ""],
        ["Outside_Sales_Rep", "N", "String", ""],
        ["Inside_Sales_Rep", "N", "String", ""],
        ["Ledger", "N", "String", ""],
        ["Legal_Entity", "N", "String", ""],
        ["Operating_Group", "N", "String", ""],
        ["Business_Unit", "N", "String", ""],
        ["6+_Month_Dispute_Total", "N", "Number", ""],
        ["9+_Month_UnDispute_Total", "N", "Number", ""],
    ]
    add_table(doc, clawback_fields, widths=[2.4, 0.9, 1.0, 2.9], font_size=8)

    add_para(doc, "The files detailed above will be mapped into Incent as follows:")
    add_table(
        doc,
        [
            ["Record Type", "Billings", ""],
            ["Source", "SFTP: Flat file", ""],
            ["Xactly Standard Order Fields", "Source / Derivation", "NOTES"],
            ["Order Code", "Invoice_ID (Transaction_Number)", ""],
            ["Item Code", "Transaction_Date", ""],
            [
                "Batch Name",
                "Clawback_<Incent Period Name>'_'<SEQ>",
                "Ex. Clawback_JAN-2026_001",
            ],
            ["Batch Type", "'Clawback'", ""],
            ["Product Name", "Leave Blank", ""],
            ["Geography Name", "Leave Blank", ""],
            ["Customer Name", "Leave Blank", ""],
            ["Quantity", "Leave Blank", ""],
            ["Amount", "Derived", "See Field Derivation"],
            ["Amount UnitType", "'USD'", ""],
            ["Incentive Date", "Processing Month End Date", ""],
            ["Order Date", "", ""],
            ["Order Type", "'Clawback Order'", ""],
            ["Discount", "Leave Blank", ""],
            ["Description", "Leave Blank", ""],
            ["Related Order Code", "Leave Blank", ""],
            ["Related Item Code", "Leave Blank", ""],
            ["Employee ID", "Derived", "From matching DataLake order"],
            ["Split Amount (%)", "100%", ""],
            ["Xactly Custom Order Field Names", "Source / Derivation", ""],
            ["Transaction_Number", "Transaction_Number", ""],
        ],
        widths=[2.3, 3.0, 2.0],
        header=False,
        font_size=8,
    )

    add_heading_custom(doc, "4.2.1 Field Derivation Details", 3)
    add_table(
        doc,
        [
            ["Order Field Name", "Derivation", "Example"],
            [
                "Amount",
                "Step 1: Lookup Invoice ID (transaction number) from the Clawback file in Xactly Incent "
                "Orders for current and prior month with Order Type as ‘DataLake’. "
                "Step 2: Check if any clawback has been paid for this invoice in the past. IF NO then "
                "aggregate the commission paid in all the months for this invoice, multiply it with -1 "
                "and then map it to Amount field. "
                "Step 3: If a clawback has been paid in the past 180 days for an invoice, and then "
                "customer completes the payment within 180 day period from clawback payment date "
                "(month end), then a positive clawback will be generated. Amount = Clawback amount "
                "generated earlier * -1. "
                "Identifier for ‘If invoice paid by customer’ — Once a customer has paid the invoice, "
                "the record will be dropped from the Clawback file. Connect will need to check if an "
                "invoice ID for clawback generated in the past 180 days is present in the file. If "
                "absent, it indicates that invoice has been paid and a positive clawback needs to be generated.",
                "Example – If clawback amount was -$1800, and customer paid back within 180 days, then "
                "a positive clawback of $1800 will be added to payment for ISR and OSR on that deal.",
            ],
            [
                "Employee_ID_1",
                "Step 1: Lookup Invoice ID from Clawback file in Incent Orders (Order Type = ‘DataLake’). "
                "Step 2: If matching records are found, assign employee ID 1 from first transaction with "
                "same invoice ID.",
                "",
            ],
            [
                "Employee_ID_2",
                "Same as Employee_ID_1 for second assignment on the matching DataLake order.",
                "",
            ],
        ],
        widths=[1.4, 3.8, 2.0],
        font_size=8,
    )

    add_heading_custom(doc, "4.2.2 Error Identification", 3)
    add_para(
        doc,
        "In order for the transactions to be loaded successfully, the following scenarios will be "
        "evaluated for data integrity.",
    )
    add_table(
        doc,
        [
            ["Reject Reason No.", "Category", "Reject Reason"],
            ["Reject-01", "FAIL", "ERROR: Invoice not found in Xactly Incent"],
            [
                "Reject-02",
                "FAIL",
                "ERROR: Clawback already done and Invoice unpaid over 270 days",
            ],
        ],
        widths=[1.4, 1.0, 4.8],
    )
    add_para(
        doc,
        "For reject 2 – count the number of days from Invoice paid date (incentive date on the first "
        "invoice associated with the invoice ID). If the days passed is >180, evaluate unpaid window "
        "rules as above.",
    )


def build_plan_components(doc):
    add_heading_custom(doc, "5. PLAN COMPONENT DETAILS", 1)
    add_para(doc, "The following subsections include component-specific details and examples.")

    # Component 01
    add_heading_custom(doc, "5.1 Component 01: Flat Rate Commission", 2)
    add_para(doc, "Incentive summary:", bold=True)
    add_kv_table(
        doc,
        [
            ("Component Number", "01"),
            ("Component Name", "Flat Rate Commission"),
            ("Which data source is used?", "DataLake"),
            ("Which type of commission math is performed?", "Flat Rate"),
            ("What level of detail does calculation occur at?", "Per Credit"),
        ],
    )

    add_heading_custom(doc, "5.1.1 Credits: Flat Rate Commission", 3)
    add_kv_table(
        doc,
        [
            ("Data Source", "DataLake"),
            ("What qualifies?", "Order Type = “DataLake”"),
            (
                "What’s calculated?",
                "Employee’s split of the Order Amount (OrderItem.SplitAmount) – "
                "(OrderItem.COST_AMT * OrderItem.SplitPercentage)",
            ),
            ("What’s it called?", "GP Credit"),
            ("Will indirect credit be passed via the hierarchy?", "N"),
            ("Will indirect credit be passed via a named relationship?", "N"),
            ("Is this indirect credit Standard?", "N"),
        ],
    )

    add_heading_custom(doc, "5.1.2 Commissions: Flat Rate Commission", 3)
    add_kv_table(
        doc,
        [
            ("Which type of commission math is performed?", "Rate Table"),
            ("What level of detail does calculation occur at?", "Per Credit"),
            ("What’s the calculation frequency?", "Monthly"),
            ("What’s the payment frequency?", "Monthly"),
            ("What’s the qualifiers for this rule?", "Credit Type = ‘GP Credit’"),
            ("Does this component pay a percentage or a flat amount?", "Percentage"),
            (
                "What is the incentive rate applied to?",
                "Formula(Rate Table (lookup table, rate of position))",
            ),
            ("How does the rate vary?", "Rate table (position)"),
            ("Is the rate fixed, calculated, or something else?", "Calculated"),
            ("Does a component weight apply?", "Y"),
            ("Which Personal Target period is used in the Base Commission Rate?", "N"),
            ("Which Quota period is used in the Base Commission Rate?", "N"),
            ("Currency?", "Payment Currency"),
            ("Holds?", "Yes"),
            ("Earning Group", "Flat Rate Commissions"),
        ],
    )

    add_para(
        doc,
        "Look Up Table – Will be maintained by Customer Number wrt to the sales rep at Order table",
    )
    add_para(doc, "Lookup table Name: LKP_Wesco_Flat_Rate_Commission", bold=True)
    add_para(doc, "Position Name: 90156-Rucker-Wesco ISR (For Testing)")
    add_table(
        doc,
        [
            ["Customer Number", "Position Name", "Return Value Rate"],
            ["AC0183-7595", "90156-Rucker-Wesco ISR", "2%"],
        ],
        widths=[2.0, 2.8, 1.6],
    )
    add_para(
        doc,
        "Customer numbers listed in the lookup table will receive 2% of the credit amount, while "
        "customer numbers not included in the Lookup table will receive 5% of the credit amount.",
    )
    add_para(
        doc,
        "Note: In the future, when we modify the percentage for the specified customer numbers, the "
        "corresponding entries in the lookup table should be changed, while the remaining customer "
        "numbers should be adjusted in the formula mentioned below.",
    )
    add_para(doc, "Formula Name: Wesco_Flat_Rate_CN_Commission", bold=True)

    add_heading_custom(doc, "5.1.3 Component Examples: Flat Rate Commission", 3)
    add_para(doc, "Reference data:")
    add_kv_table(doc, [("Employee ID", "1234"), ("Employee Title", "Flat Rate ISR")])
    add_para(doc, "Example Order Data:")
    add_table(
        doc,
        [
            [
                "Order Code",
                "Item Code",
                "Amount",
                "Amount UnitType",
                "Employee ID",
                "Split %",
                "Incentive Date",
                "Order Type",
            ],
            ["4891_OC1", "782_JAN-2026", "12,000", "USD", "1234", "100", "01/15/2026", "DataLake"],
            ["86198_OC1", "862_FEB-2026", "15,000", "USD", "1234", "100", "02/10/2026", "DataLake"],
        ],
        widths=[1.1, 1.2, 0.8, 1.0, 0.9, 0.7, 1.1, 1.0],
        font_size=8,
    )
    add_para(doc, "Example Credit and Commission Calculation:")
    add_para(doc, "Credit -", bold=True)
    add_table(
        doc,
        [
            [
                "Order Code",
                "Item Code",
                "Period",
                "Credit Amount",
                "Unit",
                "Customer Number",
                "Position Name",
                "Credit Type",
            ],
            [
                "4891_OC1",
                "782_JAN-2026",
                "JAN-2026",
                "12,000",
                "USD",
                "AC0183-7595",
                "Flat Rate ISR (1234)",
                "GP Credit",
            ],
            [
                "86198_OC1",
                "862_FEB-2026",
                "FEB-2026",
                "15,000",
                "USD",
                "AC0183-7596",
                "Flat Rate ISR (1234)",
                "GP Credit",
            ],
        ],
        widths=[1.0, 1.1, 0.9, 1.0, 0.6, 1.2, 1.3, 0.9],
        font_size=8,
    )
    add_para(doc, "Commission –", bold=True)
    add_table(
        doc,
        [
            ["Order Code", "Item Code", "Credit Amount", "Rate", "Commission", "Earning Group"],
            ["4891_OC1", "782_JAN-2026", "12,000", "2%", "$240", "GP Credit"],
            ["86198_OC1", "862_FEB-2026", "15,000", "5%", "$750", "GP Credit"],
        ],
        widths=[1.2, 1.3, 1.2, 0.8, 1.1, 1.4],
    )

    # Component 02
    add_heading_custom(doc, "5.2 Component 02: Clawback Commission", 2)
    add_para(doc, "Incentive summary:", bold=True)
    add_kv_table(
        doc,
        [
            ("Component Number", "02"),
            ("Component Name", "Clawback Commission"),
            ("Which data source is used?", "DataLake, Clawback"),
            ("Which type of commission math is performed?", "Flat Rate"),
            ("What level of detail does calculation occur at?", "Aggregation (In Connect)"),
        ],
    )

    add_heading_custom(doc, "5.2.1 Credits: Clawback Commission", 3)
    add_kv_table(
        doc,
        [
            ("Data Source", "Clawback"),
            ("What qualifies?", "Order Type = “Clawback Order”"),
            (
                "What’s calculated?",
                "Employee’s split of the Order Amount (OrderItem.SplitAmount)",
            ),
            ("What’s it called?", "Clawback Commission"),
            ("Will indirect credit be passed via the hierarchy?", "N"),
            ("Will indirect credit be passed via a named relationship?", "N"),
            ("Is this indirect credit Standard?", "N"),
        ],
    )

    add_heading_custom(doc, "5.2.2 Commissions: Clawback Commission", 3)
    add_kv_table(
        doc,
        [
            ("Which type of commission math is performed?", "Flat Rate"),
            ("What level of detail does calculation occur at?", "Per Credit (already aggregated)"),
            ("What’s the calculation frequency?", "Monthly"),
            ("What’s the payment frequency?", "Monthly"),
            ("Does this component pay a percentage or a flat amount?", "Flat Rate (100%)"),
            ("What is the incentive rate applied to?", "Line-Item Amount"),
            ("How does the rate vary?", "N/A"),
            ("Is the rate fixed, calculated, or something else?", "Fixed"),
        ],
    )
    add_para(doc, "Rate Table – Will be maintained by Position")
    add_para(doc, "Flat Rate Commission")
    add_table(
        doc,
        [["Range From", "Range To", "Flat Rate"], ["0", "0", "100%"]],
        widths=[1.5, 1.5, 1.5],
    )

    add_heading_custom(doc, "5.2.3 Component Examples: Clawback Commission", 3)
    add_para(doc, "Reference data:")
    add_kv_table(doc, [("Employee ID", "1234"), ("Employee Title", "Flat Rate ISR")])
    add_para(doc, "Example Order Data:")
    add_table(
        doc,
        [
            [
                "Order Code",
                "Item Code",
                "Amount",
                "Amount UnitType",
                "Employee ID",
                "Split %",
                "Incentive Date",
                "Order Type",
            ],
            [
                "1456923",
                "01/01/2026",
                "-18000",
                "USD",
                "1234",
                "100",
                "03/31/2026",
                "Clawback Order",
            ],
            [
                "2456973",
                "09/10/2025",
                "9000",
                "USD",
                "1234",
                "100",
                "04/30/2026",
                "Clawback Order",
            ],
        ],
        widths=[1.0, 1.1, 0.9, 1.1, 0.9, 0.7, 1.1, 1.2],
        font_size=8,
    )
    add_para(doc, "Example Credit and Commission Calculation:")
    add_para(doc, "Credit -", bold=True)
    add_table(
        doc,
        [
            ["Order Code", "Item Code", "Period", "Credit Amount", "Unit", "Credit Type"],
            ["1456923", "01/01/2026", "MAR-2026", "-18000", "USD", "Clawback Commission"],
            ["2456973", "09/10/2025", "APR-2026", "9000", "USD", "Clawback Commission"],
        ],
        widths=[1.2, 1.2, 1.0, 1.2, 0.8, 1.6],
    )
    add_para(doc, "Commission -", bold=True)
    add_table(
        doc,
        [
            ["Order Code", "Item Code", "Credit Amount", "Rate", "Commission", "Earning Group"],
            ["1456923", "01/01/2026", "-18000", "100%", "-$18000", "Clawback Commission"],
            ["2456973", "09/10/2025", "9000", "100%", "$9000", "Clawback Commission"],
        ],
        widths=[1.2, 1.2, 1.2, 0.8, 1.1, 1.6],
    )


def build_special_ancillary_reporting(doc):
    add_heading_custom(doc, "6. SPECIAL SCENARIOS", 1)
    add_table(
        doc,
        [
            ["Special Scenario", "Details"],
            [
                "New hires eligible for incentive comp immediately, or start of next period?",
                "Immediately",
            ],
            ["Proration of Personal Target calculated in Incent?", "N"],
            ["Which time period of Personal Target loaded to Person record?", "Yearly"],
            ["Mid-period job changes permitted?", "N"],
            [
                "Do terminated employees’ credit and incentives stop immediately, or at the end of the period?",
                "Immediately",
            ],
            [
                "If a payee’s total incentive for a period is negative, does it carry forward?",
                "N",
            ],
        ],
        widths=[4.5, 2.5],
        font_size=9,
    )

    add_heading_custom(doc, "7. ANCILLARY FEATURES", 1)
    add_table(
        doc,
        [
            ["Feature", "Details"],
            ["Adjustment Types", "Commission Pass-Through"],
            ["Prior Period Adjustments", "Not required, adjustments handled in current period"],
            ["Employee Hierarchy", "1-1 payee-manager relationships, standard"],
            ["Named Relationships", "N"],
            ["Custom Roles", "N"],
        ],
        widths=[2.5, 4.5],
    )

    add_heading_custom(doc, "8. REPORTING", 1)
    add_para(
        doc,
        "Xactly consultants will configure one template for each standard report and create one "
        "dashboard of PODs as an example for the customer to do additional customization.",
    )


def build_design_review(doc):
    add_heading_custom(doc, "9. DESIGN REVIEW", 1)
    add_para(
        doc,
        "This section addresses the design of the remaining Incent objects required to support "
        "Wesco’s 2026 plan requirements and summarizes the design of the plan objects.",
    )

    add_heading_custom(doc, "9.1 Processing Calendar and Names", 2)
    add_para(doc, "Wesco’s 2026 commission calendar is as shown below:")
    add_para(
        doc,
        "Note: The Calendar convention specified below cannot be modified after the FRD is signed.",
        bold=True,
    )
    cal = [["Year", "Quarter", "Month", "From", "To"]]
    months = [
        ("QTR-1-2026", "JAN-2026", "01/01/2026", "01/31/2026"),
        ("QTR-1-2026", "FEB-2026", "02/01/2026", "02/28/2026"),
        ("QTR-1-2026", "MAR-2026", "03/01/2026", "03/31/2026"),
        ("QTR-2-2026", "APR-2026", "04/01/2026", "04/30/2026"),
        ("QTR-2-2026", "MAY-2026", "05/01/2026", "05/31/2026"),
        ("QTR-2-2026", "JUN-2026", "06/01/2026", "06/30/2026"),
        ("QTR-3-2026", "JUL-2026", "07/01/2026", "07/31/2026"),
        ("QTR-3-2026", "AUG-2026", "08/01/2026", "08/31/2026"),
        ("QTR-3-2026", "SEP-2026", "09/01/2026", "09/30/2026"),
        ("QTR-4-2026", "OCT-2026", "10/01/2026", "10/31/2026"),
        ("QTR-4-2026", "NOV-2026", "11/01/2026", "11/30/2026"),
        ("QTR-4-2026", "DEC-2026", "12/01/2026", "12/31/2026"),
    ]
    for q, m, f, t in months:
        cal.append(["YEAR-2026", q, m, f, t])
    add_table(doc, cal, widths=[1.2, 1.3, 1.2, 1.3, 1.3], font_size=9)

    add_heading_custom(doc, "9.2 Business Group Names", 2)
    add_para(doc, "Wesco will use the following Business Groups.")
    add_table(
        doc,
        [["Business Group", "Business Group Currency"], ["TBC", "USD"]],
        widths=[3.0, 2.5],
    )

    add_heading_custom(doc, "9.3 Currency", 2)
    add_para(doc, "Wesco’s global sales organization requires the use of only USD currency.")
    add_heading_custom(doc, "9.3.1 Currency Design", 3)
    add_para(
        doc,
        "This is the design of the currency for Incent objects. Personal Currency and Payment "
        "Currency will be the same per individual.",
    )
    add_table(
        doc,
        [
            ["Object", "Currency"],
            ["Quotas", "USD"],
            ["Personal Target", "USD"],
            ["Orders", "USD"],
            ["Credits", "USD"],
            ["Commissions/Bonuses", "USD"],
            ["Payments", "USD"],
        ],
        widths=[2.5, 2.0],
    )
    add_heading_custom(doc, "9.3.2 Currency Names", 3)
    add_para(
        doc,
        "This is the list of currencies that Wesco requires for its variable compensation calculation "
        "process. Exchange rates will be managed by Wesco admins on an as-needed basis.",
    )
    add_table(
        doc,
        [["Currency Code", "Currency Name"], ["USD", "United States Dollar"]],
        widths=[2.0, 3.0],
    )

    add_heading_custom(doc, "9.4 Position Name Design", 2)
    add_para(
        doc,
        "Wesco will not reuse old Positions. This is the design of Wesco’s position names.",
    )
    add_table(
        doc,
        [
            ["Title Name", "Position Name Design"],
            ["Flat Rate ISR", "Smith John_Flat Rate ISR_123456"],
            ["Flat Rate OSR", "Smith John_Flat Rate OSR_123456"],
        ],
        widths=[2.0, 4.0],
    )

    add_heading_custom(doc, "9.5 Business Preferences", 2)
    add_para(
        doc,
        "The following Preferences cannot be changed once set. Please refer to the Community article "
        "for details on what these preferences control.",
    )
    add_table(
        doc,
        [
            ["Business Preference", "Value"],
            ["BALANCE_CARRY_FORWARD", "JAN-2026, Yes, Immediate"],
            ["BUSINESS_GROUP_SECURITY", "Yes"],
            ["BUSINESS_GROUP_SECURITY_FOR_BATCHES", "Yes"],
        ],
        widths=[3.5, 3.0],
    )


def build_design_summary(doc):
    add_heading_custom(doc, "10. DESIGN SUMMARY", 1)
    add_para(
        doc,
        "This is a summary of the object name design for Wesco’s 2026 plan components.",
    )
    add_table(
        doc,
        [
            [
                "#",
                "Component Name",
                "Order Type Name",
                "Credit Type Name",
                "Earning Group Name",
                "Quota Name",
                "Rate Table Name",
            ],
            [
                "01",
                "Flat Rate Commission",
                "DataLake",
                "GP Credits",
                "Flat Rate Commission",
                "-",
                "Flat Rate Commission",
            ],
            [
                "02",
                "Clawback Commission",
                "Clawback Order",
                "Clawback Commission",
                "Clawback Commission",
                "-",
                "Clawback Commission",
            ],
        ],
        widths=[0.5, 1.5, 1.2, 1.3, 1.4, 0.8, 1.4],
        font_size=8,
    )

    add_heading_custom(doc, "11. Instructions to Update Lookup table", 1)
    add_para(doc, "Login to Incent, select the Environment.", bold=True)
    steps = [
        "Hover to Plan design from the left side menu and click on Lookup table.",
        "Click on the lookup table which is mentioned in the 5.1.2 Component (LKP_Wesco_Flat_Rate_Commission).",
        "Click on edit and click on Download button at bottom right to get the list of records which are already in the lookup table.",
        "OR click on create new template to download the template with no records present.",
        "If you select “Create New Template” it will ask you for the positions for which the rate need to be added. Once we select, the template will download with the required columns.",
        "Once the rate is uploaded into the system, go back to lookup table in incent and click on upload.",
        "For Upload, we have 4 options:",
        "Allow create new row: will only upload the new rows in the file.",
        "Allow updates to existing rows: will only update to records which are already in the system.",
        "Allow update and create new: will update the old records and create the new records into the system.",
        "Allow deletes to all existing rows and create new rows: will delete all rows and it will update fresh data into the system.",
    ]
    for s in steps:
        p = doc.add_paragraph(style="List Number")
        run = p.add_run(s)
        set_run_font(run, size=10)
    add_para(doc, "Note: select the option based on the kind of upload", bold=True)


def build_acceptance(doc):
    add_heading_custom(doc, "12. DOCUMENT ACCEPTANCE", 1)
    add_para(doc, "Wesco:", bold=True, size=12)
    add_para(doc, "Approved by:\tMichael")
    add_para(doc, "Title:\t\t[PENDING CLIENT CLARIFICATION]")
    add_para(doc, "Signature:")
    add_para(doc, "Date:")
    add_para(doc, "")
    add_para(doc, "Approved by:\tJake")
    add_para(doc, "Title:\t\t[PENDING CLIENT CLARIFICATION]")
    add_para(doc, "Signature:")
    add_para(doc, "Date:")
    add_para(doc, "")
    add_para(doc, "Xactly Corporation:", bold=True, size=12)
    add_para(doc, "Approved by:\tNabanitha")
    add_para(doc, "Title:\t\tProject Manager")
    add_para(doc, "Signature:")
    add_para(doc, "Date:")
    add_para(doc, "")
    add_para(doc, "Approved by:\tSireesh Kumar")
    add_para(doc, "Title:\t\tLead Consultant")
    add_para(doc, "Signature:")
    add_para(doc, "Date:")
    add_para(doc, "")
    add_para(doc, "Approved by:\tK Sai Kiran")
    add_para(doc, "Title:\t\tSenior Consultant")
    add_para(doc, "Signature:")
    add_para(doc, "Date:")


def build_appendix_connect(doc):
    doc.add_page_break()
    add_heading_custom(doc, "APPENDIX A — Connect Object Naming Crosswalk (DDP → DataLake)", 1)
    add_para(
        doc,
        "Use this crosswalk when cloning the UploadDDP pipeline to UploadDataLake for SOW-14.",
    )
    add_table(
        doc,
        [
            ["Prior (DDP / UploadDDP)", "SOW-14 (DataLake / UploadDataLake)"],
            ["p_o_upload_process_UploadDDP", "p_o_upload_process_UploadDataLake"],
            ["p_o_set_custom_variables_Upload_DDP", "p_o_set_custom_variables_Upload_DataLake"],
            ["v_process_name_UploadDDP = 'UploadDDP'", "v_process_name_UploadDataLake = 'UploadDataLake'"],
            ["v_filename_UploadDDP_DDP", "v_filename_UploadDataLake_DataLake"],
            ["DDP_____-__-__.csv", "DataLake_____-__-__.csv"],
            ["delta.UploadDDP_DDP_dump / _clean", "delta.UploadDataLake_DataLake_dump / _clean"],
            ["delta.validation_errors_UploadDDP", "delta.validation_errors_UploadDataLake"],
            ["order_type / batch_type 'DDP'", "order_type / batch_type 'DataLake'"],
            ["v_customer_name = 'Anixter Inc'", "v_customer_name = 'Wesco'"],
            ["BRANCH", "sales_location_id"],
            ["TYPE / ORDER_TYPE (line)", "branch_shipment_type"],
            ["INVOICE_DATE", "invoice_date"],
            ["INVOICE#", "invoice_number"],
            ["LINE#", "invoice_line_number"],
            ["SIM / PROD_CODE", "sku"],
            ["SIM_DESC", "sku_description"],
            ["CUSTOMER_NAME", "customer_account_name"],
            ["CUSTOMER#", "customer_account_number"],
            ["OSR", "outside_sales_rep_id"],
            ["ISR", "inside_sales_rep_id"],
            ["SALES_AMT", "sales_amount"],
            ["COST_AMT", "cost_amount"],
            ["QTY", "quantity"],
            ["MARKET_COST", "standard_cost_amount"],
            ["FREIGHT_COST", "outbound_freight_expense_local"],
            ["SUPPLIER / AMS_SIM", "Leave Blank (not in DataLake feed)"],
            ["(new)", "datasource_name, FEED_COUNT as custom fields"],
        ],
        widths=[3.5, 3.5],
        font_size=8,
    )


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    doc = Document()
    configure_styles(doc)
    section = doc.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    build_cover(doc)
    build_history(doc)
    build_intro(doc)
    build_success(doc)
    build_overview(doc)
    build_data_section(doc)
    build_plan_components(doc)
    build_special_ancillary_reporting(doc)
    build_design_review(doc)
    build_design_summary(doc)
    build_acceptance(doc)
    build_appendix_connect(doc)

    out_path = OUT_DIR / OUT_NAME
    artifact_path = ARTIFACT_DIR / OUT_NAME
    doc.save(str(out_path))
    doc.save(str(artifact_path))
    print(f"Wrote {out_path}")
    print(f"Wrote {artifact_path}")


if __name__ == "__main__":
    main()
