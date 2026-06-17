#!/usr/bin/env python3
"""
Build the self-contained World Cup pick'em dashboard.

Pipeline:
  data/standings.csv  (pool snapshot)  ─┐
  WORLDCUP structure (this file)        ─┼─►  inject into scripts/template.html  ─►  index.html
  KNOWN_RESULTS (this file)             ─┘                                          + data/*.json

Re-run any time:  python3 scripts/build.py
"""
import csv, json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

SHEET = {"id": "1CAtVLI4V07gAlfaTcKehua-6HmIg-hDCHNUnXWhh5d4", "gid": "1365959132"}
ME = "Debiche"

# ---- 12 ability groups (the pool's custom tiers). Groups 9-12 score DOUBLE. ----
CONTEST_GROUPS = {
    1:  ["Argentina","England","France","Spain"],
    2:  ["Brazil","Germany","Netherlands","Portugal"],
    3:  ["Belgium","Colombia","Morocco","Norway"],
    4:  ["Mexico","United States","Uruguay","Japan"],
    5:  ["Croatia","Switzerland","Ecuador","Turkiye"],
    6:  ["Senegal","Austria","Paraguay","Sweden"],
    7:  ["Canada","Ivory Coast","Czechia","Scotland"],
    8:  ["Egypt","Ghana","Algeria","Bosnia and Herzegovina"],
    9:  ["South Korea","Australia","Tunisia","Iran"],
    10: ["Congo DR","Panama","South Africa","Saudi Arabia"],
    11: ["New Zealand","Iraq","Qatar","Uzbekistan"],
    12: ["Cape Verde","Haiti","Jordan","Curacao"],
}

# ---- Real 2026 World Cup groups (Pos 1-4 order from the official draw). ----
# Names normalized to MATCH the pool sheet (Turkiye, Congo DR, Czechia, Curacao).
REAL_GROUPS = {
    "A": ["Mexico","South Africa","South Korea","Czechia"],
    "B": ["Canada","Bosnia and Herzegovina","Qatar","Switzerland"],
    "C": ["Brazil","Morocco","Haiti","Scotland"],
    "D": ["United States","Paraguay","Australia","Turkiye"],
    "E": ["Germany","Curacao","Ivory Coast","Ecuador"],
    "F": ["Netherlands","Japan","Sweden","Tunisia"],
    "G": ["Belgium","Egypt","Iran","New Zealand"],
    "H": ["Spain","Cape Verde","Saudi Arabia","Uruguay"],
    "I": ["France","Senegal","Iraq","Norway"],
    "J": ["Argentina","Algeria","Austria","Jordan"],
    "K": ["Portugal","Congo DR","Uzbekistan","Colombia"],
    "L": ["England","Croatia","Ghana","Panama"],
}

