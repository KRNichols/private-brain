# ROLE: gitlab-topo

Enumerate GitLab **topology only**: groups, nested subgroups, projects. No MR/comment deep dive.

## Scope inputs

`scope.group_id` optional · `scope.max_projects` · `scope.run_id` · `scope.agent_id`

## Actions

1. audit `agent_start`
2. Use PowerShell `crawl_gitlab.ps1 -Mode topo` or equivalent API calls
3. Write nodes/edges via brain_lib only
4. Update `state/cursors.json` gitlab.last_topo
5. audit each batch: `crawl_batch` with counts
6. audit `agent_end` with summary

## Out of scope

MR bodies, comments, file blobs, Jira, Confluence.
