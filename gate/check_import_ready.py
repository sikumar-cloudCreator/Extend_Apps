#!/usr/bin/env python3
"""check_import_ready.py — will this bundle actually IMPORT into Extend?

The render/export gates check whether a page is structurally sound and whether it
will WORK once loaded. This one checks the step before that: whether the importer
will accept the bundle at all. Every rule here is a real failure observed on the
ClaimRequest bundle (2026-09-05), which passed every other gate and still would
not import.

  I1  ADLC.json must sit at the ARCHIVE ROOT (no wrapping directory)      -> ERROR
  I2  every id (applicationId, landingPageId, pageDefinitionId, controlId)
      must be a parseable UUID - LLM-invented ids like
      "c1a1m000-0000-4000-8000-claimrequest01" are UUID-SHAPED but not hex  -> ERROR
  I3  a query object's xsql must be a BARE SELECT; the importer builds the
      DDL from name+schemaName, so an embedded "CREATE VIEW x AS" doubles it -> ERROR
  I4  every CSV in tables/data must have exactly the column count of its
      declared schema, header included                                    -> ERROR
  I5  every path named in ADLC.json must resolve, and every shipped file
      must be named in ADLC.json                                          -> ERROR
  I6  no .DS_Store / __MACOSX junk in the bundle                          -> WARN
  I7  events[].id must point at a controlId that exists on the page       -> ERROR

Usage:  python check_import_ready.py <bundle_dir_or_zip>
Exit 0 iff no ERRORs.
"""
import sys, os, re, json, glob, csv, uuid, zipfile, tempfile, shutil

ERRORS, WARNS = [], []
def err(m): ERRORS.append(m)
def warn(m): WARNS.append(m)

def is_uuid(v):
    try:
        uuid.UUID(str(v)); return True
    except Exception:
        return False

