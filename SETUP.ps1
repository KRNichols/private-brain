#Requires -Version 5.1
<#
.SYNOPSIS
  One-click Private Brain sideload into existing Codex CLI.
.DESCRIPTION
  Double-click SETUP.cmd (Windows) or SETUP.command (Mac) or run this script.
  End users never run Python. Only beastMode / SETUP / UNINSTALL.

  Thin wrapper around Install-PrivateBrain.ps1 (modern sideload).
  Primary UX after install: beastMode [flags] — not session_boot / pb-codex.
#>

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }

Write-Host "You never run Python. Only beastMode / SETUP / UNINSTALL." -ForegroundColor DarkGray

$Installer = Join-Path $Root "Install-PrivateBrain.ps1"
if (-not (Test-Path $Installer)) {
    Write-Host "ERROR: Install-PrivateBrain.ps1 missing next to SETUP.ps1" -ForegroundColor Red
    exit 1
}

$Model = "gpt-5.1"
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "" }

if ($CodexHome) {
    & $Installer -Model $Model -SourceRoot $Root -CodexHome $CodexHome
} else {
    & $Installer -Model $Model -SourceRoot $Root
}

$ec = $LASTEXITCODE
if ($null -eq $ec) { $ec = 0 }
exit $ec
