# EFL extension and player research

The home chooser covers the current Football-Data E0/E1/E2/E3 season, with 20 Premier League and 24 clubs in each EFL division. Club identities and source URLs are in efl_catalog.py and efl_clubs_sources.json. Existing club IDs, rounds, games, usage and analytics are preserved.

## Daily Five
build_efl_bank.py imports source facts additively: club profile facts, completed historical league results and discipline, complete-season results and runs, FA Cup exits, player biographies and season appearances. It rejects incomplete season aggregates, ambiguous leaders, leaked answers and non-distinct distractors. The publisher preserves complete existing club rounds, requires different question families and match dates, and uses an unused historical fact for EFL clubs when current facts are unavailable. Recent fact-family and generic repeat windows remain enforced.

Sources: Football-Data CSVs, Wikipedia club profiles and attributed Transfermarkt profiles/performance records. Durable input datasets live under /var/lib/clubdailyfive/player-sources and /var/lib/clubdailyfive/transfermarkt-data; they are not committed to Git.

## Player Wordle
collect_efl_players.py requires a sourced exact competitive debut date, complete senior club history, nationality, age, year and an unambiguous prominent position before admitting a new player. It does not approximate debut ages from season start dates or supply a default position. Ambiguous or incomplete candidates stay in efl_player_research and player_candidates. Clubs open when they have at least ten verified players and a published mystery player. The initial release admitted 34 EFL player records; all new EFL Wordle games remain in preparation.

The Hull archive at https://tigerbase.hullcity.com/tigers-players.php?select_col=pos matched 156 Hull records, supporting 17 changes including Markus Henriksen to Midfielder. position_overrides retains evidence and a database trigger protects verified corrections against subsequent imports. The wider position audit is ongoing: disputed roles require review and are not silently rewritten from a player's latest career profile.

## Scheduled operation
The existing question and Wordle timers retain their UK schedule and report wrapper. efl_research_job.py bounds research and allows the publisher to continue using verified banks after a source failure. Wikipedia requests are cached, paced, capped at 100 per process and halted on a 429. Position audit and new-club research receive separate bounded runs. Transient failures are retried on later days. New-player research starts with clubs having the smallest banks.

The optional walkthrough can be dismissed, replayed and completed without making a guess. It explains the five clues and the actual green/amber/grey rules. Local storage remembers dismissal.

## Validation and deployment
deploy_efl_data.py backs up both databases and adds staging records using slug/name ID mappings. It asserts existing rounds and games are unchanged, checks foreign keys/integrity, and tests the Henriksen protection trigger. The one-time staging databases are deployment inputs, not nightly jobs.

The release passed a frozen-fixture 30-day simulation for all 72 new clubs (2,160 rounds / 10,800 slots), the question rule, match perspective, player usage and variety suites, new EFL integrity regressions, PHP syntax checks and all 72 live quiz routes. Browser checks confirmed league filtering, new-club preparation status, guide completion, no guess consumption and remembered dismissal.
