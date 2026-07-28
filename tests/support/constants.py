"""Constants used in test fixtures and setup."""

__all__ = [
    "TEST_BASE_URL",
    "TEST_JIRA_BASE_URL",
    "TEST_JIRA_PASSWORD",
    "TEST_JIRA_USERNAME",
]

TEST_BASE_URL = "https://example.com/"
"""Base URL at which the jira-data-proxy test server is mounted."""

TEST_JIRA_BASE_URL = "https://jira.example.org/"
"""Base URL of the mock upstream Jira server."""

TEST_JIRA_USERNAME = "test-user"
"""Username the application uses for Jira basic auth in tests."""

TEST_JIRA_PASSWORD = "test-password"
"""Password the application uses for Jira basic auth in tests."""
