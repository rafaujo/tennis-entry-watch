# Tournament calendar catalog

## Sources

- ATP Tour calendar (official verification): https://www.atptour.com/en/tournaments
- ATP Challenger Tour calendar (official verification): https://www.atptour.com/en/challenger-tour/calendar
- Annual ATP Tour calendar (automated structured source): https://en.wikipedia.org/wiki/2026_ATP_Tour
- Annual ATP Challenger Tour calendar (automated structured source): https://en.wikipedia.org/wiki/2026_ATP_Challenger_Tour

## Collection policy

The public ATP calendar pages are protected by Cloudflare and return HTTP 403 to the unattended GitHub Actions collector. The automated parser therefore reads the annual structured Wikipedia calendar tables and labels them as `trusted_secondary`. Official ATP URLs remain attached to the catalog for supervised verification.

The collector requires at least 50 Grand Slam/ATP events and 100 Challenger events, validates all records with Pydantic, and writes atomically only when semantic data changes. Parsing or count failures leave the last valid catalog untouched.

`data/tournaments/overrides.json` contains reviewed corrections for source naming, schedule aliases, exceptional start dates, locations, and draw metadata. This file is never overwritten by automation.

## Site lifecycle

- Homepage: current week plus the next five tournament weeks.
- Monitoring: calendar event exists, but no tracked entry list was found.
- Active: current date is inside the event date range.
- Archive: event ended after tracking began; its generated entry-list page remains accessible.
- Year rollover: current-year events are merged into the stored catalog so prior tracked history remains available.
