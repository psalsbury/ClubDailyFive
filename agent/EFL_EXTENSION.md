# Premier League and Championship
The site supports 20 Premier League clubs and 24 Championship clubs. Football-Data E0/E1 determines membership. League One and League Two club banks, research queues, analytics, owned crests and page profiles were removed on 5 October 2026. Recovery copies are outside live databases. Shared historical opponent and career source records remain available for supported-club facts.

## Player research
The target is 100 playable players per club. transfermarkt_players.py reads player profiles, recent season performances, individual match appearances and transfers. It prepares up to 100 eligible candidates per club and stores attributed evidence in transfermarkt_research. Existing banks above 100 are retained.

Season years distinguish 1990s from 2090s. Future transfers are excluded. The earliest appearance in a partial dataset is never treated as proof of a debut. Citizenship does not automatically establish football nationality. Profiles with uncertain roles, debut dates or previous senior clubs remain in enrichment_queue.

Separate explicit debut evidence is cross-checked before new playable rows are added. Multiple day/month dates in a sentence are rejected to avoid using transfer dates as debut dates. Existing verified position overrides remain protected. Attacking midfielder is classified as Midfielder.

## Scheduled operation
The existing nightly timer runs transfermarkt_players.py through the reporting wrapper, followed by the daily mystery-player publisher. Smaller banks receive fresh evidence research first. At most 40 new evidence-page requests are attempted per run; cached pages are reused, requests are paced and rate limits halt fresh requests. Source failures preserve existing verified games. Research records and playable-player counts are separate in player-bank-progress.json.

A club still requires at least ten verified players and a published daily game to open; the long-term target is 100. Some clubs have fewer than 100 candidates under the current eligibility criteria. Historical international and cup-final eligibility need separate evidence before expanding these pools.

## Daily Five and deployment
Existing Premier League and Championship rounds and usage records are preserved. The question generator uses only the two supported leagues for catalogue membership, while supported clubs' earlier seasons may include other divisions. Staging deployment rejects parked clubs. Source inputs and database snapshots are not committed to Git.
