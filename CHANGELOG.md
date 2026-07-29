# Change log

jira-data-proxy is versioned with [semver](https://semver.org/).
Dependencies are updated to the latest available version during each release, and aren't noted here.

Find changes for the upcoming release in the project's [changelog.d directory](https://github.com/lsst-sqre/jira-data-proxy/tree/main/changelog.d/).

<!-- scriv-insert-here -->

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
