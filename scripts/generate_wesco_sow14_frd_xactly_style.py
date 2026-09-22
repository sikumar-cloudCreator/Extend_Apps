#!/usr/bin/env python3
"""
Build Wesco SOW-14 FRD in authentic Xactly FRD template style.

Clones Wesco SOW16 FRD v2 (house baseline) to preserve:
  - Century Gothic typography
  - Heading colors (#345A8A / #4F81BD)
  - Peach table header fill (#FBD5B5)
  - FRD Template Final footer / section layout
  - Cover + DOCUMENT HISTORY + TOC scaffolding

Then applies SOW-14 / 2026 / DataLake / Connect updates.
"""

from __future__ import annotations

import re
import shutil
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph
from docx.table import Table

BASE = Path("/home/ubuntu/.cursor/projects/workspace/uploads/Wesco_SOW16_FRD_v2_8e4f.docx")
OUT_NAME = "Wesco_SOW14_FRD_v1_Connect_Incent_xactly_style.docx"
ARTIFACT_DIR = Path("/opt/cursor/artifacts")
OUT_DIR = Path("/workspace/out_frd")

HEADER_FILL = "FBD5B5"
H1_COLOR = RGBColor(0x34, 0x5A, 0x8A)
H2_COLOR = RGBColor(0x4F, 0x81, 0xBD)
FONT = "Century Gothic"


# ---------- low-level helpers ----------

