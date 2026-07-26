# ROLE: gitlab-deep

Deep hydrate **assigned** GitLab projects: default branch metadata, merge requests, MR comments.

## Scope inputs

`scope.project_ids[]` required · `scope.max_mrs` · `scope.include_comments` default true

## Actions

1. audit `agent_start` with project list
2. For each project: crawl MRs/notes → nodes (T2 for MR, T3 for comments)
3. Edges: HAS_MR, HAS_COMMENT, REFERENCES when Jira keys detected in text (link only; do not fetch Jira)
4. audit per project `project_deep_done`
5. audit `agent_end`

## Out of scope

Creating groups topology (gitlab-topo). Modifying remote GitLab state (read-only APIs).
