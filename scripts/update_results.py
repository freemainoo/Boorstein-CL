#!/usr/bin/env python3
"""
Hourly auto-updater for the Boorstein World Cup tracker.

Does two things, then rebuilds index.html:
  1. Pulls the latest pool standings (everyone's picks + Score) from the Google
     Sheet -> data/standings.csv
  2. Pulls live 2026 World Cup match results, maps each finished match to our
     fixtures (by team pair, orientation-aware) -> data/results.json

Match-result sources (first available wins):
  1. football-data.org  — set env DC_FOOTBALL_TOKEN (free key). Best data.
  2. TheSportsDB free   — keyless fallback.

Run:
  DC_FOOTBALL_TOKEN=xxxx python3 scripts/update_results.py
  python3 scripts/update_results.py --selftest   # offline mapping test
"""
import os, sys, io, csv, json, re, datetime, unicodedata, urllib.request, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
sys.path.insert(0, HERE)
import build  # reuse GROUP_SCHEDULE, REAL_GROUPS, SHEET

# ---------- 1. Google Sheet -> standings.csv ----------
def refresh_sheet():
    url = f"https://docs.google.com/spreadsheets/d/{build.SHEET['id']}/gviz/tq?tqx=out:csv&gid={build.SHEET['gid']}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    except Exception as e:
        print(f"  ! sheet fetch failed ({e}); keeping existing standings"); return
    if "Last Name" not in text:
        print("  ! sheet response unexpected; keeping existing standings"); return
    out = []
    for row in csv.reader(io.StringIO(text)):
        row = row[:14]
        if not row or not row[0].strip(): continue
        out.append(",".join('"%s"' % c.replace('"','""') if ("," in c or '"' in c) else c for c in row))
    with open(os.path.join(DATA, "standings.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print(f"  sheet: saved {len(out)-1} entrants")

# ---------- 2. live results -> results.json ----------
ALIASES = {
    "korea republic":"South Korea","south korea":"South Korea","republic of korea":"South Korea",
    "cote d'ivoire":"Ivory Coast","côte d'ivoire":"Ivory Coast","ivory coast":"Ivory Coast",
    "usa":"United States","united states":"United States","united states of america":"United States",
    "turkiye":"Turkiye","turkey":"Turkiye","türkiye":"Turkiye",
    "czechia":"Czechia","czech republic":"Czechia",
    "dr congo":"Congo DR","democratic republic of congo":"Congo DR","congo dr":"Congo DR",
    "curacao":"Curacao","curaçao":"Curacao",
    "bosnia and herzegovina":"Bosnia and Herzegovina","bosnia & herzegovina":"Bosnia and Herzegovina",
    "cape verde":"Cape Verde","cabo verde":"Cape Verde",
    "iran":"Iran","ir iran":"Iran","islamic republic of iran":"Iran",
}
TEAMS = {t for ts in build.REAL_GROUPS.values() for t in ts}
def canon(name):
    if not name: return None
    n = unicodedata.normalize("NFKD", name).encode("ascii","ignore").decode().strip().lower()
    if n in ALIASES: return ALIASES[n]
    return " ".join(w.capitalize() for w in n.split())
def _sq(s):  # squash to letters/digits only, dropping "and" — separator-insensitive
    s = unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode().lower()
    s = re.sub(r"\band\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)
def resolve(name):
    if not name or not str(name).strip(): return None   # TBD / null knockout slot
    c = canon(name)
    if c in TEAMS: return c
    cl = (c or "").lower()
    for t in TEAMS:
        if t.lower() == cl: return t
    s = _sq(name)
    if len(s) < 4: return None                            # too short to match safely
    for t in TEAMS:
        ts = _sq(t)
        if len(ts) >= 4 and (ts in s or s in ts): return t
    return None

PAIR_TO = {}
for (num,grp,md,date,venue,home,away) in build.GROUP_SCHEDULE:
    PAIR_TO[frozenset((home,away))] = (num, home, away)

def record(api_home, api_away, hs, as_):
    h, a = resolve(api_home), resolve(api_away)
    if not h or not a: return None
    key = frozenset((h, a))
    if key not in PAIR_TO: return None
    num, myH, myA = PAIR_TO[key]
    res = (int(hs), int(as_)) if h == myH else (int(as_), int(hs))
    return num, res

ROUND_MAP = {"LAST_32":"R32","LAST_16":"R16","QUARTER_FINALS":"QF",
             "SEMI_FINALS":"SF","THIRD_PLACE":"BRONZE","FINAL":"FINAL"}

def fetch_football_data(token):
    url = "https://api.football-data.org/v4/competitions/WC/matches"
    req = urllib.request.Request(url, headers={"X-Auth-Token": token})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    out, unmapped, ko = {}, [], []
    for m in data.get("matches", []):
        stage = m.get("stage")
        ft = m.get("score", {}).get("fullTime", {})
        fin = m.get("status") == "FINISHED"
        if stage in ROUND_MAP:  # knockout
            h = resolve((m.get("homeTeam") or {}).get("name"))
            a = resolve((m.get("awayTeam") or {}).get("name"))
            if not h or not a or h == a: continue
            pkw = None
            if m.get("score", {}).get("duration") == "PENALTY_SHOOTOUT":
                w = m["score"].get("winner")
                pkw = h if w=="HOME_TEAM" else a if w=="AWAY_TEAM" else None
            ko.append({"round": ROUND_MAP[stage], "home": h, "away": a,
                       "hs": ft.get("home"), "as": ft.get("away"),
                       "status": "final" if fin else "scheduled", "pkWinner": pkw,
                       "date": (m.get("utcDate") or "")[:10]})
            continue
        if not fin or ft.get("home") is None: continue
        r = record(m["homeTeam"]["name"], m["awayTeam"]["name"], ft["home"], ft["away"])
        if r: out[r[0]] = r[1]
        else: unmapped.append(f'{m["homeTeam"]["name"]} vs {m["awayTeam"]["name"]}')
    if unmapped: print("  ⚠ unmapped FINISHED matches:", " | ".join(unmapped))
    return out, ko

def fetch_sportsdb():
    league = os.environ.get("DC_SPORTSDB_LEAGUE", "4429")
    url = f"https://www.thesportsdb.com/api/v1/json/3/eventsseason.php?id={league}&s=2026"
    data = json.load(urllib.request.urlopen(url, timeout=30))
    out = {}
    for e in (data.get("events") or []):
        hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
        if hs is None or as_ is None: continue
        r = record(e.get("strHomeTeam"), e.get("strAwayTeam"), hs, as_)
        if r: out[r[0]] = r[1]
    return out

def refresh_results():
    token = os.environ.get("DC_FOOTBALL_TOKEN")
    results, ko, src = {}, [], None
    try:
        if token: results, ko = fetch_football_data(token); src = "football-data.org"
        else:      results = fetch_sportsdb(); src = "TheSportsDB"
    except Exception as e:
        print("  ! live result fetch failed:", e)
    if not results and not ko:
        print("  results: none fetched; leaving results.json unchanged"); return
    payload = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "source": src, "results": {str(k): list(v) for k, v in results.items()},
               "knockout": ko}
    json.dump(payload, open(os.path.join(DATA, "results.json"), "w"), indent=2)
    print(f"  results: wrote {len(results)} group + {len(ko)} knockout from {src}")

def selftest():
    samples=[("Mexico","South Africa",2,0),("Korea Republic","Czechia",2,1),
             ("Côte d'Ivoire","Ecuador",1,0),("Germany","Curaçao",7,1),("Sweden","Tunisia",5,1)]
    ok=sum(1 for h,a,hs,as_ in samples if record(h,a,hs,as_)); print(f"selftest {ok}/{len(samples)}")
    return ok==len(samples)

def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    print("Refreshing sheet standings…");  refresh_sheet()
    print("Refreshing live results…");      refresh_results()
    print("Rebuilding index.html…")
    subprocess.check_call([sys.executable, os.path.join(HERE, "build.py")])

if __name__ == "__main__":
    main()
