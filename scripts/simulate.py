#!/usr/bin/env python3
"""
DATA ENGINE — Boorstein "Title Race".  Runs on the LIVE data (data/results.json).

Enumerates EVERY remaining knockout-bracket completion exactly (2^undecided), scores all
entrants in each, and returns: exact scenario-share + Elo-weighted win odds, top-2 odds,
ceiling/floor, most-decisive games, rooting guide, necessary conditions, clinch/elimination
watch, and per-entrant path-to-1st trees.

`compute(matches, entrants)` returns a JSON payload the site build embeds.  Run this file
directly (`python3 scripts/simulate.py`) for a text preview off the live results.json.
"""
import os, sys, json, time
from collections import defaultdict
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build
DATA = os.path.join(os.path.dirname(HERE), "data")

# ---------- scoring model (mirrors the site engine) ----------
DBL = {9,10,11,12}
ADV = {"R16":16,"QF":24,"SF":32,"F":48,"W":64}
FINISH = {1:8,2:4,3:2}
KO_RANK = {"R32":0,"R16":1,"QF":2,"SF":3,"FINAL":4}
team_group = {t:g for g,ts in build.CONTEST_GROUPS.items() for t in ts}
team_real  = {t:L for L,ts in build.REAL_GROUPS.items() for t in ts}

# ---------- (a) strength model: world-football Elo (Athletic-style rating) ----------
# Base ratings anchored to eloratings.net, ~4 Jul 2026 (top 6 exact from the live table;
# remaining alive teams set from their standing on that table). Easily editable.
ELO = {
 "Spain":2159,"Argentina":2151,"France":2134,"England":2046,"Brazil":2031,"Portugal":2013,
 "Colombia":1969,"Belgium":1944,"Morocco":1901,"Switzerland":1868,"Norway":1861,
 "Mexico":1817,"United States":1801,"Egypt":1662,
}
# 2026 is co-hosted by USA/Mexico/Canada — small home edge for the alive hosts (matches are on US soil).
HOST = {"United States":50,"Mexico":40}
def elo(t): return ELO.get(t, 1750) + HOST.get(t, 0)
def pwin(a, b):
    """P(a advances past b) via the logistic Elo formula (KO games decided, no draws)."""
    return 1.0/(1.0 + 10**(-(elo(a)-elo(b))/400.0))

def group_table(letter, matches):
    teams=build.REAL_GROUPS[letter]; row={t:{"pld":0,"gf":0,"ga":0,"pts":0} for t in teams}
    for m in matches:
        if m["grp"]!=letter or m["status"]!="final": continue
        h,a=row[m["home"]],row[m["away"]]; h["pld"]+=1;a["pld"]+=1
        h["gf"]+=m["hs"];h["ga"]+=m["as"];a["gf"]+=m["as"];a["ga"]+=m["hs"]
        if m["hs"]>m["as"]: h["pts"]+=3
        elif m["hs"]<m["as"]: a["pts"]+=3
        else: h["pts"]+=1;a["pts"]+=1
    order=sorted(teams,key=lambda t:(-row[t]["pts"],-(row[t]["gf"]-row[t]["ga"]),-row[t]["gf"],t))
    return {t:{"pos":i+1,"pld":row[t]["pld"]} for i,t in enumerate(order)}

def winner_of(m):
    if not m or m["status"]!="final": return None
    if m["pk"]: return m["pkWinner"]
    return m["home"] if m["hs"]>m["as"] else (m["away"] if m["as"]>m["hs"] else None)

