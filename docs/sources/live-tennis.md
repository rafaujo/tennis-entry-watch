# Live Tennis ranking and schedules

- Ranking: <https://live-tennis.eu/en/atp-live-ranking>
- Schedules: <https://live-tennis.eu/en/atp-schedule>
- Role: tracked secondary source

The snapshot supplies the current live rank, points, and additional tournament listings. Official tournament documents remain authoritative for main-draw status, alternate order, withdrawals, and promotions.

For the US Open qualifying projection, `LISTED Q` means the Live Tennis schedule explicitly contains `Qual. US Open`. `PROJ Q` means the player is on the verified main-draw alternate list but is not explicitly marked for qualifying in the captured secondary schedule.

Player schedules and live rankings are time-sensitive. Every generated page displays the snapshot retrieval timestamp.

## Automated collection

The public ranking and schedule pages are retrieved three times per day with a descriptive user agent and a 30-second timeout per request. The collector reads only the visible player table and does not use authentication, browser automation, hidden endpoints, or access-control bypasses.

Before replacing the Git-tracked snapshot, validation requires:

- 900–1,200 rows in both tables;
- non-decreasing ranks beginning at No. 1;
- unique normalized player names in each table;
- at least 95% player overlap between ranking and schedule tables;
- at least 85% ranking-player overlap with the previous valid snapshot.

The file is replaced atomically only after validation. An unchanged semantic payload preserves the previous retrieval timestamp, preventing empty automated pull requests. Failures leave the last valid snapshot and published site untouched.