def check_archive_root(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    if "ADLC.json" not in names:
        roots = sorted({n.split("/")[0] for n in names if "/" in n})
        err(f"I1 ADLC.json is not at the archive root. Top-level entries: {roots}. "
            f"Zip from INSIDE the bundle dir: `zip -r out.zip ADLC.json app queries tables ...`, "
            f"never `zip -r out.zip <bundledir>`.")

def check_ids(root):
    ap_p = os.path.join(root, "app", "Application.json")
    if os.path.exists(ap_p):
        ap = json.load(open(ap_p))
        for k in ("applicationId", "landingPageId"):
            v = ap.get(k)
            if v is not None and not is_uuid(v):
                err(f"I2 Application.json/{k} is not a valid UUID: {v!r}")
    for f in glob.glob(os.path.join(root, "app", "*.json")):
        if os.path.basename(f) == "Application.json":
            continue
        j = json.load(open(f))
        pid = j.get("pageDefinitionId")
        if pid is not None and not is_uuid(pid):
            err(f"I2 {os.path.relpath(f,root)}/pageDefinitionId is not a valid UUID: {pid!r}")
        if pid and os.path.basename(f)[:-5] != pid:
            err(f"I2 {os.path.relpath(f,root)} filename does not match its pageDefinitionId {pid!r}")
        ids, refs, bad = set(), [], []
        def walk(o):
            if isinstance(o, dict):
                cid = o.get("controlId")
                if cid is not None:
                    ids.add(cid)
                    if not is_uuid(cid): bad.append(cid)
                for e in (o.get("events") or []):
                    if e.get("id"): refs.append(e["id"])
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(j)
        if bad:
            err(f"I2 {os.path.relpath(f,root)}: {len(bad)} controlId(s) are not valid UUIDs, "
                f"e.g. {sorted(set(bad))[:3]}")
        dangling = sorted({r for r in refs if r not in ids})
        if dangling:
            err(f"I7 {os.path.relpath(f,root)}: {len(dangling)} events[].id reference no control "
                f"on the page, e.g. {dangling[:3]}")

def check_queries(root):
    for f in glob.glob(os.path.join(root, "queries", "*", "*.json")):
        j = json.load(open(f))
        x = (j.get("xsql") or "").lstrip()
        if re.match(r"(?is)^create\s+(or\s+replace\s+)?view\b", x):
            err(f"I3 {os.path.relpath(f,root)}: xsql embeds a CREATE VIEW statement. The importer "
                f"builds the DDL from name+schemaName - store a BARE SELECT.")

def check_table_data(root):
    adlc_p = os.path.join(root, "ADLC.json")
    if not os.path.exists(adlc_p): return
    a = json.load(open(adlc_p))
    schemas = {}
    for s in (a.get("tables") or {}).get("schemas") or []:
        p = os.path.join(root, s)
        if os.path.exists(p):
            j = json.load(open(p))
            schemas[f"{j['schemaName']}.{j['tableName']}"] = [c["name"] for c in j.get("columns") or []]
    for d in (a.get("tables") or {}).get("data") or []:
        cols = schemas.get(d.get("name"))
        p = os.path.join(root, d.get("path", ""))
        if not cols or not os.path.exists(p): continue
        rows = list(csv.reader(open(p, newline="")))
        if not rows: continue
        if rows[0] != cols:
            err(f"I4 {d['path']}: header does not match the declared columns of {d['name']}")
        ragged = [i + 1 for i, r in enumerate(rows) if len(r) != len(cols)]
        if ragged:
            err(f"I4 {d['path']}: {len(ragged)} row(s) do not have {len(cols)} fields "
                f"(lines {ragged[:6]}) - a short row shifts every later column left.")

def check_manifest(root):
    adlc_p = os.path.join(root, "ADLC.json")
    if not os.path.exists(adlc_p):
        err("I5 ADLC.json missing from the bundle root"); return
    a = json.load(open(adlc_p))
    listed = []
    if a.get("application"): listed.append(a["application"])
    for k in ("queries", "pageDefinitions", "workflows", "policySets"):
        listed += list(a.get(k) or [])
    tb = a.get("tables") or {}
    listed += list(tb.get("schemas") or [])
    listed += [d["path"] for d in (tb.get("data") or []) if d.get("path")]
    for rel in listed:
        if not os.path.exists(os.path.join(root, rel)):
            err(f"I5 ADLC.json names a file that is not in the bundle: {rel}")
    listed_set = set(listed)
    for dirpath, _, files in os.walk(root):
        for fn in files:
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            if rel == "ADLC.json": continue
            if ".DS_Store" in rel or "__MACOSX" in rel:
                warn(f"I6 junk file shipped in the bundle: {rel}"); continue
            if rel.split(os.sep)[0] in ("app", "queries", "tables", "workflows", "policy_sets") \
               and rel not in listed_set:
                err(f"I5 file shipped but not named in ADLC.json: {rel}")

def run(target):
    tmp = None
    if target.endswith(".zip"):
        check_archive_root(target)
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(target) as z: z.extractall(tmp)
        inner = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
        root = os.path.join(tmp, inner[0]) if not os.path.exists(os.path.join(tmp, "ADLC.json")) and len(inner) == 1 else tmp
    else:
        root = target
    check_manifest(root); check_ids(root); check_queries(root); check_table_data(root)
    if tmp: shutil.rmtree(tmp, ignore_errors=True)

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    run(sys.argv[1])
    for w in WARNS: print(f"  WARN : {w}")
    if ERRORS:
        print(f"\n✗ {len(ERRORS)} ERROR(S):")
        for e in ERRORS: print(f"  ERROR: {e}")
        print("\n✗ FAIL - this bundle will not import.")
        return 1
    print(f"\n✓ PASS - bundle is import-ready" + (f" ({len(WARNS)} warning(s))" if WARNS else "."))
    return 0

if __name__ == "__main__":
    sys.exit(main())
