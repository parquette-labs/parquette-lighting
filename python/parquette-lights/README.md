# parquette.lights

The lighting server (Poetry project, package `parquette.lights`). See the
[root README](../../README.md) for setup, running, wiring, and deploy details.

Common commands (run from this directory):

- `poetry sync` — install deps
- `poetry run server` — run the server (`--help` for flags)
- `poetry run poe check` — black + pylint + mypy
- `poetry run poe pytest` — test suite
- `poetry run poe deploy` — deploy to the mac mini
