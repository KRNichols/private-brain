#Requires -Version 5.1
<#
.SYNOPSIS
  Windows water-pipe start - conversation once, then organism builds everything.

  1) Install sideload if needed
  2) Conversational map (packages · code · jira · confluence · AWS)
  3) organism.py: sessions -> GodsEye -> local RAG -> max agents -> AWS phase
  4) Open Codex (beastMode always-on)
#>
param(
    [string]$Route = "",
    [string]$Program = "",
    [string]$Hosts = "",
    [string]$Classification = "",
    [string]$IndexUrl = "",
    [string]$TrustedHost = "",
    [string]$IngestUrl = "",
    [switch]$Yes,
    [switch]$NoSetup,
    [switch]$NoGodsEye
)

$ErrorActionPreference = "Continue"
# Layout: <os>/README.md · DIAGRAM.md · tools/{install,engine,...}
# This script lives at tools/install/START.ps1
$InstallDir = $PSScriptRoot
if (-not $InstallDir) { $InstallDir = (Get-Location).Path }
$ToolsDir = Split-Path -Parent $InstallDir
$Root = Split-Path -Parent $ToolsDir
if (-not (Test-Path (Join-Path $ToolsDir "engine"))) {
    # fallback: flat kit (legacy) - install dir is OS root
    if (Test-Path (Join-Path $InstallDir "package")) {
        $Root = $InstallDir
        $ToolsDir = $InstallDir
        $Engine = Join-Path $InstallDir "package"
    } else {
        $Engine = Join-Path $InstallDir "package"
    }
} else {
    $Engine = Join-Path $ToolsDir "engine"
}
$env:PB_KIT_ROOT = $Root
$env:PB_ENGINE = $Engine
$env:PB_ENTERPRISE = "1"
$env:PB_GODSEYE = if ($NoGodsEye) { "0" } else { "1" }
$env:PB_AWS_REGION = if ($env:PB_AWS_REGION) { $env:PB_AWS_REGION } else { "gov-region-1" }
$env:PB_SWARM_AGENTS = if ($env:PB_SWARM_AGENTS) { $env:PB_SWARM_AGENTS } else { "auto" }
$env:PB_MAX_AGENTS = if ($env:PB_MAX_AGENTS) { $env:PB_MAX_AGENTS } else { "auto" }
$env:PB_ORGANISM_INTERVIEW = "1"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
$BrainHome = if ($env:PRIVATE_BRAIN_HOME) { $env:PRIVATE_BRAIN_HOME } else { Join-Path $CodexHome "private-brain" }
$env:CODEX_HOME = $CodexHome
$env:PRIVATE_BRAIN_HOME = $BrainHome

Write-Host "=============================================="
Write-Host " Private Brain - WATER PIPE (Windows)"
Write-Host " Same product as macOS. Open Codex after this."
Write-Host " Golden: tools\install\golden_join.json when Corporate provides it"
Write-Host "=============================================="
Write-Host " Kit:    $Root"
Write-Host " Engine: $Engine"
Write-Host " Codex:  $CodexHome"
Write-Host ""

function Find-Python {
    $candidates = @(
        (Join-Path $BrainHome "venv\Scripts\python.exe"),
        (Get-Command py -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source),
        (Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { return $c }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "ERROR: Python 3.10+ required" -ForegroundColor Red
    exit 1
}

# SETUP if missing
$needSetup = -not (Test-Path (Join-Path $BrainHome "scripts\organism.py")) -and -not (Test-Path (Join-Path $BrainHome "scripts\orchestrate.py"))
if (-not (Test-Path (Join-Path $CodexHome "hooks.json"))) { $needSetup = $true }
if ($needSetup -and -not $NoSetup) {
    Write-Host "==> Installing sideload (SETUP)"
    $setup = Join-Path $InstallDir "SETUP.ps1"
    if (-not (Test-Path $setup)) { $setup = Join-Path $Root "SETUP.ps1" }
    $install = Join-Path $InstallDir "Install-PrivateBrain.ps1"
    if (-not (Test-Path $install)) { $install = Join-Path $Root "Install-PrivateBrain.ps1" }
    # Installers expect kit root with package/ - engine is the package
    $env:PB_SOURCE_ENGINE = $Engine
    if (Test-Path $install) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $install -SourceRoot $Engine
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
            Write-Host "ERROR: Install-PrivateBrain failed (exit $LASTEXITCODE) - fail closed" -ForegroundColor Red
            exit $LASTEXITCODE
        }
    } elseif (Test-Path $setup) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $setup
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) {
            Write-Host "ERROR: SETUP failed (exit $LASTEXITCODE) - fail closed" -ForegroundColor Red
            exit $LASTEXITCODE
        }
    }
    # Fail closed: hooks + organism must exist
    if (-not (Test-Path (Join-Path $CodexHome "hooks.json"))) {
        Write-Host "ERROR: hooks.json missing after install - fail closed" -ForegroundColor Red
        exit 2
    }
    if (-not (Test-Path (Join-Path $BrainHome "scripts\organism.py")) -and -not (Test-Path (Join-Path $Engine "scripts\organism.py"))) {
        Write-Host "ERROR: organism.py missing after install - fail closed" -ForegroundColor Red
        exit 2
    }
    $py = Find-Python
}

