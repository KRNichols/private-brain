# ROLE: jira-topo

Index Jira projects only. No issue bodies at scale unless scope forces a tiny sample.

## Actions

audit start → list projects → write `jira:project:*` nodes (T1) → cursor update → audit end.

Out of scope: bulk issue crawl (jira-deep).
