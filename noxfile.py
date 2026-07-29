"""Nox configuration for jira-data-proxy."""

from __future__ import annotations

import nox
from nox_uv import session

# Default sessions (run with `nox`)
nox.options.sessions = ["lint", "typing", "test"]

# Other nox defaults
nox.options.default_venv_backend = "uv"
nox.options.reuse_existing_virtualenvs = True


def _make_env_vars(overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Create an environment variable dictionary that lets the app start up.

    ``jiradataproxy.config`` builds its ``Configuration`` at import time and
    ``JIRA_USERNAME`` and ``JIRA_PASSWORD`` have no defaults, so they must be
    in the environment before the application is imported. The root
    ``conftest.py`` sets the same two variables with ``setdefault`` so that a
    bare ``pytest`` also works; setting them here keeps the values the nox
    sessions run under explicit rather than implicit.
    """
    env_vars = {
        "JIRA_USERNAME": "USER",
        "JIRA_PASSWORD": "PASS",
    }
    if overrides:
        env_vars.update(overrides)
    return env_vars


@session(uv_only_groups=["lint"], uv_no_install_project=True)
def lint(session: nox.Session) -> None:
    """Lint the codebase by running prek."""
    session.run("prek", "run", "--all-files", *session.posargs)


@session(uv_groups=["typing", "dev"])
def typing(session: nox.Session) -> None:
    """Run mypy."""
    session.run("mypy", "src/jiradataproxy", "tests", *session.posargs)


@session(uv_groups=["dev"])
def test(session: nox.Session) -> None:
    """Run the test suite."""
    session.run(
        "pytest",
        "--cov=jiradataproxy",
        "--cov-branch",
        "--cov-report=",
        *session.posargs,
        env=_make_env_vars(),
    )


@session(name="test-coverage", uv_groups=["dev"])
def test_coverage(session: nox.Session) -> None:
    """Run the test suite and report coverage."""
    test(session)
    session.run("coverage", "report")


@session(uv_groups=["dev"])
def run(session: nox.Session) -> None:
    """Run the development server with auto-reload for code changes."""
    session.run(
        "uvicorn",
        "jiradataproxy.main:app",
        "--reload",
        *session.posargs,
        env=_make_env_vars(),
    )
