# Source review: Winston-Salem Open 2026

Reviewed on 2026-08-12 for the project's first real collector.

## Selected source

- Official announcement: <https://www.winstonsalemopen.com/en/media/news/2026-player-announcement>
- Publisher: Winston-Salem Open, an ATP official tournament
- Publication date: 2026-07-28
- Source classification: `tournament_official`

The announcement explicitly calls the data a main-draw player list, states that it contains 37 direct entries, supplies rankings as of 2026-07-27, and says that the list is subject to change. The collector therefore records `DA` only; it does not infer wild cards, alternates, or withdrawals.

Tournament surface, main-draw size, and calendar dates were cross-checked against the ATP tournament overview at <https://www.atptour.com/en/tournaments/winston-salem/6242/overview>. The tournament's own About page confirms a 16-player qualifying draw: <https://www.winstonsalemopen.com/en/tournament/about>.

## Access review

`https://www.winstonsalemopen.com/robots.txt` returned HTTP 200 on 2026-08-12. It disallows selected paths including `/sitecore/`, AJAX, search, archive, and match-stat endpoints. The selected public news announcement is not disallowed.

No authentication, paywall, CAPTCHA, browser automation, hidden endpoint, or access-control bypass is used. The collector makes one direct HTTP GET with a descriptive user agent and a 20-second timeout. It is not scheduled yet. If scheduling is introduced, runs should initially be limited to a few times per day and retain the last valid snapshot on failure.

The site's visible policy link concerns ticketing and does not provide a separate automated-use license. This review is an engineering access assessment, not legal advice. If the publisher later states a restriction, collection must stop pending review.

## Parser safety

The parser requires all of the following:

- the exact main-draw list heading;
- a parseable ranking date;
- the article's explicit direct-entry count;
- the same number of parsed player rows as the declared count.

A zero or partial parse raises a typed failure and is never accepted as a valid list.