# ---- Full group-stage schedule, transcribed match-by-match from the official
# FIFA match schedule poster (v17). Tuple: (num, group, matchday, date, venue, home, away).
# Dates are exact per match (a group's two matchday games can fall on different days).
GROUP_SCHEDULE = [
    (1,"A",1,"Jun 11","Mexico City","Mexico","South Africa"),
    (2,"A",1,"Jun 11","Guadalajara","South Korea","Czechia"),
    (3,"B",1,"Jun 12","Toronto","Canada","Bosnia and Herzegovina"),
    (4,"D",1,"Jun 12","Los Angeles","United States","Paraguay"),
    (5,"C",1,"Jun 13","Boston","Haiti","Scotland"),
    (6,"D",1,"Jun 14","Vancouver","Australia","Turkiye"),
    (7,"C",1,"Jun 13","New York NJ","Brazil","Morocco"),
    (8,"B",1,"Jun 13","SF Bay Area","Qatar","Switzerland"),
    (9,"E",1,"Jun 14","Philadelphia","Ivory Coast","Ecuador"),
    (10,"E",1,"Jun 14","Houston","Germany","Curacao"),
    (11,"F",1,"Jun 14","Dallas","Netherlands","Japan"),
    (12,"F",1,"Jun 14","Monterrey","Sweden","Tunisia"),
    (13,"H",1,"Jun 15","Miami","Saudi Arabia","Uruguay"),
    (14,"H",1,"Jun 15","Atlanta","Spain","Cape Verde"),
    (15,"G",1,"Jun 15","Los Angeles","Iran","New Zealand"),
    (16,"G",1,"Jun 15","Seattle","Belgium","Egypt"),
    (17,"I",1,"Jun 16","New York NJ","France","Senegal"),
    (18,"I",1,"Jun 16","Boston","Iraq","Norway"),
    (19,"J",1,"Jun 16","Kansas City","Argentina","Algeria"),
    (20,"J",1,"Jun 16","SF Bay Area","Austria","Jordan"),
    (21,"L",1,"Jun 17","Toronto","Ghana","Panama"),
    (22,"L",1,"Jun 17","Dallas","England","Croatia"),
    (23,"K",1,"Jun 17","Houston","Portugal","Congo DR"),
    (24,"K",1,"Jun 17","Mexico City","Uzbekistan","Colombia"),
    (25,"A",2,"Jun 18","Atlanta","Czechia","South Africa"),
    (26,"B",2,"Jun 18","Los Angeles","Switzerland","Bosnia and Herzegovina"),
    (27,"B",2,"Jun 18","Vancouver","Canada","Qatar"),
    (28,"A",2,"Jun 18","Guadalajara","Mexico","South Korea"),
    (29,"C",2,"Jun 19","Philadelphia","Brazil","Haiti"),
    (30,"C",2,"Jun 19","Boston","Scotland","Morocco"),
    (31,"D",2,"Jun 19","SF Bay Area","Turkiye","Paraguay"),
    (32,"D",2,"Jun 19","Seattle","United States","Australia"),
    (33,"E",2,"Jun 20","Toronto","Germany","Ivory Coast"),
    (34,"E",2,"Jun 20","Kansas City","Ecuador","Curacao"),
    (35,"F",2,"Jun 20","Houston","Netherlands","Sweden"),
    (36,"F",2,"Jun 20","Monterrey","Tunisia","Japan"),
    (37,"H",2,"Jun 21","Miami","Uruguay","Cape Verde"),
    (38,"H",2,"Jun 21","Atlanta","Spain","Saudi Arabia"),
    (39,"G",2,"Jun 21","Los Angeles","Belgium","Iran"),
    (40,"G",2,"Jun 21","Vancouver","New Zealand","Egypt"),
    (41,"I",2,"Jun 22","New York NJ","Norway","Senegal"),
    (42,"I",2,"Jun 22","Philadelphia","France","Iraq"),
    (43,"J",2,"Jun 22","Dallas","Argentina","Austria"),
    (44,"J",2,"Jun 23","SF Bay Area","Jordan","Algeria"),
    (45,"L",2,"Jun 23","Boston","England","Ghana"),
    (46,"L",2,"Jun 23","Toronto","Panama","Croatia"),
    (47,"K",2,"Jun 23","Houston","Portugal","Uzbekistan"),
    (48,"K",2,"Jun 23","Guadalajara","Congo DR","Colombia"),
    (49,"C",3,"Jun 24","Miami","Scotland","Brazil"),
    (50,"C",3,"Jun 24","Atlanta","Morocco","Haiti"),
    (51,"B",3,"Jun 24","Vancouver","Switzerland","Canada"),
    (52,"B",3,"Jun 24","Seattle","Bosnia and Herzegovina","Qatar"),
    (53,"A",3,"Jun 24","Mexico City","Czechia","Mexico"),
    (54,"A",3,"Jun 24","Monterrey","South Africa","South Korea"),
    (55,"E",3,"Jun 25","Philadelphia","Curacao","Ivory Coast"),
    (56,"E",3,"Jun 25","New York NJ","Ecuador","Germany"),
    (57,"F",3,"Jun 25","Dallas","Japan","Sweden"),
    (58,"F",3,"Jun 25","Kansas City","Netherlands","Tunisia"),
    (59,"D",3,"Jun 25","Los Angeles","Turkiye","United States"),
    (60,"D",3,"Jun 25","SF Bay Area","Paraguay","Australia"),
    (61,"I",3,"Jun 26","Boston","Norway","France"),
    (62,"I",3,"Jun 26","Toronto","Senegal","Iraq"),
    (63,"G",3,"Jun 26","Seattle","Egypt","Iran"),
    (64,"G",3,"Jun 26","Vancouver","New Zealand","Belgium"),
    (65,"H",3,"Jun 26","Houston","Cape Verde","Saudi Arabia"),
    (66,"H",3,"Jun 26","Guadalajara","Uruguay","Spain"),
    (67,"L",3,"Jun 27","New York NJ","Panama","England"),
    (68,"L",3,"Jun 27","Philadelphia","Croatia","Ghana"),
    (69,"J",3,"Jun 27","Kansas City","Algeria","Austria"),
    (70,"J",3,"Jun 27","Dallas","Jordan","Argentina"),
    (71,"K",3,"Jun 27","Miami","Colombia","Portugal"),
    (72,"K",3,"Jun 27","Atlanta","Congo DR","Uzbekistan"),
]

