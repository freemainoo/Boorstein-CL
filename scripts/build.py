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

SHEET = {"id": "1CAtVLI4V07gAlfaTcKehua-6HmIg-hDCHNUnXWhh5d4", "gid": "1567462692"}  # live picks+Score tab (1365959132 froze in the group stage)
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

# ---- Knockout bracket skeleton (official 2026 feeder map). ----
# (match#, round, sideA, sideB). W:A win grp A · R:B runner-up B · T:CDEFH best 3rd among
# those groups · w74 winner of match 74 · l101 loser of match 101
KO_BRACKET = [
    (73,"R32","R:A","R:B"), (74,"R32","W:E","T:ABCDF"), (75,"R32","W:F","R:C"),
    (76,"R32","W:C","R:F"), (77,"R32","W:I","T:CDFGH"), (78,"R32","R:E","R:I"),
    (79,"R32","W:A","T:CEFHI"), (80,"R32","W:L","T:EHIJK"), (81,"R32","W:D","T:BEFIJ"),
    (82,"R32","W:G","T:AEHIJ"), (83,"R32","R:K","R:L"), (84,"R32","W:H","R:J"),
    (85,"R32","W:B","T:EFGIJ"), (86,"R32","W:J","R:H"), (87,"R32","W:K","T:DEIJL"),
    (88,"R32","R:D","R:G"),
    (89,"R16","w74","w77"), (90,"R16","w73","w75"), (91,"R16","w76","w78"), (92,"R16","w79","w80"),
    (93,"R16","w83","w84"), (94,"R16","w81","w82"), (95,"R16","w86","w88"), (96,"R16","w85","w87"),
    (97,"QF","w89","w90"), (98,"QF","w93","w94"), (99,"QF","w91","w92"), (100,"QF","w95","w96"),
    (101,"SF","w97","w98"), (102,"SF","w99","w100"),
    (103,"BRONZE","l101","l102"), (104,"FINAL","w101","w102"),
]
KO_ORDER = {"R32":[74,77,73,75,83,84,81,82,76,78,79,80,86,88,85,87],
            "R16":[89,90,93,94,91,92,95,96], "QF":[97,98,99,100],
            "SF":[101,102], "FINAL":[104], "BRONZE":[103]}
KO_ROUND_META = [("R32","Round of 32","Jun 28 – Jul 3"), ("R16","Round of 16","Jul 4 – 7"),
                 ("QF","Quarter-finals","Jul 9 – 11"), ("SF","Semi-finals","Jul 14 – 15"),
                 ("FINAL","Final","Jul 19"), ("BRONZE","Third place","Jul 18")]
ROUND_DATE = {m[0]: m[2] for m in KO_ROUND_META}

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
    results = dict(KNOWN_RESULTS); knockout = []
    p = os.path.join(DATA, "results.json")
    if os.path.exists(p):
        try:
            d = json.load(open(p, encoding="utf-8"))
            for k, v in (d.get("results") or {}).items():
                results[int(k)] = tuple(v)
            knockout = d.get("knockout") or []
            print(f"  merged {len(d.get('results') or {})} group + {len(knockout)} knockout results"
                  + (f" (updated {d.get('updated')})" if d.get('updated') else ""))
        except Exception as e:
            print("  ! results.json unreadable, using seed:", e)
    return results, knockout

# Penalty-shootout goal fix. The live feed records the SHOOTOUT tally as the match
# score (e.g. Germany "4-5" Paraguay), but for scoring only regulation goals count and a
# shootout is by definition a level draw. football-data's fullTime is unreliable for these,
# so we pin the regulation score here (verified exactly against the organizer's per-team
# Goals). Keyed by the two teams (order-independent); value = the level score each side had.
# ADD any new penalty-shootout game here as the knockouts progress.
PK_REGULATION = {
    frozenset({"Germany", "Paraguay"}):    1,   # 1-1, Paraguay on pens
    frozenset({"Netherlands", "Morocco"}): 1,   # 1-1, Morocco on pens
    frozenset({"Australia", "Egypt"}):     1,   # 1-1, Egypt on pens
    frozenset({"Switzerland", "Colombia"}):0,   # 0-0, Switzerland on pens
}

def build_matches(results, knockout):
    matches = []
    for (num,grp,md,date,venue,home,away) in GROUP_SCHEDULE:
        m = {"id":f"m{num}","num":num,"grp":grp,"md":md,"date":date,"venue":venue,
             "home":home,"away":away,"status":"scheduled","hs":None,"as":None,
             "pk":False,"pkWinner":None,"round":None}
        if num in results:
            m["hs"],m["as"] = results[num]; m["status"]="final"
        matches.append(m)
    for i, k in enumerate(knockout):
        rnd = k.get("round","R32")
        ha = "".join(c for c in "_".join(sorted([str(k.get("home")), str(k.get("away"))]))
                     if c.isalnum() or c=="_")
        hs, as_ = k.get("hs"), k.get("as")
        if k.get("pkWinner"):  # override feed's shootout tally with true regulation score
            lvl = PK_REGULATION.get(frozenset({k.get("home"), k.get("away")}))
            if lvl is not None: hs = as_ = lvl
        matches.append({
            "id": f"k_{rnd}_{ha}", "num": 900+i, "grp": None, "round": rnd, "md": None,
            "date": k.get("date") or ROUND_DATE.get(rnd,""), "venue": k.get("venue",""),
            "home": k.get("home"), "away": k.get("away"),
            "hs": hs, "as": as_,
            "status": k.get("status","scheduled"),
            "pk": bool(k.get("pkWinner")), "pkWinner": k.get("pkWinner"),
        })
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
    results, knockout = load_overrides()
    matches = build_matches(results, knockout)
    entrants = read_entrants()
    title_race = None
    try:
        import simulate
        title_race = simulate.compute(matches, entrants, my_entry=ME)
        tr = title_race
        print(f"  title race: {tr['stage']} · {tr['completions']:,} completions · "
              f"{tr['aliveForFirst']} alive for 1st · fav {tr['fav']}")
    except Exception as e:
        import traceback; traceback.print_exc()
        print("  ! title-race compute failed (tab will be hidden):", e)
    payload = {
        "sheet": SHEET, "me": ME,
        "contestGroups": {str(k):v for k,v in CONTEST_GROUPS.items()},
        "realGroups": REAL_GROUPS,
        "matches": matches,
        "koSchedule": [{"round":r,"dates":d} for (r,d) in KO_SCHEDULE],
        "koBracket": [{"num":n,"round":r,"a":a,"b":b} for (n,r,a,b) in KO_BRACKET],
        "koOrder": KO_ORDER,
        "koRounds": [{"key":k,"name":nm,"dates":d} for (k,nm,d) in KO_ROUND_META],
        "entrants": entrants,
        "flags": FLAGS,
        "knockout": {},          # team -> furthest round key (R16/QF/SF/F/W) once knockouts begin
        "thirdsAdvanced": [],    # 3rd-place teams that qualify (set after group stage)
        "eliminated": [],        # teams knocked out (optional, for "alive" count)
        "titleRace": title_race, # None until knockouts begin; drives the Title Race tab
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
