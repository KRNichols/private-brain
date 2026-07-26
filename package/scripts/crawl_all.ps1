# Fan-out crawl DAG: GitLab → Jira → Confluence (sequential for API politeness).
# Codex may also spawn these in parallel via multi-agent.

$ErrorActionPreference = "Continue"
$BrainRoot = if ($env:PRIVATE_BRAIN_HOME) { $env:PRIVATE_BRAIN_HOME }
             elseif ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "private-brain" }
             else { Join-Path $env:USERPROFILE ".codex\private-brain" }

$scripts = Join-Path $BrainRoot "scripts"
Write-Host "=== CRAWL ALL (Private Brain) ===" -ForegroundColor Magenta

if ($env:GITLAB_TOKEN) {
    & "$scripts\crawl_gitlab.ps1" -Mode auto
} else { Write-Host "skip GitLab (no GITLAB_TOKEN)" -ForegroundColor Yellow }

if ($env:JIRA_API_TOKEN) {
    & "$scripts\crawl_jira.ps1" -Mode auto
} else { Write-Host "skip Jira (no JIRA_API_TOKEN)" -ForegroundColor Yellow }

if ($env:CONFLUENCE_API_TOKEN) {
    & "$scripts\crawl_confluence.ps1" -Mode auto
} else { Write-Host "skip Confluence (no CONFLUENCE_API_TOKEN)" -ForegroundColor Yellow }

& "$scripts\session_boot.ps1"
Write-Host "=== CRAWL ALL DONE ===" -ForegroundColor Green