def resolve_bracket(matches):
    W={};R={}
    for L in build.REAL_GROUPS:
        t=group_table(L,matches); order=sorted(t,key=lambda x:t[x]["pos"]); W[L]=order[0]; R[L]=order[1]
    koR=defaultdict(list)
    for m in matches:
        if m["round"]: koR[m["round"]].append(m)
    def findKO(rnd,a,b):
        for m in koR[rnd]:
            if {m["home"],m["away"]}=={a,b}: return m
        return None
    B={n:{"num":n,"round":r,"a":a,"b":b,"t1":None,"t2":None,"winner":None,"loser":None} for (n,r,a,b) in build.KO_BRACKET}
    wr=lambda c: W.get(c[2]) if c[0]=="W" else (R.get(c[2]) if c[0]=="R" else None)
    for (n,r,a,b) in build.KO_BRACKET:
        if r!="R32": continue
        nd=B[n]; t1=wr(a); t2=wr(b); known=[x for x in (t1,t2) if x]; m=None
        if len(known)==2: m=findKO("R32",known[0],known[1])
        elif len(known)==1:
            for x in koR["R32"]:
                if known[0] in (x["home"],x["away"]): m=x; break
        if m: nd["t1"],nd["t2"]=m["home"],m["away"]; nd["winner"]=winner_of(m)
    for rnd in ("R16","QF","SF","FINAL"):
        for (n,r,a,b) in build.KO_BRACKET:
            if r!=rnd: continue
            nd=B[n]
            nd["t1"]=B[int(a[1:])]["winner"] if a[0]=="w" else None
            nd["t2"]=B[int(b[1:])]["winner"] if b[0]=="w" else None
            if nd["t1"] and nd["t2"]:
                m=findKO(rnd,nd["t1"],nd["t2"])
                if m: nd["winner"]=winner_of(m)
    for n,nd in B.items():
        if nd["winner"] and nd["t1"] and nd["t2"]:
            nd["loser"]=nd["t2"] if nd["winner"]==nd["t1"] else nd["t1"]
    return B,W,R

# ---------- team scoring parts ----------
def ko_reach(team, matches):
    best=-1; inR32=False; wonF=False
    for m in matches:
        if not m["round"] or m["round"]=="BRONZE": continue
        if team not in (m["home"],m["away"]): continue
        if m["round"]=="R32": inR32=True
        rk=KO_RANK.get(m["round"]);
        if rk is None: continue
        if rk>best: best=rk
        if m["status"]=="final" and winner_of(m)==team:
            if m["round"]=="FINAL": wonF=True
            elif rk+1>best: best=rk+1
    return best,inR32,wonF

def adv_for(best,wonF):
    if wonF: return ADV["W"]
    if best>=KO_RANK["FINAL"]: return ADV["F"]
    if best>=KO_RANK["SF"]: return ADV["SF"]
    if best>=KO_RANK["QF"]: return ADV["QF"]
    if best>=KO_RANK["R16"]: return ADV["R16"]
    return 0

def team_fixed_adv(team, matches):
    g=team_group[team]; mult=2 if g in DBL else 1; goals=gpts=finish=0
    for m in matches:
        if m["status"]!="final" or m["round"]=="BRONZE": continue
        if team not in (m["home"],m["away"]): continue
        mine=m["hs"] if m["home"]==team else m["as"]; opp=m["as"] if m["home"]==team else m["hs"]
        goals+=mine
        if m["grp"]:
            if mine>opp: gpts+=3
            elif mine==opp: gpts+=1
    tbl=group_table(team_real[team],matches); pos=tbl[team]["pos"]; done=all(tbl[t]["pld"]==3 for t in tbl)
    best,inR32,wonF=ko_reach(team,matches)
    if done:
        if pos==1: finish=FINISH[1]
        elif pos==2: finish=FINISH[2]
        elif pos==3: finish=FINISH[3] if inR32 else 0
    return goals+gpts+finish, adv_for(best,wonF), mult

ROUND_NAME={"R16":"Round of 16","QF":"Quarter-finals","SF":"Semi-finals","FINAL":"Final"}

