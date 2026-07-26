# Confluence crawl → filesystem brain.
# Env: CONFLUENCE_URL, CONFLUENCE_EMAIL, CONFLUENCE_API_TOKEN
[CmdletBinding()]
param(
    [ValidateSet("topo", "deep", "auto")]
    [string]$Mode = "auto",
    [string]$SpaceKey = "",
    [int]$MaxPages = 100
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

if (-not $env:CONFLUENCE_API_TOKEN) { throw "CONFLUENCE_API_TOKEN not set" }
if (-not $env:CONFLUENCE_EMAIL) { throw "CONFLUENCE_EMAIL not set" }
$Base = $env:CONFLUENCE_URL.TrimEnd("/")
$pair = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($env:CONFLUENCE_EMAIL):$($env:CONFLUENCE_API_TOKEN)"))
$Headers = @{ Authorization = "Basic $pair"; Accept = "application/json" }

function CF-Get($Path, $Query = @{}) {
    $qs = ($Query.GetEnumerator() | ForEach-Object { "$($_.Key)=$([uri]::EscapeDataString([string]$_.Value))" }) -join "&"
    $url = "$Base/wiki/rest/api$Path"
    if ($Path.StartsWith("/api/")) { $url = "$Base$Path" }  # allow absolute-style
    if ($qs) { $url = "$url`?$qs" }
    # Standard Confluence Cloud:
    $url = "$Base/wiki/rest/api$Path"
    if ($qs) { $url = "$url`?$qs" }
    Invoke-RestMethod -Headers $Headers -Uri $url -Method Get
}

function Add-Node($id, $type, $title, $tier, $uri, $parent, $content) {
    $contentEsc = if ($content) { $content -replace '\\', '\\\\' -replace "'", "''" } else { $null }
    & $Py -c @"
from brain_lib import write_node
write_node(r'''$id''', type=r'''$type''', source='confluence', title=r'''$title''', tier=r'''$tier''', uri=$(if($uri){"r'''$uri'''"}else{"None"}), parent_id=$(if($parent){"r'''$parent'''"}else{"None"}), content=$(if($contentEsc){"r'''$contentEsc'''"}else{"None"}))
"@
}
function Add-Edge($src, $rel, $dst) {
    & $Py -c "from brain_lib import write_edge; write_edge(r'''$src''', r'''$rel''', r'''$dst''')"
}

Write-Host "Confluence crawl mode=$Mode" -ForegroundColor Cyan

if ($Mode -in @("topo", "auto")) {
    $start = 0
    do {
        $spaces = CF-Get "/space" @{ limit = 50; start = $start }
        foreach ($s in $spaces.results) {
            $id = "confluence:space:$($s.key)"
            Add-Node $id "Space" $s.name "T0" "$Base/wiki/spaces/$($s.key)" $null $null
        }
        $start += 50
    } while ($spaces.size -eq 50 -and $start -lt 200)
}

if ($Mode -in @("deep", "auto")) {
    $cql = if ($SpaceKey) { "space=$SpaceKey order by lastmodified desc" } else { "type=page order by lastmodified desc" }
    $start = 0
    $got = 0
    while ($got -lt $MaxPages) {
        $resp = CF-Get "/content/search" @{ cql = $cql; limit = 25; start = $start; expand = "body.storage,space" }
        foreach ($page in $resp.results) {
            $id = "confluence:page:$($page.id)"
            $parent = "confluence:space:$($page.space.key)"
            $body = $page.body.storage.value
            # strip crude HTML tags for brain text
            $text = [regex]::Replace([string]$body, "<[^>]+>", " ")
            if ($text.Length -gt 12000) { $text = $text.Substring(0, 12000) }
            Add-Node $id "Page" $page.title "T0" "$Base/wiki$($page._links.webui)" $parent $text
            Add-Edge $parent "CONTAINS" $id
            $got++
            if ($got -ge $MaxPages) { break }
        }
        if (-not $resp.results -or $resp.results.Count -lt 25) { break }
        $start += 25
    }
    Write-Host "pages written: $got"
}

& $Py (Join-Path $BrainRoot "scripts\brain_snapshot.py")
Write-Host "Confluence crawl done." -ForegroundColor Green