def set_run_font(run, size=None, bold=None, color=None, name=FONT):
    run.font.name = name
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:ascii"), name)
    rFonts.set(qn("w:hAnsi"), name)
    rFonts.set(qn("w:eastAsia"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def clear_paragraph(paragraph: Paragraph):
    p = paragraph._p
    for child in list(p):
        if child.tag != qn("w:pPr"):
            p.remove(child)


def set_paragraph_text(paragraph: Paragraph, text: str, size=10, bold=False, color=None):
    clear_paragraph(paragraph)
    run = paragraph.add_run(text)
    set_run_font(run, size=size, bold=bold, color=color)
    return run


def shade_cell(cell, fill=HEADER_FILL):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def set_cell_text(cell, text, size=10, bold=False, shade=False):
    # keep one paragraph
    paras = cell.paragraphs
    for i, p in enumerate(paras):
        if i == 0:
            set_paragraph_text(p, "" if text is None else str(text), size=size, bold=bold)
        else:
            clear_paragraph(p)
    if shade:
        shade_cell(cell)


def insert_paragraph_after(paragraph: Paragraph, text="", style=None, size=10, bold=False, color=None):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if style:
        new_para.style = style
    if text:
        run = new_para.add_run(text)
        set_run_font(run, size=size, bold=bold, color=color)
    return new_para


def insert_table_after(paragraph: Paragraph, rows: list[list[str]], header_rows=1, col_count=None):
    """Insert a Table Grid table after paragraph; return (table, last_element)."""
    cols = col_count or max(len(r) for r in rows)
    # create via document helper on a temp body then move — use oxml tbl built through docx API
    doc = paragraph.part.document
    # Add at end then relocate
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    for ri, row_data in enumerate(rows):
        for ci in range(cols):
            val = row_data[ci] if ci < len(row_data) else ""
            is_hdr = ri < header_rows
            set_cell_text(table.rows[ri].cells[ci], val, size=9 if not is_hdr else 10, bold=is_hdr, shade=is_hdr)
    tbl = table._tbl
    # detach from end
    tbl.getparent().remove(tbl)
    paragraph._p.addnext(tbl)
    return table


def delete_element(elem):
    parent = elem.getparent()
    if parent is not None:
        parent.remove(elem)


def replace_text_in_paragraph(paragraph: Paragraph, mapping: list[tuple[str, str]]):
    # Operate on full paragraph text then rewrite runs (preserves simple paragraphs)
    full = paragraph.text
    if not full:
        return False
    new = full
    for old, repl in mapping:
        if old in new:
            new = new.replace(old, repl)
    if new == full:
        return False
    # Preserve approximate formatting from first run
    size = None
    bold = None
    color = None
    name = FONT
    if paragraph.runs:
        r0 = paragraph.runs[0]
        size = r0.font.size.pt if r0.font.size else None
        bold = r0.bold
        if r0.font.color and r0.font.color.rgb:
            color = r0.font.color.rgb
        if r0.font.name:
            name = r0.font.name
    # Heading styles already carry formatting — just set text
    style_name = paragraph.style.name if paragraph.style else ""
    clear_paragraph(paragraph)
    run = paragraph.add_run(new)
    if style_name.startswith("Heading"):
        set_run_font(run, name=FONT, bold=True)
    else:
        set_run_font(run, size=size, bold=bold, color=color, name=name)
    return True


def replace_everywhere(doc: Document, mapping: list[tuple[str, str]]):
    for p in doc.paragraphs:
        replace_text_in_paragraph(p, mapping)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    replace_text_in_paragraph(p, mapping)
    # headers/footers
    for section in doc.sections:
        for hdrftr in (section.header, section.footer, section.first_page_header, section.first_page_footer):
            try:
                for p in hdrftr.paragraphs:
                    replace_text_in_paragraph(p, mapping)
            except Exception:
                pass


def find_paragraph(doc: Document, exact: str | None = None, contains: str | None = None):
    for p in doc.paragraphs:
        t = p.text.strip()
        if exact is not None and t == exact:
            return p
        if contains is not None and contains in t:
            return p
    return None


def body_children(doc: Document):
    return list(doc.element.body.iterchildren())


def remove_between(doc: Document, start_para: Paragraph, end_para: Paragraph, keep_start=True, keep_end=True):
    """Remove body elements strictly between start_para and end_para."""
    body = doc.element.body
    children = list(body.iterchildren())
    start_i = children.index(start_para._p)
    end_i = children.index(end_para._p)
    for elem in children[start_i + 1 : end_i]:
        body.remove(elem)


# ---------- content builders for Section 4 ----------

DATALAKE_FILE_ATTRS = [
    ["Source File: DataLake_YYYY-MM-DD.csv", "Source File: DataLake_YYYY-MM-DD.csv"],
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
]

DATALAKE_COLUMNS = [
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
    ["outside_sales_rep_id", "N", "String", "HOUSE | GIUJER (OSR key)"],
    ["inside_sales_rep_id", "N", "String", "AUSWIL (ISR key)"],
    ["sales_amount", "Y", "Number", "4.69"],
    ["cost_amount", "N", "Number", "2.82"],
    ["quantity", "N", "Number", "1"],
    ["standard_cost_amount", "N", "Number", "2.82"],
    ["branch_shipment_type", "N", "String", "S | D"],
    ["outbound_freight_expense_local", "N", "Number", "0"],
]

DATALAKE_MAPPING = [
    ["Record Type", "Billings", ""],
    ["Source", "SFTP: Flat file (DataLake)", ""],
    ["Xactly Standard Order Fields", "Source / Derivation", "NOTES"],
    ["Order Code", "invoice_number || '_' || invoice_date", "e.g. S6437712.001_2026-06-26"],
    ["Item Code", "invoice_line_number || '_' || branch_shipment_type", "e.g. 18_S"],
    ["Batch Name", "'DataLake_' || Period End Date (+ BG / seq at prestage)", "Ex. DataLake_2026-06-30_BG_001"],
    ["Batch Type", "'DataLake'", ""],
    ["Product Name", "sku", ""],
    ["Geography Name", "Leave Blank", ""],
    ["Customer Name", "customer_account_name", ""],
    ["Quantity", "quantity", ""],
    ["Amount", "sales_amount", ""],
    ["Amount UnitType", "'USD'", ""],
    ["Incentive Date", "invoice_date", ""],
    ["Order Date", "invoice_date", ""],
    ["Order Type", "'DataLake'", "Replaces prior DDP order type"],
    ["Discount", "Leave Blank", ""],
    ["Description", "sku_description", ""],
    ["Related Order Code", "Leave Blank", ""],
    ["Related Item Code", "Leave Blank", ""],
    ["Employee ID", "Derived via TMCA (OSR/ISR rules-based crediting)", ""],
    ["Split Amount (%)", "From TMCA SPLIT_PERCENTAGE", ""],
    ["Xactly Custom Order Field Names", "Source / Derivation", "NOTES"],
    ["OSR_Code", "outside_sales_rep_id", ""],
    ["ISR_Code", "inside_sales_rep_id", ""],
    ["Branch_Code", "sales_location_id", ""],
    ["SIM_NUMBER", "sku", ""],
    ["Line_Type", "branch_shipment_type", ""],
    ["CUSTOMER_NUMBER", "customer_account_number", ""],
    ["COST_AMT", "cost_amount", ""],
    ["COST_AMT_UnitTypeName", "'USD'", ""],
    ["AMS_SIM", "Leave Blank", "Not in DataLake feed"],
    ["MARKET_COST", "standard_cost_amount", ""],
    ["MARKET_COST_UnitTypeName", "'USD'", ""],
    ["SUPPLIER", "Leave Blank", "Not in DataLake feed"],
    ["FREIGHT_COST", "outbound_freight_expense_local", ""],
    ["FREIGHT_COST_UNITTYPENAME", "'USD'", ""],
    ["datasource_name", "datasource_name", ""],
    ["FEED_COUNT", "FEED_COUNT", ""],
]

VALIDATIONS = [
    ["Reject / Warning", "Category", "Rule"],
    ["Mandatory — invoice_date", "REJECT", "invoice_date is null → Mandatory Data missing"],
    ["Mandatory — sales_amount", "REJECT", "sales_amount is null → Mandatory Data missing"],
    ["Mandatory — invoice_number", "REJECT", "invoice_number is null → Mandatory Data missing"],
    ["Mandatory — invoice_line_number", "REJECT", "invoice_line_number is null → Mandatory Data missing"],
    ["Format — invoice_date", "REJECT", "Invalid date M/d/yyyy"],
    ["Format — numeric amounts", "REJECT", "Invalid number for sales/cost/qty/standard_cost/freight when present"],
    ["Warning — sales_amount", "WARNING", "DataLake-Warning: SALES Amt is Null or zero"],
    ["TMCA CR assignment missing", "REJECT / Email", "Raw TMCA txn without credited_trans → email error log"],
]

PIPELINE_BULLETS = [
    "Process group root: p_o_upload_process_UploadDataLake (cloned from UploadDDP structure; field names updated for DataLake).",
    "p_o_set_dynamic_variables — set period/process/email vars; v_customer_name = 'Wesco'; build shared customer/pod email identity.",
    "p_o_set_custom_variables_Upload_DataLake — v_process_name_UploadDataLake = 'UploadDataLake'; v_batch_size = 20000.",
    "p_o_load_sourcedata_UploadDataLake — create validation_errors_UploadDataLake; DirList /inbound/ for DataLake_____-__-__.csv; ReadFile into UploadDataLake_DataLake_dump.",
    "p_o_validate_source_file_UploadDataLake_DataLake — mandatory + datatype validations; load clean excluding error rows.",
    "Create prestage order item / assignment / process_log; load participant + business group dumps.",
    "p_o_transform_UploadDataLake — TMCA order item dump from clean DataLake; upload geo/customer/product; purge/validate/upload/calculate TMCA; build credited assignments; prestage Incent orders with BG-suffixed order/batch codes.",
    "p_o_order_validations_UploadDataLake — custom + standard order validations; insert valid rows to staging.",
    "p_o_shared_upload_orders — create batches, validate/upload orders, queue downstream process groups; email on invocation errors.",
]


def fill_existing_table(table: Table, rows: list[list[str]], header_rows=1):
    # Resize rows if needed by cloning last row XML
    while len(table.rows) < len(rows):
        tbl = table._tbl
        last_tr = table.rows[-1]._tr
        tbl.append(deepcopy(last_tr))
    # If too many rows, remove extras from end
    while len(table.rows) > len(rows):
        tr = table.rows[-1]._tr
        tr.getparent().remove(tr)

    cols = len(table.columns)
    for ri, row_data in enumerate(rows):
        for ci in range(cols):
            val = row_data[ci] if ci < len(row_data) else ""
            is_hdr = ri < header_rows
            # For attribute tables with peach on first two rows, keep shade for header_rows
            set_cell_text(table.rows[ri].cells[ci], val, size=9 if not is_hdr else 10, bold=is_hdr or False, shade=is_hdr)


def apply_global_renames(doc: Document):
    # Order matters — longer / more specific first
    mapping = [
        ("Wesco SOW16", "Wesco SOW-14"),
        ("SOW16", "SOW-14"),
        ("LKP_EES_Flat_Rate_Commission", "LKP_Wesco_Flat_Rate_Commission"),
        ("EES_Flat_Rate_CN_Commission", "Wesco_Flat_Rate_CN_Commission"),
        ("90156-Rucker-EES ISR", "90156-Rucker-Wesco ISR"),
        ("2025 EES Flat Rate Plan", "2026 Wesco Flat Rate Plan"),
        ("EES ISR, EES OSR", "Wesco ISR, Wesco OSR"),
        ("EES ISR", "Wesco ISR"),
        ("EES OSR", "Wesco OSR"),
        ("EES Flat Rate", "Wesco Flat Rate"),
        ("EES", "Wesco"),
        ("Load_DDP_Clawback", "Load_DataLake_Clawback"),
        ("DDP_Clawback_", "DataLake_Clawback_"),
        ("Order Type as ‘DDP’", "Order Type as ‘DataLake’"),
        ("Order Type as 'DDP'", "Order Type as 'DataLake'"),
        ("Order Type = “DDP”", "Order Type = “DataLake”"),
        ("Order Type = \"DDP\"", "Order Type = \"DataLake\""),
        ("Order Type Name", "Order Type Name"),  # no-op anchor
        ("‘DDP’", "‘DataLake’"),
        ("'DDP'", "'DataLake'"),
        ("“DDP”", "“DataLake”"),
        ("DDP,", "DataLake,"),
        ("DDP ", "DataLake "),
        (" DDP", " DataLake"),
        ("Yearly", "Yearly"),
        ("YEAR-2025", "YEAR-2026"),
        ("QTR-1-2025", "QTR-1-2026"),
        ("QTR-2-2025", "QTR-2-2026"),
        ("QTR-3-2025", "QTR-3-2026"),
        ("QTR-4-2025", "QTR-4-2026"),
        ("JAN-2025", "JAN-2026"),
        ("FEB-2025", "FEB-2026"),
        ("MAR-2025", "MAR-2026"),
        ("APR-2025", "APR-2026"),
        ("MAY-2025", "MAY-2026"),
        ("JUN-2025", "JUN-2026"),
        ("JUL-2025", "JUL-2026"),
        ("AUG-2025", "AUG-2026"),
        ("SEP-2025", "SEP-2026"),
        ("OCT-2025", "OCT-2026"),
        ("NOV-2025", "NOV-2026"),
        ("DEC-2025", "DEC-2026"),
        ("01/01/2025", "01/01/2026"),
        ("01/31/2025", "01/31/2026"),
        ("02/01/2025", "02/01/2026"),
        ("02/28/2025", "02/28/2026"),
        ("03/01/2025", "03/01/2026"),
        ("03/31/2025", "03/31/2026"),
        ("04/01/2025", "04/01/2026"),
        ("04/30/2025", "04/30/2026"),
        ("05/01/2025", "05/01/2026"),
        ("05/31/2025", "05/31/2026"),
        ("06/01/2025", "06/01/2026"),
        ("06/30/2025", "06/30/2026"),
        ("07/01/2025", "07/01/2026"),
        ("07/31/2025", "07/31/2026"),
        ("08/01/2025", "08/01/2026"),
        ("08/31/2025", "08/31/2026"),
        ("09/01/2025", "09/01/2026"),
        ("09/30/2025", "09/30/2026"),
        ("10/01/2025", "10/01/2026"),
        ("10/31/2025", "10/31/2026"),
        ("11/01/2025", "11/01/2026"),
        ("11/30/2025", "11/30/2026"),
        ("12/01/2025", "12/01/2026"),
        ("12/31/2025", "12/31/2026"),
        ("01/15/2025", "01/15/2026"),
        ("02/10/2025", "02/10/2026"),
        ("09/10/2024", "09/10/2025"),
        ("2025 plan year", "2026 plan year"),
        ("2025 plans", "2026 plans"),
        ("2025 plan", "2026 plan"),
        ("2025 commission calendar", "2026 commission calendar"),
        ("JAN-2024", "JAN-2026"),
    ]
    replace_everywhere(doc, mapping)

    # Remaining bare DDP cells (design summary etc.)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip() == "DDP":
                    set_cell_text(cell, "DataLake", size=9, bold=False, shade=False)
                elif cell.text.strip() == "DDP, Clawback":
                    set_cell_text(cell, "DataLake, Clawback", size=9)


def update_cover_and_history(doc: Document):
    # Cover SOW line already renamed; add Connect+Incent subtitle if missing
    sow = find_paragraph(doc, exact="SOW-14")
    if sow:
        # ensure cover lines stay 28pt Century Gothic
        set_paragraph_text(sow, "SOW-14", size=28, bold=False)
        nxt = sow
        # Insert subtitle after SOW-14 if not present
        following = sow._p.getnext()
        # add a subtitle paragraph
        sub = insert_paragraph_after(sow, "Connect & Incent — Plan Year 2026", size=14, bold=False)

    # Document history table (first table)
    hist = doc.tables[0]
    # Clear extra history rows beyond header+1, set new row
    rows_wanted = [
        ["Version", "Date", "SOW / CO", "Author(s)", "Comments / Summary of Updates"],
        [
            "0.1",
            "09/22/2026",
            "SOW-14",
            "K Sai Kiran / Sireesh Kumar",
            "Initial SOW-14 FRD from Wesco SOW16 baseline. Plan year 2026. "
            "EES renamed to Wesco; DDP renamed to DataLake. Section 4 (DATA) rewritten for "
            "DataLake SFTP load and Connect pipeline UploadDataLake. Approvers updated.",
        ],
    ]
    fill_existing_table(hist, rows_wanted, header_rows=1)
    # history headers in baseline may not be shaded — leave as template


def update_plan_summary_table(doc: Document):
    # Table 2 plan summary
    plan = doc.tables[2]
    # header + one data row
    fill_existing_table(
        plan,
        [
            ["Plan Number", "Plan Name", "Title Name(s)", "Approximate Number of Payees on Plan", "Comments"],
            ["01", "2026 Wesco Flat Rate Plan", "Wesco ISR, Wesco OSR", "", ""],
        ],
        header_rows=1,
    )


def update_data_summary_table(doc: Document):
    # Table 5 — data type summary under DATA
    data_sum = doc.tables[5]
    fill_existing_table(
        data_sum,
        [
            ["Data Type", "Source", "Volume", "Upload Frequency", "File Period", "Currency Type", "Order Type Name(s)"],
            ["DataLake Orders", "SFTP", "~60k+ rows / month (sample Jun-2026)", "Daily", "Daily / MTD", "USD", "DataLake"],
            ["Clawback Orders", "SFTP", "", "Weekly", "YTD", "USD", "Clawback Order"],
        ],
        header_rows=1,
    )


def rebuild_data_section(doc: Document):
    """Replace inbound process content between data summary and PLAN COMPONENT DETAILS."""
    data_heading = find_paragraph(doc, exact="DATA")
    plan_heading = find_paragraph(doc, exact="PLAN COMPONENT DETAILS")
    assert data_heading and plan_heading

    # Update DATA intro paragraph (first normal para after DATA)
    # Find children after DATA
    body = doc.element.body
    children = list(body.iterchildren())
    data_i = children.index(data_heading._p)
    plan_i = children.index(plan_heading._p)

    # Keep: DATA heading + intro para + data summary table (table5)
    # Identify table5 element
    table5_tbl = doc.tables[5]._tbl
    # Remove everything after table5 until plan_heading
    children = list(body.iterchildren())
    t5_i = children.index(table5_tbl)
    plan_i = children.index(plan_heading._p)
    for elem in children[t5_i + 1 : plan_i]:
        body.remove(elem)

    # Update intro text under DATA
    # paragraph immediately after DATA heading
    intro = None
    for p in doc.paragraphs:
        if "source data that will be loaded into Incent" in p.text or "source data that will be loaded" in p.text:
            intro = p
            break
    if intro:
        set_paragraph_text(
            intro,
            "This section defines all of Wesco’s source data that will be loaded into Incent for SOW-14. "
            "The primary inbound order feed is DataLake (replacing the prior DDP feed). Files are placed "
            "on SFTP and processed by Xactly Connect (UploadDataLake), then mapped into Incent standard "
            "and custom order fields. Clawback remains a secondary inbound process.",
            size=10,
        )

    # Anchor = table5
    anchor_p = None
    # Insert a blank paragraph after table5 to hang content on
    # Create paragraph element after table5
    new_p = OxmlElement("w:p")
    table5_tbl.addnext(new_p)
    cursor = Paragraph(new_p, data_heading._parent)

    def add_p(text, style=None, size=10, bold=False, color=None):
        nonlocal cursor
        cursor = insert_paragraph_after(cursor, text=text, style=style, size=size, bold=bold, color=color)
        if style and style.startswith("Heading"):
            # re-apply style colors via run
            clear_paragraph(cursor)
            cursor.style = style
            run = cursor.add_run(text)
            set_run_font(run, name=FONT, bold=True, color=H1_COLOR if style == "Heading 1" else H2_COLOR,
                         size=16 if style == "Heading 1" else (13 if style == "Heading 2" else 11))
        return cursor

    def add_tbl(rows, header_rows=1):
        nonlocal cursor
        # insert empty para then table after it
        cursor = insert_paragraph_after(cursor, text="")
        table = insert_table_after(cursor, rows, header_rows=header_rows)
        # move cursor to a new para after table
        new_after = OxmlElement("w:p")
        table._tbl.addnext(new_after)
        cursor = Paragraph(new_after, data_heading._parent)
        return table

    # Clear the initial empty cursor text
    set_paragraph_text(cursor, "")

    add_p("Inbound Process 1 - Load_DataLake", style="Heading 2")
    add_p(
        "Final SFTP load file format is based on DataLake_YYYY-MM-DD (sample reference: DataLake_2026-06-30). "
        "Connect selects the latest matching file from /inbound/."
    )
    add_tbl(DATALAKE_FILE_ATTRS, header_rows=2)
    add_p("When placed on the SFTP, the DataLake file will have the following columns, headers and expected format:")
    add_tbl(DATALAKE_COLUMNS, header_rows=1)
    add_p("The files detailed above will be mapped into Incent as follows:")
    add_tbl(DATALAKE_MAPPING, header_rows=0)  # peach on first rows manually
    # shade key header rows in mapping table — re-get last tables
    map_table = doc.tables[-1]
    for ri in (0, 1, 2, 22):  # Record/Source/Standard header/Custom header
        if ri < len(map_table.rows):
            for cell in map_table.rows[ri].cells:
                shade_cell(cell)
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.bold = True

    add_p("Field Derivation Details", style="Heading 3")
    add_tbl(
        [
            ["Order Field Name", "Derivation", "Example"],
            [
                "Order Code",
                "Concatenate invoice_number, underscore, and invoice_date.",
                "S6437712.001_2026-06-26",
            ],
            [
                "Item Code",
                "Concatenate invoice_line_number, underscore, and branch_shipment_type.",
                "18_S",
            ],
            [
                "Amount",
                "sales_amount from DataLake. Flat Rate GP Credit uses employee split of Order Amount "
                "minus (COST_AMT * SplitPercentage).",
                "sales_amount=4.69; cost_amount=2.82",
            ],
            [
                "Employee ID / Split %",
                "TMCA validate/upload/calculate using OSR/ISR; join credited transactions to participants; "
                "write prestage_order_item_assignment; suffix order/batch with business group before Incent upload.",
                "OSR/ISR resolved to employee_id via TMCA",
            ],
            [
                "Batch Name",
                "'DataLake_' || period end date; append business group and sequence suffix at staging.",
                "DataLake_2026-06-30_BG_001",
            ],
        ],
        header_rows=1,
    )

    add_p("Error Identification", style="Heading 3")
    add_p(
        "In order for the transactions to be loaded successfully, the following scenarios will be evaluated "
        "for data integrity in Connect before staging to Incent."
    )
    add_tbl(VALIDATIONS, header_rows=1)

    add_p("Connect Pipeline Structure — UploadDataLake", style="Heading 3")
    add_p(
        "Pipeline structure follows Xactly Connect standards used in the UploadDDP pattern. Object and "
        "variable names are updated for DataLake; mapping fields follow the tables above."
    )
    for b in PIPELINE_BULLETS:
        cursor = insert_paragraph_after(cursor, text=b, size=10)
        # bullet-like prefix
        set_paragraph_text(cursor, "• " + b, size=10)

    add_p("Inbound Process 2 - Load_DataLake_Clawback", style="Heading 2")
    add_p(
        "Clawback inbound processing remains as designed in the prior Wesco SOW16 FRD, with references to "
        "prior DDP orders updated to DataLake order type for lookup of original invoices."
    )
    add_tbl(
        [
            ["Source File: DataLake_Clawback_<<Period_Name>>.csv", "Source File: DataLake_Clawback_<<Period_Name>>.csv"],
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
        header_rows=2,
    )
    add_p("When placed on the SFTP, the Clawback file will have the following columns, headers and expected format:")
    add_tbl(
        [
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
        ],
        header_rows=1,
    )
    add_p("The files detailed above will be mapped into Incent as follows:")
    add_tbl(
        [
            ["Record Type", "Billings", ""],
            ["Source", "SFTP: Flat file", ""],
            ["Xactly Standard Order Fields", "Source / Derivation", "NOTES"],
            ["Order Code", "Invoice_ID (Transaction_Number)", ""],
            ["Item Code", "Transaction_Date", ""],
            ["Batch Name", "Clawback_<Incent Period Name>'_'<SEQ>", "Ex. Clawback_JAN-2026_001"],
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
        header_rows=0,
    )
    claw_map = doc.tables[-1]
    for ri in (0, 1, 2, 22):
        if ri < len(claw_map.rows):
            for cell in claw_map.rows[ri].cells:
                shade_cell(cell)
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.bold = True

    add_p("Field Derivation Details", style="Heading 3")
    add_tbl(
        [
            ["Order Field Name", "Derivation", "Example"],
            [
                "Amount",
                "Step 1: Lookup Invoice ID (transaction number) from the Clawback file in Xactly Incent Orders "
                "for current and prior month with Order Type as ‘DataLake’. "
                "Step 2: If no clawback paid previously, aggregate commission paid for the invoice, multiply by -1, map to Amount. "
                "Step 3: If clawback paid in past 180 days and customer pays within 180 days of clawback payment month-end, "
                "generate positive clawback = prior clawback amount * -1. "
                "Paid-invoice indicator: invoice drops off Clawback file; Connect checks absence of prior clawback invoice IDs.",
                "If clawback was -$1800 and customer paid within 180 days, positive clawback $1800 for ISR/OSR.",
            ],
            [
                "Employee_ID_1 / Employee_ID_2",
                "Lookup matching DataLake order by invoice ID; assign employee IDs from the first matching Incent transaction.",
                "",
            ],
        ],
        header_rows=1,
    )
    add_p("Error Identification", style="Heading 3")
    add_p("In order for the transactions to be loaded successfully, the following scenarios will be evaluated for data integrity.")
    add_tbl(
        [
            ["Reject Reason No.", "Category", "Reject Reason"],
            ["Reject-01", "FAIL", "ERROR: Invoice not found in Xactly Incent"],
            ["Reject-02", "FAIL", "ERROR: Clawback already done and Invoice unpaid over 270 days"],
        ],
        header_rows=1,
    )
    add_p(
        "For reject 2 – count the number of days from Invoice paid date (incentive date on the first invoice "
        "associated with the invoice ID). If the days passed is >180, evaluate unpaid window rules as above."
    )


def update_acceptance(doc: Document):
    """Replace acceptance block people with SOW-14 roster."""
    acc = find_paragraph(doc, exact="DOCUMENT ACCEPTANCE")
    if not acc:
        return
    # Collect paragraphs after acceptance until end
    body = doc.element.body
    children = list(body.iterchildren())
    start = children.index(acc._p)
    # Remove all following paragraphs/tables until sectPr
    for elem in children[start + 1 :]:
        if elem.tag == qn("w:sectPr"):
            break
        body.remove(elem)

    cursor = acc

    def line(text, bold=False, size=10):
        nonlocal cursor
        cursor = insert_paragraph_after(cursor, text=text, size=size, bold=bold)

    line("")
    line("Wesco:", bold=True, size=11)
    line("Approved by:\tMichael")
    line("Title:\t\t[PENDING CLIENT CLARIFICATION]")
    line("Signature:")
    line("Date:")
    line("")
    line("Approved by:\tJake")
    line("Title:\t\t[PENDING CLIENT CLARIFICATION]")
    line("Signature:")
    line("Date:")
    line("")
    line("Xactly Corporation:", bold=True, size=11)
    line("Approved by:\tNabanitha")
    line("Title:\t\tProject Manager")
    line("Signature:")
    line("Date:")
    line("")
    line("Approved by:\tSireesh Kumar")
    line("Title:\t\tLead Consultant")
    line("Signature:")
    line("Date:")
    line("")
    line("Approved by:\tK Sai Kiran")
    line("Title:\t\tSenior Consultant")
    line("Signature:")
    line("Date:")


def update_component_examples_order_type(doc: Document):
    """Ensure example order type cells show DataLake where blank/old."""
    for table in doc.tables:
        # header contains Order Type
        headers = [c.text.strip() for c in table.rows[0].cells]
        if "Order Type" in headers:
            idx = headers.index("Order Type")
            for ri, row in enumerate(table.rows[1:], start=1):
                cell = row.cells[idx]
                val = cell.text.strip()
                if val == "" or val == "DDP" or val == "DataLake":
                    # Flat rate examples should be DataLake; clawback tables already set
                    # Heuristic: if Amount looks negative or Order Type already Clawback, skip
                    pass
                if val == "":
                    # check sibling for Clawback Order in other rows of same table
                    set_cell_text(cell, "DataLake", size=9)


def polish_cover_fonts(doc: Document):
    for label in ("Xactly Corporation", "Functional Requirements", "Wesco", "SOW-14"):
        p = find_paragraph(doc, exact=label)
        if p:
            set_paragraph_text(p, label, size=28, bold=False)
    p = find_paragraph(doc, exact="DOCUMENT HISTORY")
    if p:
        set_paragraph_text(p, "DOCUMENT HISTORY", size=12, bold=True)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    work = OUT_DIR / "_sow14_work.docx"
    shutil.copy2(BASE, work)
    doc = Document(str(work))

    apply_global_renames(doc)
    polish_cover_fonts(doc)
    update_cover_and_history(doc)
    update_plan_summary_table(doc)
    update_data_summary_table(doc)
    rebuild_data_section(doc)
    update_component_examples_order_type(doc)
    update_acceptance(doc)

    # Final leftover DDP/EES/SOW16/2025 plan-year cleanup in paragraphs
    replace_everywhere(
        doc,
        [
            ("prior DDP feed", "prior DDP feed"),  # keep historical mention in DATA intro
            ("UploadDDP", "UploadDDP"),  # keep as pattern reference in Connect section
        ],
    )

    out_path = OUT_DIR / OUT_NAME
    art_path = ARTIFACT_DIR / OUT_NAME
    # also timestamped immutable artifact
    art_ts = ARTIFACT_DIR / "Wesco_SOW14_FRD_v1_Connect_Incent_xactly_style_20260922.docx"

    doc.save(str(out_path))
    doc.save(str(art_path))
    doc.save(str(art_ts))

    # zip pack
    import zipfile

    zpath = ARTIFACT_DIR / "Wesco_SOW14_FRD_xactly_style_download.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out_path, OUT_NAME)
        csv = OUT_DIR / "section4_datalake_order_field_mapping.csv"
        if csv.exists():
            z.write(csv, csv.name)
        z.writestr(
            "README.txt",
            "Wesco SOW-14 FRD (Xactly template style)\n"
            f"- {OUT_NAME}\n"
            "Built from Wesco SOW16 FRD v2 Xactly house template.\n",
        )

    print("Wrote", out_path)
    print("Wrote", art_path)
    print("Wrote", art_ts)
    print("Wrote", zpath)


if __name__ == "__main__":
    main()
