# Title Race Tab — Handoff

The **🏆 Title Race** tab answers one question: *given where the tournament is right now, who can still win the Boorstein pick'em pool, and what has to happen for each of them?* It does this by simulating **every possible way the remaining knockout bracket can finish** and scoring all 231 entries in each one.

This document explains what the tab shows, how the engine works, how it stays current, and how to maintain or extend it.

---

## 1. Where it lives / how the pieces fit

```
data/results.json  ──►  scripts/simulate.py  ──►  payload.titleRace  ──►  index.html
 (live scores)          compute(matches,        (embedded JSON)          renderTitleRace()
                        entrants)                                        draws the tab
```

| File | Role in the Title Race |
|------|------------------------|
| `data/results.json` | Live group + knockout results, refreshed hourly by the GitHub Action (`scripts/update_results.py` pulls football-data.org). This is the single source of truth. |
| `scripts/simulate.py` | The engine. `compute(matches, entrants)` runs the full simulation and returns a JSON-serializable dict. Also runnable standalone (`python3 scripts/simulate.py`) for a text preview. |
| `scripts/build.py` | Calls `simulate.compute(...)` during the build and drops the result into `payload["titleRace"]`, which gets injected into the page. |
| `scripts/template.html` | Contains the tab markup, CSS, and `renderTitleRace()` (plus helpers) that turn the payload into the visual tab. |
| `index.html` | The built, self-contained page with the payload baked in. |

**Key idea:** the simulation runs at *build time* in Python, not in the browser. The result is a small precomputed payload. Because the site rebuilds hourly, the tab refreshes automatically as games finish — there is no separate step to run.

---

## 2. What the tab shows

### Header + mode toggle
A one-line summary (how many matches remain, how many possible bracket completions, how many entrants are still alive for 1st, who leads, who the model favours) and a toggle:

- **Even odds** — every remaining match is treated as a coin flip. Every bracket completion is equally likely. This is the honest, assumption-free headline number.
- **Elo model** — each completion is weighted by world-football Elo ratings, so stronger teams are more likely to advance. This is the "realistic" lens.

The toggle re-renders the leaderboard bars and percentages. The two numbers can differ a lot, and that difference is itself informative (a contender who is high on even-odds but low on the model is riding on upsets).

### Who can still win
The contenders ranked by win probability, with a bar, current points, win %, and a top-2 tag. Entrants who are mathematically **out of first** are shown greyed with an "out of 1st" tag. Your entry (**Debiche**) is starred and colour-highlighted.

### Most decisive games left
Each unplayed game in the next round, ranked by **swing** — how much the eventual champion distribution changes depending on who wins. The bar and sub-line show how the current favourite's odds move under each result. (Right now USA vs Belgium is the single most decisive game.)

### Contender explorer
A dropdown (defaults to your team) that, for the selected entrant, shows:
- **Root for** — which advancing team helps them most, and by how many win-odds points (★ marks their own picks).
- **Must happen** — any single result that is *required* for them to finish 1st ("Spain must beat Portugal").
- **Path to 1st** — a branching if/then tree. Each level is the most decisive remaining game for that entrant; branches show the resulting win odds, dead ends are marked "out of 1st", and clinches are marked 🏆.

### Clinch / elimination watch
For each upcoming game, both outcomes, and who each result eliminates from (or, later in the tournament, clinches) first place. No one can clinch this early — the interesting story is who gets knocked out of contention.

---

## 3. How the engine works (`simulate.py`)

### Exact enumeration, not Monte Carlo
When the tournament reaches the knockout stage, the number of *undecided* bracket games is small enough to enumerate **every** completion exactly:

- Round of 16 with a couple games played → ~2,048–8,192 completions
- Each is scored in well under a second total

So instead of sampling (like most public simulators, including The Athletic's), we compute the **true** probability of every outcome. "Win %" is the exact share of completions in which that entrant finishes 1st.

### The steps
1. **Resolve the live bracket** (`resolve_bracket`) — read the real group tables and knockout results from `matches`, place teams into the official bracket skeleton, and mark which games are decided.
2. **Fix each team's locked-in score** (`team_fixed_adv`) — goals, group points, finish bonus, and the advancement bonus already earned, using the pool's exact scoring rules (including the ×2 multiplier for ability groups 9–12).
3. **Enumerate** (`recurse`) — branch every undecided game two ways, propagating winners up the bracket. Each leaf is one complete tournament.
4. **Score every entrant in every leaf** and record: who finishes 1st, who's top-2, each entrant's ceiling/floor, and probability weights.
5. **Derive the analyses** — decisive games, rooting guides, necessary conditions, clinch/elimination watch, and per-entrant path trees — then package it all into the payload.

### The two probability models
- **Even odds:** each leaf counts equally (weight = 1).
- **Elo model:** each leaf's weight is the product of its game probabilities, where each game's probability comes from the logistic Elo formula. Ratings live in the `ELO` dict in `simulate.py` (anchored to eloratings.net, July 2026), plus a small home-field bump for the USA/Mexico co-hosts in `HOST`.

Both are always computed; the toggle just picks which to display.

### Expected goals (minor knob)
The engine also computes a variant that credits ~1.3 expected goals per future knockout game a team survives into (`eg_goals`). In testing this moved win odds by well under a percentage point, so it is not surfaced in the UI — the advancement bonuses dominate. It's there if you ever want it.

---

## 4. Keeping it current

Nothing to do — the hourly GitHub Action pulls fresh results, and the build re-runs the engine. As each knockout game finishes:
- that game drops out of the "undecided" set (fewer completions),
- eliminated teams and entrants fall away,
- the board, decisive games, trees, and watch all update.

The tab **auto-hides before the knockouts start** (`payload.titleRace` is `null` during the group stage) and reappears once there's a bracket to simulate.

To preview locally without the site:
```bash
python3 scripts/simulate.py      # text preview off the live data/results.json
python3 scripts/build.py         # rebuild index.html with the tab
```

---

## 5. Maintenance notes / gotchas

- **Retuning strength:** edit the `ELO` dict (and `HOST`) in `simulate.py`. Nothing else needs to change. If you'd rather trust pure chance, users can just leave the toggle on "Even odds."
- **Your entry:** the contender explorer and the always-included path tree default to `Debiche`, set via `my_entry` (passed from `ME` in `build.py`). Change `ME` to point elsewhere.
- **Scoring must stay in sync:** the engine mirrors the pool's scoring rules (goals + group points + finish bonus + advancement bonus, ×2 for groups 9–12, bronze game excluded). If the site's scoring engine changes, update `simulate.py` to match.
- **Build-time vs. local edits:** the tab reflects the last *server* build, not manual "Enter Results" edits in the browser. That's intentional — it mirrors production. (See v2 below.)
- **Name matching:** entrants are keyed by the "Last Name" column in `standings.csv`. There is no entry literally named "Alon"; Debiche is the owner's team.

---

## 6. Possible v2

Port the enumeration to JavaScript so the tab becomes a live **what-if simulator**: click winners for the upcoming games and watch every contender's odds update instantly in the browser, including reaction to manual result edits. The enumeration is small enough (a few thousand completions) to run client-side. This is the natural next step if more interactivity is wanted; the current build-time approach was chosen first for robustness and exact parity with the Python engine.