def compute(matches, entrants, my_entry="Debiche", eg_goals=1.3, board_n=18, detail_extra=4):
    """Run the full title-race engine on a live `matches` list. Returns a JSON-serializable dict."""
    B,W,R=resolve_bracket(matches)
    tinfo={t:team_fixed_adv(t,matches) for t in team_group}
    entrants=[dict(e) for e in entrants]
    for e in entrants: e["cur"]=sum((tinfo[t][0]+tinfo[t][1])*tinfo[t][2] for t in e["picks"])
    entrants.sort(key=lambda e:(-e["cur"],-e.get("goalsPred",0)))
    for i,e in enumerate(entrants): e["rank"]=i+1
    ename={e["name"]:e for e in entrants}

    ORDER=[n for r in ("R16","QF","SF","FINAL") for n in build.KO_ORDER[r]]
    known_winner={n:B[n]["winner"] for n in ORDER}
    feA={n:B[n]["a"] for n in ORDER}; feB={n:B[n]["b"] for n in ORDER}
    r32w={B[n]["winner"] for (n,r,a,b) in build.KO_BRACKET if r=="R32" and B[n]["winner"]}
    lost=set()
    for n in ORDER:
        nd=B[n]
        if nd["winner"] and nd["t1"] and nd["t2"]:
            lost.add(nd["t2"] if nd["winner"]==nd["t1"] else nd["t1"])
    alive=r32w-lost
    for e in entrants: e["ap"]=[(t,tinfo[t][2],tinfo[t][1]) for t in e["picks"] if t in alive]

    def propagate(assign):
        nodes={}
        for n in ORDER:
            nd=B[n]; r=nd["round"]
            if r=="R16": t1,t2=nd["t1"],nd["t2"]
            else:
                t1=nodes[int(feA[n][1:])]["winner"]; t2=nodes[int(feB[n][1:])]["winner"]
            nodes[n]={"t1":t1,"t2":t2,"round":r,"winner":known_winner[n] or assign.get(n)}
        return nodes

    undecided=[n for n in ORDER if not known_winner[n]]
    idx={n:i for i,n in enumerate(undecided)}
    leader_name=entrants[0]["name"] if entrants else None
    # "next up" = ready undecided games at the shallowest remaining round
    ready=[n for n in undecided if B[n]["t1"] and B[n]["t2"]]
    nextg=[]
    if ready:
        mr=min(KO_RANK[B[n]["round"]] for n in ready)
        nextg=[n for n in ready if KO_RANK[B[n]["round"]]==mr]
    cur_round=B[nextg[0]]["round"] if nextg else (B[undecided[0]]["round"] if undecided else "FINAL")

    def run(eg):
        s_first=defaultdict(int); w_first=defaultdict(float); s_top2=defaultdict(int)
        w_top2=defaultdict(float); beat=defaultdict(float); ceiling={}; floor={}; leaves=[]
        def score_leaf(nodes,weight,assign):
            adv={}; fut={}
            for t in alive:
                best=-1; wonF=False; games=0
                for n in ORDER:
                    nd=nodes[n]
                    if t in (nd["t1"],nd["t2"]):
                        rk=KO_RANK[nd["round"]]
                        if n in idx: games+=1
                        if rk>best: best=rk
                        if nd["winner"]==t:
                            if nd["round"]=="FINAL": wonF=True
                            elif rk+1>best: best=rk+1
                adv[t]=adv_for(best,wonF); fut[t]=games
            b1=(-1,None);b2=(-1,None); vals={}
            for e in entrants:
                val=e["cur"]+sum((adv[t]-ca+eg*fut[t])*mu for (t,mu,ca) in e["ap"]); vals[e["name"]]=val
                if val>ceiling.get(e["name"],-1): ceiling[e["name"]]=val
                if val<floor.get(e["name"],10**9): floor[e["name"]]=val
                if val>b1[0]: b2=b1;b1=(val,e["name"])
                elif val>b2[0]: b2=(val,e["name"])
            s_first[b1[1]]+=1; w_first[b1[1]]+=weight
            for nm in (b1[1],b2[1]): s_top2[nm]+=1; w_top2[nm]+=weight
            if leader_name is not None:
                lv=vals[leader_name]
                for nm,v in vals.items():
                    if v>lv: beat[nm]+=weight
            leaves.append((weight,b1[1],tuple(assign[n] for n in undecided)))
        def recurse(assign,weight):
            nodes=propagate(assign); nxt=None
            for n in ORDER:
                nd=nodes[n]
                if nd["t1"] and nd["t2"] and nd["winner"] is None: nxt=n; break
            if nxt is None: score_leaf(nodes,weight,assign); return
            a,b=nodes[nxt]["t1"],nodes[nxt]["t2"]; p=pwin(a,b)
            r=dict(assign); r[nxt]=a; recurse(r,weight*p)
            r=dict(assign); r[nxt]=b; recurse(r,weight*(1-p))
        t0=time.time(); recurse({},1.0); dt=time.time()-t0
        return dict(s_first=s_first,w_first=w_first,s_top2=s_top2,beat=beat,
                    ceiling=ceiling,floor=floor,leaves=leaves,N=len(leaves),dt=dt)

    r0=run(0.0); rG=run(eg_goals); N=max(r0["N"],1)
    leaves=r0["leaves"]
    fav=max(r0["w_first"],key=r0["w_first"].get) if r0["w_first"] else leader_name
    gmatch={r:(B[r]["t1"],B[r]["t2"]) for r in nextg}

    def cond(C, constraints):
        num=den=0.0
        for w,c,adv in leaves:
            if all(adv[idx[n]]==tm for n,tm in constraints.items()):
                den+=w
                if c==C: num+=w
        return (num/den if den else 0.0)

    aliveC=[e["name"] for e in entrants if r0["s_first"].get(e["name"],0)>0]
    aliveset=set(aliveC)
    order=sorted(entrants,key=lambda e:(-r0["s_first"].get(e['name'],0),-r0["w_first"].get(e['name'],0)))

    def rooting(C):
        out=[]; picks=set(ename[C]["picks"])
        for r in nextg:
            A,Bt=gmatch[r]; pa=cond(C,{r:A}); pb=cond(C,{r:Bt})
            want=A if pa>=pb else Bt; d=abs(pa-pb)
            out.append({"team":want,"own":want in picks,"delta":round(d,4),
                        "vs":(Bt if want==A else A)})
        out.sort(key=lambda x:-x["delta"]); return out

    def necessary(C):
        wins=[adv for w,c,adv in leaves if c==C]
        if not wins: return []
        conds=[]
        for r in nextg:
            i=idx[r]; s={adv[i] for adv in wins}
            if len(s)==1:
                tm=next(iter(s)); other=B[r]["t2"] if tm==B[r]["t1"] else B[r]["t1"]
                conds.append({"team":tm,"vs":other})
        return conds

    def build_tree(C, depth=3):
        if r0["s_first"].get(C,0)==0: return None
        picks=set(ename[C]["picks"])
        def rec(constraints, remaining, d):
            best=None
            for r in remaining:
                A,Bt=gmatch[r]; pa=cond(C,{**constraints,r:A}); pb=cond(C,{**constraints,r:Bt})
                lev=abs(pa-pb)
                if best is None or lev>best[0]: best=(lev,r,A,Bt,pa,pb)
            if best is None: return None
            lev,r,A,Bt,pa,pb=best
            if lev<1e-9: return None
            rem2=[x for x in remaining if x!=r]; br=[]
            for tm,p in sorted(((A,pa),(Bt,pb)),key=lambda x:-x[1]):
                dead=p<=1e-9; clinch=abs(p-1)<1e-9; child=None
                if not dead and not clinch and d>1 and rem2:
                    child=rec({**constraints,r:tm}, rem2, d-1)
                br.append({"team":tm,"own":tm in picks,"pct":round(p,4),
                           "dead":dead,"clinch":clinch,"child":child})
            return {"a":A,"b":Bt,"branches":br}
        return rec({}, list(nextg), depth)

    # decisive games (swing = total-variation change in champion distribution)
    games=[]
    for r in nextg:
        A,Bt=gmatch[r]; i=idx[r]
        wA=defaultdict(float);wB=defaultdict(float);tA=tB=0.0
        for w,c,adv in leaves:
            if adv[i]==A: wA[c]+=w;tA+=w
            else: wB[c]+=w;tB+=w
        tv=0.5*sum(abs((wA[c]/tA if tA else 0)-(wB[c]/tB if tB else 0)) for c in set(wA)|set(wB))
        games.append({"a":A,"b":Bt,"swing":round(tv,4),
                      "fav":fav,"favIfA":round(wA[fav]/tA if tA else 0,4),
                      "favIfB":round(wB[fav]/tB if tB else 0,4)})
    games.sort(key=lambda g:-g["swing"])

    # clinch / elimination watch
    watch=[]
    for r in sorted(nextg,key=lambda r:-games_swing(games,gmatch[r])):
        A,Bt=gmatch[r]; outs=[]
        for X,Y in ((A,Bt),(Bt,A)):
            elim=[C for C in aliveC if cond(C,{r:X})==0]
            clinch=[C for C in aliveC if abs(cond(C,{r:X})-1.0)<1e-9]
            outs.append({"winner":X,"loser":Y,"eliminated":elim,"clinch":clinch})
        watch.append({"a":A,"b":Bt,"outcomes":outs})

    # detail set: alive-for-1st + my_entry + a few top even%
    detail=set(aliveC) | ({my_entry} if my_entry in ename else set())
    for e in order[:detail_extra]: detail.add(e["name"])

    board=[]
    picked=[e["name"] for e in order[:board_n]]
    for nm in (picked + [my_entry] if (my_entry in ename and my_entry not in picked) else picked):
        e=ename[nm]; row={
            "name":nm,"rank":e["rank"],"cur":e["cur"],
            "even":round(r0["s_first"].get(nm,0)/N,4),
            "eg":round(rG["s_first"].get(nm,0)/max(rG["N"],1),4),
            "model":round(r0["w_first"].get(nm,0),4),
            "top2":round(r0["s_top2"].get(nm,0)/N,4),
            "beat":round(r0["beat"].get(nm,0),4),
            "floor":int(r0["floor"].get(nm,e["cur"])),"ceil":int(r0["ceiling"].get(nm,e["cur"])),
            "alive":nm in aliveset,
        }
        if nm in detail:
            row["rooting"]=rooting(nm); row["necessary"]=necessary(nm); row["tree"]=build_tree(nm)
        board.append(row)

    return {
        "updated":_now_iso(matches),
        "stage":ROUND_NAME.get(cur_round,cur_round),
        "undecided":len(undecided),"completions":2**len(undecided),
        "aliveCount":len(alive),"aliveTeams":sorted(alive),
        "aliveForFirst":len(aliveC),"entrantsTotal":len(entrants),
        "leader":leader_name,"fav":fav,"myEntry":my_entry if my_entry in ename else None,
        "games":games,"watch":watch,"board":board,
        "elo":{t:elo(t) for t in sorted(alive)},
    }

