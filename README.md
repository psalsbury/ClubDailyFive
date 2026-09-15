# ClubDailyFive

Source for ClubDailyFive.com and its daily question-generation agent.

## Layout
- `site/` PHP site and static assets
- `agent/` question-bank builder, daily publisher and API-Football quota client
- `systemd/` nightly publication service and timer

## Question model
- Exactly 300 bank questions per active club.
- Each bank row records `use_count` and `last_used_date`.
- Daily round: four least-recently-used/randomised bank questions from distinct source facts plus one recent-match/current-season question.
- Final five are shuffled deterministically per club/date.
- Recent-match window: seven days.
- UK date boundary: Europe/London.

Secrets, live databases and environment files are intentionally excluded from source control.

## Monetary questions
All displayed monetary values must be pounds sterling (£), including options and explanations. The bank builder converts the dataset's rounded euro amounts using the historical EUR/GBP rate on the fact date (or preceding working day). These are labelled approximate sterling equivalents, not exact reported contract fees. Historical rates are bundled in `agent/eur_gbp_rates.json` from https://api.frankfurter.dev/v1/2021-01-01..2026-02-02?base=EUR&symbols=GBP (documentation: https://frankfurter.dev/v1/). Missing dates are fetched explicitly; conversion failures block generation rather than guess a rate. Other source currencies require an explicit conversion before publication.

`sudo python3 agent/migrate_sterling.py` previews existing bank conversions; `--apply` backs up the database and updates in place, preserving question IDs, correct-answer indexes, usage history and daily rounds. Original question records are retained in `sterling_conversion_audit`.

## Daily question variety
Every round must pass `question_variety.validate_round`: no overlapping broad question families across all five questions, including the fresh one. Different seasons, facts and archive wording do not count as different types. Families include high-scoring matches, match scores/goal totals, first goals, managers, transfers, attendance, discipline, runs, cups and player scoring. Questions may occupy multiple families. The selector keeps least-used ordering where compatible and searches for a valid mix; it can choose a different fresh-question type for sparse banks. It fails publication rather than silently repeat a type. Unknown wording must be classified before publication.

Verification: `sudo python3 agent/test_question_variety.py` checks similar-question examples and 1,800 club/date/fresh-type combinations using the current bank. Enabled for rounds from 15 September 2026; existing rounds are preserved.

## Player-use and match rules (September 2026)
- A round cannot repeat a match, even across different question families. Match-linked questions share a conservative club/date identity across sources; missing match dates block selection. Fixtures for a club on the same date are treated as conflicting.
- Never ask which team/side scored first. The builder excludes these questions and the selector rejects them. Existing bank rows are retired while old daily-round references and player results are preserved.
- Publication no longer increments `use_count` or `last_used_date`. A `shown` event records the first time a player sees each question on a UK day; refreshes and further players do not increment it again that day. Questions nobody sees remain eligible tomorrow, subject to the other selection rules. Reuse is permitted, not guaranteed.
- Historical usage counts are retained conservatively because per-question exposure was not previously recorded. At migration, today's completely unplayed club rounds are refunded using existing start/completion events. Played clubs are conservatively marked used for today.

Deployment: pause the publication timer, back up code, run `python3 agent/migrate_question_rules.py --apply` before deploying `site/track.php`, `site/index.php` and the updated agent modules together. The migration backs up SQLite, preserves today's rounds, retires banned bank entries and removes future prepared rounds for regeneration. Re-run the publisher and re-enable the timer. The eligible bank can temporarily be below 300 after retirement; do not rebuild the whole bank merely to refill it, since the old builder installer deletes round history.

Checks: `python3 -m unittest test_question_rules test_match_perspective test_player_usage test_question_variety` from `agent/`. The usage test needs PHP; the variety test needs read access to the live bank. Player usage tracking requires the new schema. No paid generation services are introduced.

## Aggregate-only owner statistics
The owner page now reads only a small `club_daily_totals` table and the club names. It shows starts/completions per club for today, this calendar week (Monday start), and this calendar month in Europe/London time. These are round counts, not deduplicated people across days, clubs or devices. No player IDs, individual event rows, profiles, selection events or per-person timestamps are retained in analytics. Browser-local per-club/day event flags prevent ordinary refresh duplicates; Web Locks coordinate tabs when available. Without server identifiers, hostile submissions and cleared browser storage cannot be deduplicated reliably.

`migrate_aggregate_analytics.py DATABASE` converts existing start/completion events into totals, drops the individual event table, securely deletes SQLite freed pages and truncates its WAL. Run it on the live analytics database and retained old copies; do not create backups of the identifiers being removed. It is idempotent and preserves concurrently accumulated new totals. Deploy by first creating `club_daily_totals`, installing the new tracker, then running the migration and installing the dashboard/client. Keep existing owner authentication in place.

Only daily totals needed for the current month or overlapping current week are retained; each aggregate write prunes older dates. Question-use records remain separate anonymous question/day flags, with no player linkage. Existing locally saved game results and daily play limits remain intact.
