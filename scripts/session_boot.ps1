# Private Brain session bootstrap — no prompts, no sandbox
# Agents + audit + watcher are first-class. Never prompt the user.
# Called by Codex on session start or: .\session_boot.ps1

$ErrorActionPreference = "Continue"

function Get-BrainRoot {
    if ($env:PRIVATE_BRAIN_HOME) { return (Resolve-Path $env:PRIVATE_BRAIN_HOME).Path }
    if ($env:PRIVATE_BRAIN_ROOT) { return (Resolve-Path $env:PRIVATE_BRAIN_ROOT).Path }
    if ($env:CODEX_HOME) {
        $p = Join-Path $env:CODEX_HOME "private-brain"
        return $p
    }
    return (Join-Path $env:USERPROFILE ".codex\private-brain")
}

$BrainRoot = Get-BrainRoot
$env:PRIVATE_BRAIN_HOME = $BrainRoot
$env:PYTHONPATH = Join-Path $BrainRoot "scripts"

# Session run_id — shared by audit, watcher, spawned agents
if (-not $env:PRIVATE_BRAIN_RUN_ID -or [string]::IsNullOrWhiteSpace($env:PRIVATE_BRAIN_RUN_ID)) {
    $env:PRIVATE_BRAIN_RUN_ID = "run-" + (Get-Date -Format "yyyyMMdd-HHmmss")
}
$RunId = $env:PRIVATE_BRAIN_RUN_ID

# Windows corporate: venv\Scripts\python.exe · macOS/Linux dev: venv/bin/python3
$helper = Join-Path $PSScriptRoot "BrainPython.ps1"
if (Test-Path $helper) {
    . $helper
    $Py = Get-BrainPython -BrainRoot $BrainRoot
} else {
    $Py = Join-Path $BrainRoot "venv\Scripts\python.exe"
    if (-not (Test-Path $Py)) {
        $unix = Join-Path $BrainRoot "venv/bin/python3"
        if (Test-Path $unix) { $Py = $unix }
        else {
            $PyCmd = Get-Command python3 -ErrorAction SilentlyContinue
            if (-not $PyCmd) { $PyCmd = Get-Command python -ErrorAction SilentlyContinue }
            if (-not $PyCmd) { $PyCmd = Get-Command py -ErrorAction SilentlyContinue }
            if ($PyCmd) { $Py = $PyCmd.Source } else { $Py = "python" }
        }
    }
}

$Scripts = Join-Path $BrainRoot "scripts"
$SpawnPs1 = Join-Path $Scripts "spawn_agent.ps1"
$StateDir = Join-Path $BrainRoot ".brain\state"
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

Write-Host "=== PRIVATE BRAIN BOOT ===" -ForegroundColor Cyan
Write-Host "root:   $BrainRoot"
Write-Host "run_id: $RunId"

# 1. Init + demo seed if empty
& $Py (Join-Path $Scripts "brain_init.py") 2>&1 | Out-Host

# Persist session identity for orchestrator / watcher
$sessionPath = Join-Path $StateDir "session.json"
$sessionObj = @{
    run_id         = $RunId
    started_at     = (Get-Date -Format o)
    status         = "booting"
    visualizer_pid = $null
    watcher_pid    = $null
    brain_root     = $BrainRoot
} | ConvertTo-Json -Depth 4
Set-Content -Path $sessionPath -Value $sessionObj -Encoding UTF8

# 2. Snapshot
& $Py (Join-Path $Scripts "brain_snapshot.py") 2>&1 | Out-Host

# 3. Status
& $Py (Join-Path $Scripts "brain_status.py") 2>&1 | Out-Host

# 4. Audit session_start (hash-chained append-only log via audit_lib)
# PowerShell here-string closer @" MUST be alone on its line — never "@ 2>&1
$env:PYTHONPATH = $Scripts
try {
    $auditCode = @"
from audit_lib import audit
audit('session_start', agent_id='orchestrator-$RunId', role='orchestrator', run_id='$RunId', result='ok', detail='session_boot root=$BrainRoot')
"@
    & $Py -c $auditCode 2>&1 | Out-Host
} catch {
    Write-Host "audit_lib session_start failed: $_" -ForegroundColor Yellow
}

