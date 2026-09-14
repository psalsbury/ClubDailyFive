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
