# ⚽ World Cup Pick'em — Portfolio Tracker

A self-contained dashboard for tracking your entry in the **2026 World Cup Challenge**
(Tom Boorstein's pick-a-team-from-each-of-12-ability-groups pool). Built for entry **Debiche**.

## What it shows

- **Overview** — live rank, score, goals, and a breakdown of where your points come from (double-points picks highlighted).
- **My 12 Teams** — each pick with its ability group, real World Cup group, live mini-table, points breakdown, and next match.
- **Bracket & Paths** — the real groups your teams sit in, who's advancing, and what each knockout round is worth (doubled for groups 9–12).
- **Leaderboard** — the full field, pulled **live** from the organizer's Google Sheet, with your twins highlighted.
- **Field Analysis** — how unique your portfolio is, how many entrants share your picks, and which of your picks are contrarian vs. with-the-crowd.
- **Enter Results** — match-by-match score entry (saved in your browser) that keeps the bracket and per-team math exact.

## Two ways to run it

### 1. Just open it (simplest)
Double-click **`index.html`**. It works immediately and pulls the live leaderboard
from the organizer's sheet every time you open it or hit **↻ Refresh**.
*(If your browser blocks the live fetch when opening a local file, it falls back to the
saved snapshot — everything still works, just not real-time. Hosting it, below, fixes that.)*

### 2. Host it for true auto-updates (GitHub Pages)
This gives you a shareable URL that refreshes itself on a schedule.

1. Create a new GitHub repo and upload this whole `worldcup-tracker/` folder.
2. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. The included workflow (`.github/workflows/update.yml`) then runs every 2 hours:
   it re-pulls the sheet, rebuilds `index.html`, commits, and redeploys Pages.
4. Your tracker lives at `https://<your-username>.github.io/<repo>/`.

## Updating data by hand

```bash
python3 scripts/update.py   # re-pull the sheet + rebuild index.html
python3 scripts/build.py     # rebuild only (after editing match results below)
```

## Folder layout

```
worldcup-tracker/
├── index.html              ← the dashboard (open this)
├── data/
│   ├── standings.csv        ← pool snapshot (offline fallback; refreshed by update.py)
│   ├── worldcup.json        ← real groups A–L, fixtures, flags
│   └── portfolio.json       ← your 12 picks
├── scripts/
│   ├── template.html        ← dashboard source (HTML/CSS/JS)
│   ├── build.py             ← assembles index.html from template + data
│   └── update.py            ← refreshes standings from the sheet, then builds
├── .github/workflows/update.yml  ← optional auto-refresh + Pages deploy
└── README.md
```

## Scoring (encoded in the engine)

Per team: **1**/goal · **1**/group-stage point (3 win / 1 draw) ·
**+8** win group / **+4** 2nd / **+2** advance as a 3rd-place team ·
knockout milestones **+16** R16 · **+24** QF · **+32** SF · **+48** final · **+64** champion.
**Teams in ability-groups 9–12 score double.**

> Verified: the engine reproduces the organizer's official `Score` column for **all 231 entrants** exactly.

### Updating match results / knockouts
- Quick edits: use the **Enter Results** tab in the dashboard (saved in your browser).
- To bake results into the shared/hosted copy, edit `KNOWN_RESULTS` in `scripts/build.py`.
- Once the group stage ends, set `thirdsAdvanced` (the 8 qualifying 3rd-place teams) and,
  as the knockouts progress, the `knockout` map (`team → R16/QF/SF/F/W`) in `build.py`.

### One scoring assumption
The knockout bonuses (16/24/32/48/64) are treated as **"furthest round reached"** (a team that
reaches the final gets 48, not 16+24+32+48). If the organizer scores them cumulatively instead,
change `ADV` handling in `scripts/template.html`. This can't be confirmed until the knockouts begin.
