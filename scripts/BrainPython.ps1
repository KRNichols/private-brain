# Shared: resolve Private Brain Python (Windows venv\Scripts OR Unix venv/bin).
# Dot-source: . "$PSScriptRoot\BrainPython.ps1"

function Get-BrainRootPath {
    if ($env:PRIVATE_BRAIN_HOME) { return $env:PRIVATE_BRAIN_HOME }
    if ($env:PRIVATE_BRAIN_ROOT) { return $env:PRIVATE_BRAIN_ROOT }
    if ($env:CODEX_HOME) { return (Join-Path $env:CODEX_HOME "private-brain") }
    $home = if ($env:USERPROFILE) { $env:USERPROFILE } else { $env:HOME }
    return (Join-Path $home ".codex/private-brain")
}

function Get-BrainPython {
    param([string]$BrainRoot = (Get-BrainRootPath))
    $candidates = @(
        (Join-Path $BrainRoot "venv/Scripts/python.exe"),
        (Join-Path $BrainRoot "venv/bin/python3"),
        (Join-Path $BrainRoot "venv/bin/python")
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return (Resolve-Path -LiteralPath $c).Path }
    }
    foreach ($name in @("python3", "python", "py")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    return "python3"
}

function Test-BrainVenv {
    param([string]$BrainRoot)
    $py = Get-BrainPython -BrainRoot $BrainRoot
    return ($py -like "*venv*")
}