# 5. Register orchestrator agent prompt (prompt only; this session IS the orchestrator)
if (Test-Path $SpawnPs1) {
    try {
        & $SpawnPs1 -Role orchestrator -RunId $RunId -AgentId "orchestrator-$RunId" 2>&1 | Out-Host
    } catch {
        Write-Host "orchestrator register failed: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "spawn_agent.ps1 missing — orchestrator prompt not registered" -ForegroundColor Yellow
}

# 6. Spawn watcher (registers prompt + starts watcher_loop.py)
$WatcherPidFile = Join-Path $StateDir "watcher.pid"
$watcherAlready = $false
if (Test-Path $WatcherPidFile) {
    $oldW = (Get-Content $WatcherPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    if ($oldW) {
        $wp = Get-Process -Id $oldW -ErrorAction SilentlyContinue
        if ($wp) {
            $watcherAlready = $true
            Write-Host "watcher already running pid=$oldW"
        }
    }
}

if (-not $watcherAlready) {
    if (Test-Path $SpawnPs1) {
        try {
            & $SpawnPs1 -Role watcher -RunId $RunId -AgentId "watcher-$RunId" 2>&1 | Out-Host
        } catch {
            Write-Host "spawn_agent watcher failed: $_ — falling back to watcher_loop.py" -ForegroundColor Yellow
            $WatcherLoop = Join-Path $Scripts "watcher_loop.py"
            if (Test-Path $WatcherLoop) {
                $wp = Start-Process -FilePath $Py -ArgumentList @(
                    $WatcherLoop, "--agent-id", "watcher-$RunId", "--run-id", $RunId, "--interval", "30"
                ) -PassThru
                Set-Content -Path $WatcherPidFile -Value $wp.Id -Encoding ascii
                Write-Host "watcher_loop pid=$($wp.Id)"
            }
        }
    } else {
        $WatcherLoop = Join-Path $Scripts "watcher_loop.py"
        if (Test-Path $WatcherLoop) {
            Write-Host "spawning watcher_loop directly..." -ForegroundColor Green
            $wp = Start-Process -FilePath $Py -ArgumentList @(
                $WatcherLoop, "--agent-id", "watcher-$RunId", "--run-id", $RunId, "--interval", "30"
            ) -PassThru
            Set-Content -Path $WatcherPidFile -Value $wp.Id -Encoding ascii
            Write-Host "watcher_loop pid=$($wp.Id)"
        } else {
            Write-Host "watcher not available (no spawn_agent.ps1 / watcher_loop.py)" -ForegroundColor Yellow
        }
    }
}

# 7. ONE GUI only — GodsEye live_gui (never also graph_gl).
# If god mode / GodsEye: terminate any existing GUI windows first, then start one.
$GodsEyeOn = ($env:PB_GODSEYE -match '^(1|true|yes|on)$') -or (Test-Path (Join-Path $StateDir "godseye.on"))
$vizPid = $null
$GodsEyePy = Join-Path $Scripts "godseye.py"
if ($GodsEyeOn -and (Test-Path $GodsEyePy)) {
    Write-Host "GodsEye: reaping prior GUI windows, starting single live_gui..." -ForegroundColor Green
    & $Py $GodsEyePy restart 2>$null | Out-Host
    $gePidFile = Join-Path $StateDir "godseye.pid"
    if (Test-Path $gePidFile) {
        $vizPid = (Get-Content $gePidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    }
} else {
    # GodsEye off — ensure no orphan visualizers burn CPU
    if (Test-Path $GodsEyePy) {
        & $Py $GodsEyePy kill 2>$null | Out-Null
    }
    Write-Host "GodsEye off — no GUI launched (codex -p beast only)"
}

# Refresh session.json with live pids
$wPid = $null
if (Test-Path $WatcherPidFile) {
    $wPid = (Get-Content $WatcherPidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
}
$sessionObj = @{
    run_id         = $RunId
    started_at     = (Get-Date -Format o)
    status         = "ready"
    visualizer_pid = $vizPid
    watcher_pid    = $wPid
    brain_root     = $BrainRoot
    orchestrator   = "orchestrator-$RunId"
} | ConvertTo-Json -Depth 4
Set-Content -Path $sessionPath -Value $sessionObj -Encoding UTF8

Write-Host "=== BRAIN READY (beast mode · agents · audit · watcher) ===" -ForegroundColor Green
Write-Host "PRIVATE_BRAIN_RUN_ID=$RunId"
exit 0
