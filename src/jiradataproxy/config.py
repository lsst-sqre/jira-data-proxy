"""Configuration definition."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, HttpUrl, SecretStr
from pydantic.functional_validators import AfterValidator
from pydantic_settings import BaseSettings
from safir.logging import LogLevel, Profile

__all__ = ["Configuration", "config"]


def validate_root_url(url: HttpUrl) -> HttpUrl:
    """Validate that the URL ends with a trailing slash."""
    if not url.path:
        raise ValueError(
            "URL must have a path that ends with a trailing slash"
        )
    if not url.path.endswith("/"):
        raise ValueError("URL must end with a trailing slash")
    return url


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

    jira_base_url: Annotated[
        HttpUrl, AfterValidator(validate_root_url)
    ] = Field(
        HttpUrl("https://jira.lsstcorp.org/"),
        title="Base URL for the Jira API",
        validation_alias="JIRA_BASE_URL",
    )


config = Configuration()
"""Configuration for jira-data-proxy."""
