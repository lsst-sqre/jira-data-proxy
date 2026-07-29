"""Root pytest configuration.

``jiradataproxy.config`` builds its ``Configuration`` object at import time and
``JIRA_USERNAME`` and ``JIRA_PASSWORD`` have no defaults, so those settings
must be present in the environment before any test module imports the
application. Setting them here, in the root ``conftest.py``, means a bare
``pytest`` invocation works without a test runner supplying the values. The
values are only defaults: ``noxfile.py`` (and anyone running pytest by hand)
can still override them.
"""

import os

os.environ.setdefault("JIRA_USERNAME", "test-user")
os.environ.setdefault("JIRA_PASSWORD", "test-password")
