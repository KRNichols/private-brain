# GitLab topology + deep crawl into filesystem brain.
# Uses $env:GITLAB_URL and $env:GITLAB_TOKEN. Never prints token.
# Usage:
#   .\crawl_gitlab.ps1 -Mode topo
#   .\crawl_gitlab.ps1 -Mode deep -ProjectId 42
#   .\crawl_gitlab.ps1 -Mode auto

[CmdletBinding()]
param(
    [ValidateSet("topo", "deep", "auto")]
    [string]$Mode = "auto",
    [int]$ProjectId = 0,
    [string]$GroupId = "",
    [int]$MaxProjects = 50
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
    $u = Join-Path $BrainRoot "venv\Scripts\python.exe"
    if (-not (Test-Path $u)) { $u = Join-Path $BrainRoot "venv/bin/python3" }
    if (Test-Path $u) { $Py = $u } else { $Py = "python" }
  }
}
$Snap = Join-Path $BrainRoot "scripts\brain_snapshot.py"
$env:PYTHONPATH = Join-Path $BrainRoot "scripts"

if (-not $env:GITLAB_TOKEN) { throw "GITLAB_TOKEN not set" }
$Base = if ($env:GITLAB_URL) { $env:GITLAB_URL.TrimEnd("/") } else { "https://gitlab.com" }
$Headers = @{ "PRIVATE-TOKEN" = $env:GITLAB_TOKEN }

function Invoke-GL($Path, $Query = @{}) {
    $qs = ($Query.GetEnumerator() | ForEach-Object { "$($_.Key)=$([uri]::EscapeDataString([string]$_.Value))" }) -join "&"
    $url = "$Base/api/v4$Path"
    if ($qs) { $url = "$url`?$qs" }
    return Invoke-RestMethod -Headers $Headers -Uri $url -Method Get
}

# brain_write.py was purged — write via brain_lib (same pattern as crawl_jira/confluence)
function Write-Node($id, $type, $title, $tier, $uri, $parent, $tags, $content) {
    $tagList = if ($tags) { "['" + (($tags | ForEach-Object { $_ -replace "'", "''" }) -join "','") + "']" } else { "None" }
    $contentEsc = if ($content) { $content -replace '\\', '\\\\' -replace "'", "''" } else { $null }
    & $Py -c @"
from brain_lib import write_node
write_node(r'''$id''', type=r'''$type''', source='gitlab', title=r'''$title''', tier=r'''$tier''', uri=$(if($uri){"r'''$uri'''"}else{"None"}), parent_id=$(if($parent){"r'''$parent'''"}else{"None"}), tags=$tagList, content=$(if($contentEsc){"r'''$contentEsc'''"}else{"None"}))
"@
}

function Add-Edge($src, $rel, $dst) {
    & $Py -c "from brain_lib import write_edge; write_edge(r'''$src''', r'''$rel''', r'''$dst''')"
}
# alias used by older body
function Write-Edge($src, $rel, $dst) { Add-Edge $src $rel $dst }

Write-Host "GitLab crawl mode=$Mode base=$Base" -ForegroundColor Cyan

if ($Mode -in @("topo", "auto")) {
    $groups = @()
    if ($GroupId) {
        $groups = @(Invoke-GL "/groups/$GroupId")
    } else {
        $page = 1
        do {
            $batch = Invoke-GL "/groups" @{ per_page = 50; page = $page; top_level_only = $false }
            $groups += $batch
            $page++
        } while ($batch.Count -eq 50 -and $page -lt 20)
    }
    foreach ($g in $groups) {
        $gid = "gitlab:group:$($g.id)"
        $type = if ($g.parent_id) { "Subgroup" } else { "Group" }
        Write-Node $gid $type $g.full_path "T2" $g.web_url $(if ($g.parent_id) { "gitlab:group:$($g.parent_id)" } else { $null }) @("gitlab") $null
        if ($g.parent_id) { Add-Edge "gitlab:group:$($g.parent_id)" "PARENT_OF" $gid }
    }
    # projects
    $page = 1
    $count = 0
    do {
        $proj = Invoke-GL "/projects" @{ per_page = 50; page = $page; membership = $true; simple = $true }
        foreach ($p in $proj) {
            if ($count -ge $MaxProjects) { break }
            $pid = "gitlab:project:$($p.id)"
            Write-Node $pid "Project" $p.path_with_namespace "T2" $p.web_url $(if ($p.namespace.id) { "gitlab:group:$($p.namespace.id)" } else { $null }) @("gitlab") $null
            if ($p.namespace.id) { Add-Edge "gitlab:group:$($p.namespace.id)" "CONTAINS" $pid }
            $count++
        }
        $page++
    } while ($proj.Count -eq 50 -and $count -lt $MaxProjects -and $page -lt 30)
    Write-Host "topo: wrote groups/projects (projects capped at $MaxProjects)" 
}

if ($Mode -in @("deep", "auto") -and $ProjectId -gt 0) {
    $p = Invoke-GL "/projects/$ProjectId"
    $pid = "gitlab:project:$($p.id)"
    Write-Node $pid "Project" $p.path_with_namespace "T2" $p.web_url $null @("gitlab") ($p.description)
    # MRs
    $mrs = Invoke-GL "/projects/$ProjectId/merge_requests" @{ state = "all"; per_page = 30 }
    foreach ($mr in $mrs) {
        $mid = "gitlab:mr:$ProjectId`:$($mr.iid)"
        Write-Node $mid "MergeRequest" $mr.title "T2" $mr.web_url $pid @("gitlab") $mr.description
        Add-Edge $pid "HAS_MR" $mid
        $notes = Invoke-GL "/projects/$ProjectId/merge_requests/$($mr.iid)/notes" @{ per_page = 20 }
        foreach ($n in $notes) {
            if ($n.system) { continue }
            $cid = "gitlab:mr_comment:$ProjectId`:$($mr.iid):$($n.id)"
            Write-Node $cid "MRComment" ("comment by " + $n.author.username) "T3" $null $mid @("gitlab") $n.body
            Add-Edge $mid "HAS_COMMENT" $cid
        }
    }
    Write-Host "deep: project $ProjectId MRs+comments"
}

& $Py $Snap
Write-Host "GitLab crawl done." -ForegroundColor Green
