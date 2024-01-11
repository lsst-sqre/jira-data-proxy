"""Configuration definition."""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings
from safir.logging import LogLevel, Profile

__all__ = ["Configuration", "config"]


class Configuration(BaseSettings):
    """Configuration for jira-data-proxy."""

    name: str = Field(
        "jira-data-proxy",
        title="Name of application",
        validation_alias="SAFIR_NAME",
    )

    path_prefix: str = Field(
        "/jira-data-proxy",
        title="URL prefix for application",
        validation_alias="SAFIR_PATH_PREFIX",
    )

    profile: Profile = Field(
        Profile.development,
        title="Application logging profile",
        validation_alias="SAFIR_PROFILE",
    )

    log_level: LogLevel = Field(
        LogLevel.INFO,
        title="Log level of the application's logger",
        validation_alias="SAFIR_LOG_LEVEL",
    )

    jira_username: str = Field(
        ...,
        title="Username for Jira basic auth",
        validation_alias="JIRA_USERNAME",
    )

    jira_password: SecretStr = Field(
        ...,
        title="Password for Jira basic auth",
        validation_alias="JIRA_PASSWORD",
    )

    jira_base_url: str = Field(
        "https://jira.lsstcorp.org/",
        title="Base URL for the Jira API",
        validation_alias="JIRA_BASE_URL",
    )


config = Configuration()
"""Configuration for jira-data-proxy."""