def games_swing(games, ab):
    for g in games:
        if {g["a"],g["b"]}=={ab[0],ab[1]}: return g["swing"]
    return 0.0

def _now_iso(matches):
    p=os.path.join(DATA,"results.json")
    if os.path.exists(p):
        try: return json.load(open(p,encoding="utf-8")).get("updated")
        except Exception: pass
    return None

# ---------- CLI text preview ----------
def print_preview(P):
    print(f"Live state: {P['stage']} · undecided {P['undecided']} -> {P['completions']:,} completions")
    print(f"Alive teams ({P['aliveCount']}): "+", ".join(P['aliveTeams']))
    print(f"Alive for 1st: {P['aliveForFirst']} of {P['entrantsTotal']}   leader {P['leader']} · model fav {P['fav']}\n")
    print(f"{'Entrant':14}{'#':>3}{'Now':>5} | {'even':>6}{'model':>7}{'top2':>6} | {'floor':>6}{'ceil':>6}  alive")
    for r in P["board"][:14]:
        print(f"{r['name']:14}{r['rank']:>3}{r['cur']:>5} | {r['even']*100:>5.1f}%{r['model']*100:>6.0f}%"
              f"{r['top2']*100:>5.0f}% | {r['floor']:>6}{r['ceil']:>6}  {'Y' if r['alive'] else '-'}")
    print("\nMOST DECISIVE next games:")
    for g in P["games"]:
        print(f"   {g['a']} vs {g['b']}: swing {g['swing']*100:4.0f}%  "
              f"({g['fav']} {g['favIfA']*100:.0f}% / {g['favIfB']*100:.0f}%)")
    print("\nCLINCH / ELIMINATION WATCH:")
    for w in P["watch"]:
        for o in w["outcomes"]:
            tag=[]
            if o["clinch"]: tag.append("CLINCHES: "+", ".join(o["clinch"]))
            if o["eliminated"]: tag.append("out of 1st: "+", ".join(o["eliminated"]))
            print(f"   {o['winner']} beats {o['loser']:14} -> "+(" | ".join(tag) if tag else "no eliminations"))
    def show_tree(nd, ind="      "):
        if not nd: print(ind+"(no single decisive game left)"); return
        for br in nd["branches"]:
            star="*" if br["own"] else ""
            if br["dead"]: print(f"{ind}{br['team']}{star} adv: 0% (dead)")
            elif br["clinch"]: print(f"{ind}{br['team']}{star} adv: 100% (clinch)")
            elif br["child"]: print(f"{ind}{br['team']}{star} adv:"); show_tree(br["child"], ind+"   ")
            else: print(f"{ind}{br['team']}{star} adv: {br['pct']*100:.0f}%")
    print("\nPATH-TO-1st TREES:")
    names=[r["name"] for r in P["board"][:5]]
    if P["myEntry"] and P["myEntry"] not in names: names.append(P["myEntry"])
    byname={r["name"]:r for r in P["board"]}
    for nm in names:
        r=byname.get(nm);
        if not r: continue
        print(f"\n   {nm} (even {r['even']*100:.1f}% / model {r['model']*100:.1f}% · rank {r['rank']}, {r['cur']} pts):")
        if not r.get("alive"): print("      eliminated from 1st."); continue
        show_tree(r.get("tree"))

def main():
    results, knockout = build.load_overrides()
    matches = build.build_matches(results, knockout)
    entrants = build.read_entrants()
    P = compute(matches, entrants)
    print_preview(P)

if __name__=="__main__":
    main()
