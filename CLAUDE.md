# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

jira-data-proxy is a **read-only** proxy of the Jira API for USDF RSP and [Times Square](https://github.com/lsst-sqre/times-square) report users. Callers authenticate with Gafaelfawr using ordinary Science Platform tokens; the proxy itself talks to Jira with a bot account's basic auth. Only `GET` is proxied, so the service cannot create or modify issues.

Deployed with Phalanx as the `jira-data-proxy` application.

**Stack:** Python 3.14 (pinned in `.python-version`, `requires-python = ">=3.14"`), FastAPI, Safir, Pydantic settings, uv for dependency management (a single committed `uv.lock`), nox as the task runner.

## Development commands

```bash
make init          # uv sync --frozen --all-groups; uv run prek install
make run           # dev server with auto-reload (nox -s run)
make update        # update-deps, then init
make update-deps   # uv lock --upgrade, prek autoupdate, ./scripts/update-uv-version.sh
```

Everything else goes through nox, always invoked via the `nox` dependency group:

```bash
uv run --only-group=nox nox                          # default: lint, typing, test
uv run --only-group=nox nox -s lint                  # prek run --all-files
uv run --only-group=nox nox -s typing                # mypy src/jiradataproxy tests
uv run --only-group=nox nox -s test                  # pytest with coverage collected
uv run --only-group=nox nox -s test-coverage         # test, then coverage report
uv run --only-group=nox nox -s test -- tests/handlers/external_test.py
```

CI runs `nox -s lint` and `nox -s typing test-coverage`. Periodic CI adds `make update-deps` first, to catch breakage from new dependency releases.

**Linting is prek, not pre-commit.** `prek` is a Rust reimplementation that reads the same `.pre-commit-config.yaml`; don't reintroduce `pre-commit` or `pre-commit-uv`.

## Configuration and the JIRA_* env vars

`jiradataproxy.config` builds its `Configuration` object **at import time**, and `JIRA_USERNAME` / `JIRA_PASSWORD` have no defaults. Anything that imports the application therefore needs them in the environment first. Two places handle that, and both should stay:

- the root `conftest.py` `setdefault()`s them, so a bare `pytest` works;
- `noxfile.py`'s `_make_env_vars()` passes them explicitly to the `test` and `run` sessions.

Settings are read via `validation_alias`, so the env var names are not prefixed uniformly — `SAFIR_*` for the Safir-standard settings and bare `JIRA_*` for the Jira ones. See `src/jiradataproxy/config.py`.

## Architecture

Small enough to read end to end:

- `main.py` — app factory. Built at module import (the standard FastAPI-service pattern), mounts `internal_router` at `/` and `external_router` under `config.path_prefix`, adds `XForwardedMiddleware`, and closes Safir's shared HTTP client in the lifespan.
- `handlers/internal.py` — the unprefixed `/` metadata endpoint Phalanx and Gafaelfawr expect.
- `handlers/external.py` — the proxy itself: `resolve_jira_url()` plus a single catch-all `GET /{path:path}` handler.

### resolve_jira_url is a security boundary

This is the one piece of code in the repo that is subtle, and it is the fix for DM-55651. The proxy attaches the Jira bot account's credentials to the upstream request, so a path that resolves to some other host would hand those credentials away. `urllib.parse.urljoin` gives no containment on its own — it returns its second argument unchanged when that argument is absolute (`https://evil.example.org/`) or protocol-relative (`//evil.example.org/`).

So the joined URL is parsed as an `httpx.URL` and checked against the base URL's `(scheme, host, port)` and path prefix, and **that same parsed object** is what gets sent upstream — validating with the parser that issues the request leaves no room for the two to disagree about which host a URL names. When you touch this function, keep that property: don't re-derive the request URL from the string after validating.

`tests/handlers/external_test.py` covers the escape attempts. Add to it rather than trimming it.

## Testing

pytest with `pytest-asyncio` in strict mode; `respx` mocks the upstream Jira responses and `asgi-lifespan` drives the app lifespan. Fixtures live in `tests/conftest.py`, shared constants in `tests/support/constants.py`.

## Releases

scriv changelog fragments in `changelog.d/`, collected into `CHANGELOG.md`, then a GitHub release; tagging triggers the Docker build and push to GHCR in `ci.yaml`. Deployment is a version bump in the Phalanx `jira-data-proxy` application.

Write a changelog fragment for user-visible changes. Internal developer tooling (task runner, linting, lockfile mechanics) does not get one.

## Conventions

- Ruff for linting and formatting, configured by the vendored `ruff-shared.toml` plus project-specific overrides in `pyproject.toml`. Don't edit `ruff-shared.toml` by hand for project reasons — it is a fleet-shared file.
- mypy is strict: every function needs annotations.
- Work on `tickets/DM-XXXXX` branches and open a PR; never push to `main`. PR titles are `DM-XXXXX: Summary`.