# Knockout round dates (round-level; specific teams/venues resolved as the bracket fills).
KO_SCHEDULE = [
    ("Round of 32","Jun 28 – Jul 3"),
    ("Round of 16","Jul 4 – Jul 7"),
    ("Quarter-finals","Jul 9 – Jul 11"),
    ("Semi-finals","Jul 14 – Jul 15"),
    ("Third place","Jul 18"),
    ("Final","Jul 19  ·  MetLife Stadium, NY/NJ"),
]

# ---- Known final results (as of June 14, 2026, midday). Matchday 1 nearly complete. ----
KNOWN_RESULTS = {            # match num : (home_score, away_score)
    1:  (2,0),   # Jun 11  Mexico 2-0 South Africa
    2:  (2,1),   # Jun 11  South Korea 2-1 Czechia
    3:  (1,1),   # Jun 12  Canada 1-1 Bosnia and Herzegovina
    4:  (4,1),   # Jun 12  United States 4-1 Paraguay
    5:  (0,1),   # Jun 13  Haiti 0-1 Scotland
    7:  (1,1),   # Jun 13  Brazil 1-1 Morocco
    8:  (1,1),   # Jun 13  Qatar 1-1 Switzerland
    6:  (2,0),   # Jun 14  Australia 2-0 Turkiye
    10: (7,1),   # Jun 14  Germany 7-1 Curacao
    11: (2,2),   # Jun 14  Netherlands 2-2 Japan
    9:  (1,0),   # Jun 14  Ivory Coast 1-0 Ecuador
    # Not yet final (Jun 14 evening): 12 Sweden-Tunisia
}

# ---- Flags (emoji) ----
FLAGS = {
 "Argentina":"🇦🇷","England":"🏴","France":"🇫🇷","Spain":"🇪🇸","Brazil":"🇧🇷","Germany":"🇩🇪",
 "Netherlands":"🇳🇱","Portugal":"🇵🇹","Belgium":"🇧🇪","Colombia":"🇨🇴","Morocco":"🇲🇦","Norway":"🇳🇴",
 "Mexico":"🇲🇽","United States":"🇺🇸","Uruguay":"🇺🇾","Japan":"🇯🇵","Croatia":"🇭🇷","Switzerland":"🇨🇭",
 "Ecuador":"🇪🇨","Turkiye":"🇹🇷","Senegal":"🇸🇳","Austria":"🇦🇹","Paraguay":"🇵🇾","Sweden":"🇸🇪",
 "Canada":"🇨🇦","Ivory Coast":"🇨🇮","Czechia":"🇨🇿","Scotland":"🏴","Egypt":"🇪🇬","Ghana":"🇬🇭",
 "Algeria":"🇩🇿","Bosnia and Herzegovina":"🇧🇦","South Korea":"🇰🇷","Australia":"🇦🇺","Tunisia":"🇹🇳",
 "Iran":"🇮🇷","Congo DR":"🇨🇩","Panama":"🇵🇦","South Africa":"🇿🇦","Saudi Arabia":"🇸🇦",
 "New Zealand":"🇳🇿","Iraq":"🇮🇶","Qatar":"🇶🇦","Uzbekistan":"🇺🇿","Cape Verde":"🇨🇻","Haiti":"🇭🇹",
 "Jordan":"🇯🇴","Curacao":"🇨🇼",
}

