#Requires -Version 5.1
<#
.SYNOPSIS
  ONE Day-1 script (Windows / Corporate) — Codex sideload only.
  Order (zero-fail): config → map → SETUP → sessions → heal → mission → crawl → quarantine
  See MISSION_MONDAY.md and README Monday morning TODO.
#>
param(
    [string]$Route = "",
    [string]$Program = "",
    [string]$Hosts = "",
    [string]$Gitlab = $env:PB_GITLAB_URL,
    [string]$Jira = $env:PB_JIRA_URL,
    [string]$Confluence = $env:PB_CONFLUENCE_URL,
    [switch]$Yes,
    [switch]$CrawlOnly,
    [switch]$SkipCrawl
)

$ErrorActionPreference = "Continue"
$ScriptDir = $PSScriptRoot
$Brain = if ($env:PRIVATE_BRAIN_HOME) { $env:PRIVATE_BRAIN_HOME } else { Join-Path $env:USERPROFILE ".codex\private-brain" }
$Codex = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$env:PRIVATE_BRAIN_HOME = $Brain
$env:CODEX_HOME = $Codex
$env:PB_ENTERPRISE = "1"
$env:PYGAME_HIDE_SUPPORT_PROMPT = "1"
$env:PB_KIT_ROOT = (Split-Path -Parent $ScriptDir)

# Windows venv FIRST
function Find-Py {
    $c = @(
        (Join-Path $Brain "venv\Scripts\python.exe"),
        (Join-Path $Brain "venv\Scripts\python"),
        (Get-Command py -EA SilentlyContinue | Select-Object -Expand Source),
        (Get-Command python -EA SilentlyContinue | Select-Object -Expand Source)
    )
    foreach ($x in $c) { if ($x -and (Test-Path $x)) { return $x } }
    return $null
}

$py = Find-Py
if (-not $py) { Write-Error "Python 3.10+ required (venv\Scripts\python.exe after SETUP.ps1)"; exit 1 }

Write-Host "=============================================="
Write-Host " Private Brain — DAY1 Windows (Corporate)"
Write-Host "=============================================="
Write-Host " PYTHON=$py"
Write-Host " BRAIN=$Brain"

function Get-BeastMode {
    $bm = Join-Path $env:USERPROFILE "bin\beastMode.cmd"
    if (-not (Test-Path $bm)) { $bm = Join-Path $Brain "scripts\beastMode.cmd" }
    return $bm
}

