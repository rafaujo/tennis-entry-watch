# Tennis Entry Watch

Tennis Entry Watch is a small, auditable tracker for upcoming ATP men's singles entry lists. Its focus is direct acceptances, alternates, withdrawals, protected rankings, wild cards, projected seeds, provenance, and list history—not live scores or full ranking calculations.

## Current status

The current milestone turns the proof of concept into a multi-tournament entry watch. It includes the official Winston-Salem announcement and the official US Open men's main-draw/alternate PDF, an objective alternate queue, qualifying-list support, live rankings, ranking-ordered player schedules, validated domain models, structured change detection, and GitHub Pages automation.

The Live Tennis snapshot also generates tracked entry pages for the August 17 Challenger events in Cancun, Quebec City, Kingston, Prague, Roehampton, and Sion. These pages include the listed main-draw and qualifying players, current ranks, projected seeds, and unassigned reserved places. They are clearly identified as secondary-source lists until an official tournament document supersedes them.

## Architecture

```text
validated JSON snapshots
        ↓
Pydantic domain models
        ↓
deterministic comparison
        ↓
structured changes + static HTML
```

The repository's JSON and Git history provide an audit trail, while `EntryChange` supplies explicit domain history. Every entry carries its source URL, retrieval time, source type, and collector name.

Important boundaries:

- An `OUT` entry is an explicit withdrawal and records its previous status.
- A player missing from the new snapshot produces `PLAYER_REMOVED`; the detector does not guess that this means withdrawal.
- `ALT` entries require unique positive alternate positions.
- Statuses are an enum that can be extended when a verified ATP-specific case appears.
- Unknown facts remain `null`; sample values are clearly marked fictional.

## Repository layout

```text
src/tennis_entry_watch/
  models/          Pydantic domain types
  changes/         Snapshot comparison
  site/            Static HTML generation
data/entries/      Git-tracked snapshots
docs/sources/       Per-source access and provenance reviews
tests/             Offline unit tests
site/              Generated GitHub Pages artifact
.github/workflows/ CI and Pages deployment
```

## Development

Python 3.11 or newer is required.

```bash
python -m venv .venv
# Activate the environment, then:
python -m pip install -e ".[dev]"
pytest
python -m tennis_entry_watch.site.build
# Explicit network operation; fetches one official announcement:
python -m tennis_entry_watch.collectors.winston_salem_cli
```

The build discovers every `data/entries/*/current.json` file (excluding sample data), then writes the tournament dashboard, one page per tournament, and `site/schedules/index.html`. Tests are fully offline and never contact third-party sites. Collectors write only after HTTP, parsing, count, and Pydantic validation succeed, using an atomic file replacement.

## Change detection

`detect_changes(previous, current)` currently reports:

- `PLAYER_ADDED`
- `PLAYER_REMOVED`
- `PLAYER_WITHDRAWN`
- `ALT_POSITION_CHANGED`
- `ALT_TO_MAIN_DRAW`
- `STATUS_CHANGED`
- `ENTRY_RANK_CHANGED`

It rejects snapshots for different tournaments and snapshots supplied out of chronological order. Inputs are validated before comparison.

## Automation

`test.yml` runs tests and verifies the static build on pushes and pull requests. `deploy-pages.yml` tests, builds, uploads the `site/` artifact, and deploys it through GitHub Pages on pushes to `main` or manual dispatch.

The repository owner must select **GitHub Actions** as the Pages source in repository settings. Deployment uses GitHub's standard Pages permissions and requires no secrets. The workflow is prepared but cannot deploy until the repository exists on GitHub and Pages is enabled.

## Provenance policy

Important external facts must retain source URL, retrieval timestamp, source type, and collector. Preferred sources are ATP official material, official tournament material, then established specialist sources. Lower-confidence material must not silently replace higher-confidence facts. AI-extracted material, if introduced later, remains explicitly labeled and must pass deterministic validation before publication.

## First real source

The Winston-Salem collector parses a dated official tournament announcement containing 37 explicitly identified direct entries and their 2026-07-27 rankings. The US Open snapshot contains 104 current main-field names, 99 alternates, one withdrawal, and one promotion from the official report created on 2026-08-02. Neither dataset infers entry from ranking alone.

## Known limitations

- The comparison demo remains fictional; the Winston-Salem snapshot is real sourced data.
- There is one collector only, no ranking provider, and no automated data commits yet.
- Name-derived player IDs are a conservative fallback because this announcement exposes no stable ATP identifier; there is no fuzzy matching.
- Validation covers core schema invariants, not expected draw occupancy or suspiciously large changes.
- Until a verified qualifying list is available, registered main-draw alternates are shown as projected qualifying candidates (`PROJ Q`).
- Queue distance is deterministic; it is not presented as a subjective probability.
- The generated site does not yet render a historical change timeline.
- Projected seeds are accepted as sourced data; no seeding calculation is implemented.

## Recommended next milestone

Observe this one source through at least one real change, preserve the prior valid snapshot, run deterministic change detection, and publish a change timeline. Do not add multiple collectors until this source teaches us how updates and withdrawals are represented.