def load_overrides():
    """Merge live results from data/results.json over the hardcoded seed.
    results.json (written by scripts/update_results.py) wins when present."""
    results = dict(KNOWN_RESULTS)
    p = os.path.join(DATA, "results.json")
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            for k, v in (d.get("results") or {}).items():
                results[int(k)] = tuple(v)
            print(f"  merged {len(d.get('results') or {})} live results from results.json"
                  + (f" (updated {d.get('updated')})" if d.get('updated') else ""))
        except Exception as e:
            print("  ! results.json unreadable, using seed:", e)
    return results

def build_matches(results):
    matches = []
    for (num,grp,md,date,venue,home,away) in GROUP_SCHEDULE:
        m = {"id":f"m{num}","num":num,"grp":grp,"md":md,"date":date,"venue":venue,
             "home":home,"away":away,"status":"scheduled","hs":None,"as":None}
        if num in results:
            m["hs"],m["as"] = results[num]; m["status"]="final"
        matches.append(m)
    return matches

def read_entrants():
    rows = []
    with open(os.path.join(DATA,"standings.csv"),newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            picks = [r[f"Group {g}"].strip() for g in range(1,13)]
            if len([p for p in picks if p]) < 12: continue
            rows.append({"name":r["Last Name"].strip(),"picks":picks,
                         "goalsPred":int(r.get("Total Goals") or 0),
                         "sheetScore":int(r.get("Score") or 0)})
    return rows

def main():
    results = load_overrides()
    matches = build_matches(results)
    entrants = read_entrants()
    payload = {
        "sheet": SHEET, "me": ME,
        "contestGroups": {str(k):v for k,v in CONTEST_GROUPS.items()},
        "realGroups": REAL_GROUPS,
        "matches": matches,
        "koSchedule": [{"round":r,"dates":d} for (r,d) in KO_SCHEDULE],
        "entrants": entrants,
        "flags": FLAGS,
        "knockout": {},          # team -> furthest round key (R16/QF/SF/F/W) once knockouts begin
        "thirdsAdvanced": [],    # 3rd-place teams that qualify (set after group stage)
        "eliminated": [],        # teams knocked out (optional, for "alive" count)
        "builtAt": datetime.date.today().isoformat(),
    }
    # write readable data files (for the git pipeline / inspection)
    with open(os.path.join(DATA,"worldcup.json"),"w") as f:
        json.dump({"realGroups":REAL_GROUPS,"contestGroups":payload["contestGroups"],
                   "matches":matches,"flags":FLAGS},f,indent=2,ensure_ascii=False)
    with open(os.path.join(DATA,"portfolio.json"),"w") as f:
        me = next(e for e in entrants if e["name"]==ME)
        json.dump({"me":ME,"picks":me["picks"],
                   "doubleGroups":[9,10,11,12]},f,indent=2,ensure_ascii=False)
    # inject into template
    with open(os.path.join(HERE,"template.html"),encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("__DATA__", json.dumps(payload,ensure_ascii=False))
    out = os.path.join(ROOT,"index.html")
    with open(out,"w",encoding="utf-8") as f:
        f.write(html)
    print(f"Built {out}")
    print(f"  entrants: {len(entrants)}  matches: {len(matches)}  "
          f"finals: {sum(1 for m in matches if m['status']=='final')}")

if __name__ == "__main__":
    main()
