#!/usr/bin/env python3
"""
Refresh pool data from the live Google Sheet, then rebuild index.html.

Run locally:        python3 scripts/update.py
Run in CI (Action): same command on a schedule.

What it does:
  1. Downloads the latest standings (everyone's picks + Score) from the sheet's
     CSV export endpoint -> data/standings.csv
  2. Calls build.py to regenerate index.html with the fresh snapshot baked in.

Note: the dashboard ALSO fetches the sheet live in the browser on every load,
so this script is only needed to refresh the *offline fallback* snapshot and to
update the hosted (GitHub Pages) copy. Match results entered in the browser are
stored per-user and are not overwritten here; to bake results into the shared
copy, edit KNOWN_RESULTS in build.py.
"""
import os, sys, urllib.request, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHEET_ID = "1CAtVLI4V07gAlfaTcKehua-6HmIg-hDCHNUnXWhh5d4"
GID = "1365959132"
URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&gid={GID}"

def main():
    print("Fetching latest standings from sheet…")
    try:
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        csv_text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    except Exception as e:
        print(f"  ! could not reach sheet ({e}); keeping existing snapshot")
        csv_text = None

    if csv_text and "Last Name" in csv_text:
        # keep only the 14 meaningful columns, drop trailing empties
        out_lines = []
        import csv, io
        for row in csv.reader(io.StringIO(csv_text)):
            row = row[:14]
            if not row or not row[0].strip():
                continue
            out_lines.append(",".join('"%s"' % c.replace('"','""') if ("," in c or '"' in c) else c for c in row))
        with open(os.path.join(ROOT, "data", "standings.csv"), "w", encoding="utf-8") as f:
            f.write("\n".join(out_lines) + "\n")
        print(f"  saved {len(out_lines)-1} entrants")
    else:
        print("  ! response did not look like the standings sheet; keeping snapshot")

    print("Rebuilding index.html…")
    subprocess.check_call([sys.executable, os.path.join(HERE, "build.py")])

if __name__ == "__main__":
    main()
