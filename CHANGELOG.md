# Change log

jira-data-proxy is versioned with [semver](https://semver.org/).
Dependencies are updated to the latest available version during each release, and aren't noted here.

Find changes for the upcoming release in the project's [changelog.d directory](https://github.com/lsst-sqre/jira-data-proxy/tree/main/changelog.d/).

<!-- scriv-insert-here -->

<a id='changelog-1.0.2'></a>
## 1.0.2 (2026-07-29)

### Other changes

- Lock dependencies with `uv.lock` instead of `requirements/*.txt`. Runtime
  dependencies now live in `[project.dependencies]` and development
  dependencies in `[dependency-groups]`, the Docker image builds with the
  multi-stage `uv sync --frozen` pattern, and CI installs with uv rather than
  pip. `make update` refreshes the lockfile, the prek hooks, and the pinned uv
  version in one step.

- Retire neophile. The weekly dependency-update workflow is gone; dependabot
  already covers GitHub Actions and Docker base images, and `make update`
  covers Python dependencies.

- Remove the `jira-data-proxy` console script entry point. It pointed at
  `jiradataproxy.cli:main`, a module that has never existed, so the installed
  script could only ever fail on invocation. The container entrypoint is
  uvicorn and is unaffected.

- Require Python 3.14 or later, up from a declared floor of 3.11.
  `.python-version`, the Docker base image, the `requires-python` floor, the
  Ruff `target-version`, and the PyPI classifier now all name 3.14, and the
  Docker base image moves from Debian bullseye to bookworm, which is where the
  3.14 slim images are published. The old 3.11 floor was not merely stale but
  load-bearing: it forked the lockfile into a 3.11 resolution branch that
  selected Safir 9.3.0 and Starlette 0.52.1, the release line predating the fix
  for CVE-2026-48710. CI takes the new interpreter automatically — neither the
  CI nor the periodic-CI workflow pins a Python version, so both follow
  `.python-version` through uv.

- Require Safir 15.1.1 or later, up from 5.0.0. Safir 15.1.1 pins Starlette to
  1.0.1 or later and so ensures the fix for CVE-2026-48710 is present; a floor
  this low was free to resolve a Safir old enough to permit a vulnerable
  Starlette. Every Safir API this service uses is unchanged across the 5 to 15
  span, so no application code needed to move.

- Declare floors for the FastAPI stack: `fastapi>=0.141`, `starlette>=1.0.1`,
  and `pydantic>=2.13`. The Starlette floor duplicates the one Safir 15.1.1
  imposes so that the CVE-2026-48710 fix stays required here even if Safir's
  own constraint changes.

- Move `pydantic` from the `dev` dependency group into the runtime
  dependencies. `jiradataproxy.config` imports `Field`, `HttpUrl`, and
  `SecretStr` from it directly, so it was a runtime dependency that happened to
  be satisfied transitively through `pydantic-settings`.

<a id='changelog-1.0.1'></a>
## 1.0.1 (2026-07-28)

### Bug fixes

- Pass the `lifespan` context manager to the `FastAPI` constructor. The lifespan hook was defined but never registered, so the shared `httpx.AsyncClient` provided by Safir's `http_client_dependency` was never closed when the application shut down.

- Refuse proxied paths that resolve outside the configured Jira base URL. `urllib.parse.urljoin` returns its second argument unchanged when that argument is an absolute (`https://evil.example.org/`) or protocol-relative (`//evil.example.org/`) URL, so any authenticated caller could name a host of their choosing and have the proxy send the Jira bot account's basic auth credentials there, as well as use the service as an SSRF pivot to anything reachable from its pod. The joined URL is now parsed with the same parser that issues the upstream request, and the request is refused with a 404 unless the URL's scheme, host, and port match `JIRA_BASE_URL` and its path stays at or below the base URL's path.
- Return a 404 rather than failing with an unhandled exception when the proxied path cannot be parsed as a URL, such as `https://[/`.

<a id='changelog-1.0.0'></a>
## 1.0.0 (2024-01-23)

### New features

- First release of Jira Data Proxy. This is a new service that proxies GET requests to Jira's REST API and accepts authentication using Rubin Science Platform security tokens.
