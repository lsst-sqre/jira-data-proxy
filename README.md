# jira-data-proxy

This application provides a read-only proxy of the Jira API for USDF RSP/[Times Square](https://github.com/lsst-sqre/times-square) report users.
User authentication is handled by Gafaelfawr using regular Science Platform tokens.
Jira Data Proxy itself uses a bot account to access Jira (since requsets are only GETs, there is no need to use a real user account).
This means that the Jira Data Proxy cannot be used to create or modify Jira issues.

## Example usage

Using [httpie](https://httpie.org/), with `-a` corresponding to a Gafaelfawr token with a notebook execution role:

```bash
http -A bearer -a "gt-T-..." get "https://data-dev.lsst.cloud/jira-data-proxy/rest/api/2/search?jql=assignee=jsick&maxResults=1"
```
