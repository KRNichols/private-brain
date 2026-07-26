# Jira crawl → filesystem brain. Env: JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN
[CmdletBinding()]
param(
    [ValidateSet("topo", "deep", "auto")]
    [string]$Mode = "auto",
    [string]$ProjectKey = "",
    [int]$MaxIssues = 100
)

$ErrorActionPreference = "Stop"
$BrainRoot = if ($env:PRIVATE_BRAIN_HOME) { $env:PRIVATE_BRAIN_HOME }
             elseif ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "private-brain" }
             else { Join-Path $env:USERPROFILE ".codex\private-brain" }
$helper = Join-Path $PSScriptRoot "BrainPython.ps1"
if (Test-Path $helper) { . $helper; $Py = Get-BrainPython -BrainRoot $BrainRoot }
else {
  $Py = Join-Path $BrainRoot "venv\Scripts\python.exe"
  if (-not (Test-Path $Py)) {
    $u = Join-Path $BrainRoot "venv/bin/python3"
    if (Test-Path $u) { $Py = $u } else { $Py = "python" }
  }
}
$env:PYTHONPATH = Join-Path $BrainRoot "scripts"

if (-not $env:JIRA_API_TOKEN) { throw "JIRA_API_TOKEN not set" }
if (-not $env:JIRA_EMAIL) { throw "JIRA_EMAIL not set" }
$Base = $env:JIRA_URL.TrimEnd("/")
$pair = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($env:JIRA_EMAIL):$($env:JIRA_API_TOKEN)"))
$Headers = @{ Authorization = "Basic $pair"; Accept = "application/json" }

function Jira-Get($Path, $Query = @{}) {
    $qs = ($Query.GetEnumerator() | ForEach-Object { "$($_.Key)=$([uri]::EscapeDataString([string]$_.Value))" }) -join "&"
    $url = "$Base/rest/api/3$Path"
    if ($qs) { $url = "$url`?$qs" }
    Invoke-RestMethod -Headers $Headers -Uri $url -Method Get
}

function Add-Node($id, $type, $title, $tier, $uri, $parent, $content) {
    & $Py -c @"
from brain_lib import write_node
write_node(r'''$id''', type=r'''$type''', source='jira', title=r'''$title''', tier=r'''$tier''', uri=$(if($uri){"r'''$uri'''"}else{"None"}), parent_id=$(if($parent){"r'''$parent'''"}else{"None"}), content=$(if($content){"r'''$($content -replace "'","''")'''"}else{"None"}))
"@
}
function Add-Edge($src, $rel, $dst) {
    & $Py -c "from brain_lib import write_edge; write_edge(r'''$src''', r'''$rel''', r'''$dst''')"
}

Write-Host "Jira crawl mode=$Mode" -ForegroundColor Cyan

if ($Mode -in @("topo", "auto")) {
    $projects = Jira-Get "/project/search" @{ maxResults = 50 }
    foreach ($p in $projects.values) {
        $id = "jira:project:$($p.key)"
        Add-Node $id "JiraProject" $p.name "T1" "$Base/browse/$($p.key)" $null $p.description
    }
}

if ($Mode -in @("deep", "auto")) {
    $jql = if ($ProjectKey) { "project = $ProjectKey ORDER BY updated DESC" } else { "updated >= -30d ORDER BY updated DESC" }
    $start = 0
    $got = 0
    while ($got -lt $MaxIssues) {
        $resp = Jira-Get "/search" @{ jql = $jql; startAt = $start; maxResults = 50; fields = "summary,description,comment,project,issuetype,status,updated" }
        foreach ($issue in $resp.issues) {
            $id = "jira:issue:$($issue.key)"
            $parent = "jira:project:$($issue.fields.project.key)"
            $desc = $issue.fields.summary
            Add-Node $id "Issue" $issue.fields.summary "T1" "$Base/browse/$($issue.key)" $parent $desc
            Add-Edge $parent "CONTAINS" $id
            $got++
            if ($got -ge $MaxIssues) { break }
        }
        if ($resp.issues.Count -lt 50) { break }
        $start += 50
    }
    Write-Host "issues written: $got"
}

& $Py (Join-Path $BrainRoot "scripts\brain_snapshot.py")
Write-Host "Jira crawl done." -ForegroundColor Green
