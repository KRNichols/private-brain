# ROLE: jira-deep

Hydrate issues/comments/links for scoped projects or JQL.

## Scope

`scope.project_key` or `scope.jql` · `scope.max_issues`

## Rules

- Issues = T1; comments = T3
- audit every batch
- Read-only Jira APIs
- Detect GitLab MR references in text as REFERENCES edges (ids only)
