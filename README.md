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