if (-not $CrawlOnly) {
    Write-Host "==> [0/7] Config-of-config (scripted board)"
    $coc = Join-Path $ScriptDir "config_of_config.py"
    if (-not (Test-Path $coc)) { $coc = Join-Path $Brain "scripts\config_of_config.py" }
    $suggest = ""
    if (Test-Path $coc) {
        $out = & $py $coc 2>&1 | Out-String
        Write-Host ($out -split "`n" | Select-Object -Last 25)
        if ($out -match "COC_ROUTE=(\w+)") { $suggest = $Matches[1] }
        $env:PB_CONFIG_OF_CONFIG_JSON = Join-Path $Brain ".brain\state\config_of_config.json"
    }

    Write-Host "==> [1/7] Intelligent Day-1 map (Interview A Corporate Library · B sources · C AWS optional)"
    $d1 = Join-Path $ScriptDir "day1_first_start.py"
    if (-not (Test-Path $d1)) { $d1 = Join-Path $Brain "scripts\day1_first_start.py" }
    $args = @()
    if ($Yes) { $args += "--yes" }
    if ($Route) { $args += @("--route", $Route) }
    elseif ($suggest) { $args += @("--route", $suggest) }
    if ($Program) { $args += @("--program", $Program) }
    if ($Hosts) { $args += @("--hosts", $Hosts) }
    & $py $d1 @args

    foreach ($e in @(
        (Join-Path $Brain "day1.env.ps1"),
        (Join-Path $env:PB_KIT_ROOT "day1.env.ps1")
    )) {
        if (Test-Path $e) { . $e; break }
    }
    $env:PB_ENTERPRISE = "1"
    $py = Find-Py  # re-resolve after SETUP may create venv

    Write-Host "==> [2/7] SETUP if needed"
    $need = -not (Test-Path (Join-Path $Brain "scripts\orchestrate.py"))
    if (-not (Test-Path (Join-Path $Codex "hooks.json"))) { $need = $true }
    if (-not (Test-Path (Join-Path $Brain "venv\Scripts\python.exe"))) { $need = $true }
    if ($need) {
        $setup = Join-Path $env:PB_KIT_ROOT "SETUP.ps1"
        $install = Join-Path $env:PB_KIT_ROOT "Install-PrivateBrain.ps1"
        if (Test-Path $install) {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $install -SourceRoot $env:PB_KIT_ROOT
        } elseif (Test-Path $setup) {
            & powershell -NoProfile -ExecutionPolicy Bypass -File $setup
        }
        $py = Find-Py
    }

    $bm = Get-BeastMode
    Write-Host "==> [3/7] sessions first (local gold — no AppGate)"
    $env:PYTHONPATH = "$(Join-Path $Brain 'scripts');$Brain"
    $sd = Join-Path $Brain "scripts\smart_discover.py"
    if (Test-Path $sd) {
        & $py -c "from smart_discover import run_discover_ingest; import json; print(json.dumps(run_discover_ingest(max_files=400, force=False, agent_id='day1-sessions-win'), default=str)[:600])"
    }

    Write-Host "==> [4/7] enterprise heal + doctor"
    & $bm --enterprise --heal
    if ($LASTEXITCODE -ne 0) {
        Write-Host "heal non-zero — retry" -ForegroundColor Yellow
        & $bm --enterprise --heal
    }
    & $bm --enterprise --doctor
    if ($LASTEXITCODE -ne 0) {
        Write-Host "doctor FAIL — heal again" -ForegroundColor Yellow
        & $bm --enterprise --heal
        & $bm --enterprise --doctor
    }

    Write-Host "==> [5/7] Monday mission zero-fail gates"
    $mm = Join-Path $Brain "scripts\mission_monday.py"
    if (Test-Path $mm) {
        & $py $mm
    } else {
        & $bm --mission
    }
} else {
    $bm = Get-BeastMode
    $py = Find-Py
}

if (-not $SkipCrawl -and ($Gitlab -or $Jira -or $Confluence)) {
    Write-Host "==> [6/7] Polite multi-agent crawl (AppGate must be up)"
    $env:PYTHONPATH = "$(Join-Path $Brain 'scripts');$Brain"
    $cargs = @("--deep", "--agents", "6")
    if ($Gitlab) { $cargs += @("--gitlab", $Gitlab) }
    if ($Jira) { $cargs += @("--jira", $Jira) }
    if ($Confluence) { $cargs += @("--confluence", $Confluence) }
    $swarm = Join-Path $Brain "scripts\internal_crawl_swarm.py"
    if (Test-Path $swarm) {
        & $py $swarm @cargs
        & $py -c "from vector_manager import reindex_all; print(reindex_all())" 2>$null
    }
} else {
    Write-Host "==> [6/7] skip crawl (pass -Gitlab/-Jira/-Confluence or set env)"
}

Write-Host "==> [7/7] quarantine + mission + doctor"
$bm = Get-BeastMode
& $bm --enterprise --quarantine-public 2>$null
& $bm --mission 2>$null
& $bm --enterprise --doctor

Write-Host " DAY1 COMPLETE — Windows Codex sideload ready" -ForegroundColor Green
Write-Host " Next: beastMode --enterprise   (opens Codex)"
Write-Host " Gates: beastMode --mission"
Write-Host " Docs:  README Monday morning TODO · MISSION_MONDAY.md"
exit 0