# Prefer live brain scripts after install
$org = Join-Path $BrainHome "scripts\organism.py"
if (-not (Test-Path $org)) {
    $org = Join-Path $Engine "scripts\organism.py"
}
$day1 = Join-Path $BrainHome "scripts\day1_first_start.py"
if (-not (Test-Path $day1)) {
    $day1 = Join-Path $Engine "scripts\day1_first_start.py"
}

$env:PYTHONPATH = "$(Join-Path $BrainHome 'scripts');$BrainHome;$env:PYTHONPATH"
$env:PYGAME_HIDE_SUPPORT_PROMPT = "1"

# Load prior day1 env if any
foreach ($envf in @(
    (Join-Path $BrainHome "day1.env.ps1"),
    (Join-Path $Root "day1.env.ps1")
)) {
    if (Test-Path $envf) { . $envf; break }
}
$env:PB_ENTERPRISE = "1"

# Co-worker magic: golden_join next to START (tools/install) or brain state
$join = Join-Path $InstallDir "golden_join.json"
if (-not (Test-Path $join)) { $join = Join-Path $Root "golden_join.json" }
if (-not (Test-Path $join)) {
    $join = Join-Path $BrainHome ".brain\state\golden_join.json"
}
if (Test-Path $join) {
    Write-Host "==> Co-worker join kit found: $join"
    Write-Host "    Applying shared Corporate map (no re-interview). Your sessions ingest next."
    $env:PB_NONINTERACTIVE = "1"
    if (Test-Path $day1) {
        & $py $day1 --yes --join $join
    }
}

Write-Host "==> ORGANISM water-pipe (sessions · golden · GodsEye · swarm · AWS)"
if (Test-Path $org) {
    $oArgs = @()
    if ($Yes) {
        $env:PB_NONINTERACTIVE = "1"
        if ($Route) { $env:PB_ROUTE = $Route }
    }
    if ($NoGodsEye) { $oArgs += "--no-godseye" }
    if ($Yes -and $Route -and -not (Test-Path $join)) {
        $dArgs = @("--yes")
        if ($Route) { $dArgs += @("--route", $Route) }
        if ($Program) { $dArgs += @("--program", $Program) }
        if ($Hosts) { $dArgs += @("--hosts", $Hosts) }
        if ($IndexUrl) { $dArgs += @("--index-url", $IndexUrl) }
        if ($TrustedHost) { $dArgs += @("--trusted-host", $TrustedHost) }
        if (Test-Path $day1) { & $py $day1 @dArgs }
    }
    & $py $org @oArgs
    $orgRc = $LASTEXITCODE
    if ($orgRc -ne 0 -and $null -ne $orgRc) {
        Write-Host "NOTE: organism exit $orgRc (not fully ALIVE yet is OK on Day-1 - hooks/sideload still READY)" -ForegroundColor Yellow
    }
} else {
    Write-Host "organism.py missing - run SETUP from complete kit" -ForegroundColor Red
    exit 1
}

# Put beastMode on path if present (optional power tool)
$bm = Join-Path $env:USERPROFILE "bin\beastMode.cmd"
if (-not (Test-Path $bm)) { $bm = Join-Path $BrainHome "scripts\beastMode.cmd" }
if (-not (Test-Path $bm)) { $bm = Join-Path $Engine "scripts\beastMode.cmd" }

Write-Host ""
Write-Host "=============================================="
Write-Host " READY - water is flowing (windows ≡ mac)"
Write-Host " Daily:  open Codex and talk (hooks sideloaded)"
Write-Host " Pause:  say 'stop beast mode' in chat"
Write-Host " Reopen: beast turns back on automatically"
Write-Host " HUD:    say 'show GodsEye' in Codex"
Write-Host " Golden: drop golden_join.json here when Corporate provides it"
Write-Host " Shell beastMode is optional power tool only"
Write-Host "=============================================="

# Optional: open Codex once after install (hooks work without this launcher)
$env:PB_ORGANISM_LIGHT = "1"
if ($env:PB_NO_OPEN_CODEX -eq "1") {
    Write-Host "PB_NO_OPEN_CODEX=1 - not launching Codex"
    exit 0
}
if (Test-Path $bm) {
    & $bm --enterprise
} else {
    Write-Host "Open Codex Desktop / ChatGPT Codex now - Private Brain hooks are already wired."
}
