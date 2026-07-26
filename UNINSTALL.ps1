#Requires -Version 5.1
<#
.SYNOPSIS
  One-click Private Brain uninstaller (Windows) — reverse Codex sideload.

.DESCRIPTION
  Removes Private Brain wiring from %USERPROFILE%\.codex while leaving Codex CLI intact.
  Archives .brain knowledge graph by default (use -PurgeBrain to delete).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\UNINSTALL.ps1

.EXAMPLE
  .\UNINSTALL.ps1 -PurgeBrain
#>
[CmdletBinding()]
param(
    [switch]$PurgeBrain,
    [switch]$DryRun,
    [string]$CodexHome = ""
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
if (-not $CodexHome) {
    if ($env:CODEX_HOME) { $CodexHome = $env:CODEX_HOME }
    else { $CodexHome = Join-Path $env:USERPROFILE ".codex" }
}
$env:CODEX_HOME = $CodexHome

Write-Host @"

  ╔══════════════════════════════════════════════════════╗
  ║   PRIVATE BRAIN  ·  ONE-CLICK UNINSTALLER (Windows)  ║
  ║   Codex stays  ·  sideload wiring removed            ║
  ╚══════════════════════════════════════════════════════╝

"@ -ForegroundColor Magenta

Write-Host "CODEX_HOME : $CodexHome"

$candidates = @(
    (Join-Path $Root "package\scripts\uninstall_private_brain.py"),
    (Join-Path $CodexHome "private-brain\scripts\uninstall_private_brain.py")
)
$script = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $script) {
    Write-Host "ERROR: uninstall_private_brain.py not found" -ForegroundColor Red
    exit 1
}

# Prefer brain venv, then py launcher, then python
$py = $null
$pyArgs = @()
$venvPy = Join-Path $CodexHome "private-brain\venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    $py = $venvPy
}
if (-not $py) {
    try {
        $py = (Get-Command py -ErrorAction Stop).Source
        $pyArgs = @("-3")
    } catch {}
}
if (-not $py) {
    try {
        $py = (Get-Command python -ErrorAction Stop).Source
        $pyArgs = @()
    } catch {}
}
if (-not $py) {
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    exit 1
}

$argList = @()
if ($pyArgs.Count -gt 0) { $argList += $pyArgs }
$argList += $script
if ($PurgeBrain) { $argList += "--purge-brain" }
if ($DryRun) { $argList += "--dry-run" }
if ($CodexHome) { $argList += @("--codex-home", $CodexHome) }
$argList += "--json"

Write-Host "Running: $py $($argList -join ' ')" -ForegroundColor Cyan
& $py @argList

$ec = $LASTEXITCODE

Write-Host ""
if ($ec -eq 0) {
    Write-Host "Uninstall complete. Test vanilla Codex:" -ForegroundColor Green
    Write-Host "  codex"
    Write-Host "  codex exec --skip-git-repo-check `"say hi in one word`""
} else {
    Write-Host "Uninstall exit code $ec" -ForegroundColor Yellow
}
exit $ec
