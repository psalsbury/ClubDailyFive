# Premier League and Championship
The site supports 20 Premier League clubs and 24 Championship clubs. Football-Data E0/E1 determines membership. League One and League Two club banks, research queues, analytics, owned crests and page profiles were removed on 5 October 2026. Recovery copies are outside live databases. Shared historical opponent and career source records remain available for supported-club facts.

## Player research
The target is 100 playable players per club. transfermarkt_players.py reads player profiles, recent season performances, individual match appearances and transfers. It prepares up to 100 eligible candidates per club and stores attributed evidence in transfermarkt_research. Existing banks above 100 are retained.

Season years distinguish 1990s from 2090s. Future transfers are excluded. The earliest appearance in a partial dataset is never treated as proof of a debut. Citizenship does not automatically establish football nationality. Profiles with uncertain roles, debut dates or previous senior clubs remain in enrichment_queue.

Separate explicit debut evidence is cross-checked before new playable rows are added. Multiple day/month dates in a sentence are rejected to avoid using transfer dates as debut dates. Existing verified position overrides remain protected. Attacking midfielder is classified as Midfielder.

## Scheduled operation
The existing nightly timer runs transfermarkt_players.py through the reporting wrapper, followed by the bounded position audit and daily mystery-player publisher. Smaller banks receive fresh evidence research first. At most 40 new evidence-page requests are attempted per run; cached pages are reused, requests are paced and rate limits halt fresh requests. Source failures preserve existing verified games. Research records and playable-player counts are separate in player-bank-progress.json.

A club still requires at least ten verified players and a published daily game to open; the long-term target is 100. Some clubs have fewer than 100 candidates under the current eligibility criteria. Historical international and cup-final eligibility need separate evidence before expanding these pools.

## Daily Five and deployment
Existing Premier League and Championship rounds and usage records are preserved. The question generator uses only the two supported leagues for catalogue membership, while supported clubs' earlier seasons may include other divisions. Staging deployment rejects parked clubs. Source inputs and database snapshots are not committed to Git.

## Derby historical expansion
expand_derby_wikipedia.py reads the club's attributed 100-appearance Wikipedia list and linked biographies, supplemented by official Academy Hall of Fame first-team debuts and individually corroborated match reports. It requires sourced birth dates, competitive debut dates, typical positions, nationalities and prior senior careers before promoting rows. All-competition appearances are taken from the list; active stale totals and disputed careers remain in wikipedia_player_research. Database backups and evidence are retained outside Git. The first completed verification increased Derby from 8 to 45 playable players; 100 remains the target, with remaining clue gaps recorded. Existing selected games are preserved.

## Championship bulk expansion (5 October 2026)
agent/championship_expansion (deployed to /opt/clubdailyfive/bin/championship_expansion; working data and the applied record in /var/lib/clubdailyfive/championship-expansion) brought all 24 Championship clubs to 100 playable players, adding 2,265 rows. Steps, run from /opt/clubdailyfive/bin:
1. candidates.py: eligibility from the Transfermarkt season data (appeared in 2025/26, or 25+ appearances in 2016/17–2025/26) plus Wikidata for criterion 3 (played for the club since 2006/07 and for a European senior men's national team).
2. fetch_wiki.py: English Wikipedia articles found through Wikidata by Transfermarkt ID, fetched serially through the MediaWiki parse API (honours maxlag/Retry-After); identity confirmed by date of birth. wikidata_spells.py adds day-precision joining dates.
3. build.py with debut_finder.py and nationality.py: the five clues. Debut comes from Wikipedia prose restricted to the debut clause and to sentences about this club (not loans or opponents), resolved where needed against football-data.co.uk league fixture lists (opening/final day, opponent and score, "N days later"), and must fall in the player's first season with appearances for the club; a league-only first season requires the date to be a club league fixture. Otherwise the debut is estimated from that first season, anchored on a sourced joining date where one exists. Positions must agree between Transfermarkt and Wikipedia. Dual nationals use senior caps, then "represents X", then the article's opening line, then Transfermarkt's first-listed nationality.
4. apply.py: one transaction after a database backup; each row's efl_player_research reason records the precision ("exact debut date", "debut month and year" or "season-based debut estimate"), so estimates can be listed, upgraded or removed. Positions are not locked in position_overrides.
Result: 849 exact debut dates, 19 to the month, 1,397 season estimates (867 of them anchored on a sourced joining date). Soccerbase (JavaScript-only), 11v11 (bot challenge), FBref (blocked) and worldfootball.net (robots.txt excludes ClaudeBot) were not used; Transfermarkt pages were not scraped.
apply.py also added triggers canonical_nationality_insert/update so every writer stores one spelling per country (Republic of Ireland, Ivory Coast, South Korea, USA, Bosnia-Herzegovina, Turkey, Curacao); 207 existing rows were standardised.
