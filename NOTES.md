# Notes / TODO

## Deferred: per-game points allocation (audit view)
DC-microsite has a per-game points breakdown (each match row shows each team's
points + reason: `+3 W`, `+1 D`, `+0 L`, `+3 PK W`, `+1 PK L`) in Enter Results,
plus a "sum of games = total" checkline on each My Team card — a transparency /
audit mechanism.

**For Boorstein:** hold off adding it as-is. Boorstein scoring is richer per game
(goals + group points + finish bonus + advancement bonus, ×2 for groups 9–12),
so a single per-row chip would be crowded. When revisited, show the *components*
(e.g. `2g +3grp` in the group stage, `+16 R16` in knockouts) rather than one number,
likely as an expandable breakdown on the My Teams cards rather than in Enter Results.

## DONE: "Title Race" tab (🏆)
Built. `scripts/simulate.py` `compute(matches, entrants)` runs at build time
(off the live data/results.json) and embeds `payload.titleRace`; the template's
`renderTitleRace()` renders it. Auto-updates hourly with the pipeline.
Shows: who-can-win board (even-odds / Elo-model toggle), most-decisive games,
contender explorer (rooting guide + necessary conditions + path-to-1st tree, defaults
to Debiche), and a clinch/elimination watch. Engine = exact enumeration of all
2^undecided bracket completions; Elo ratings live in simulate.ELO (edit to retune).
Tab auto-hides before knockouts (titleRace is null).

Possible v2: port enumeration to JS for a live "what-if" simulator (click winners,
watch odds update) instead of the build-time snapshot.
