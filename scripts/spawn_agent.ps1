# Materialize a role-specific system prompt for a spawned agent and register it.
# Usage:
#   .\spawn_agent.ps1 -Role watcher -RunId $runId
#   .\spawn_agent.ps1 -Role gitlab-topo -RunId $runId -ScopeJson '{"max_projects":50}'

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet(
        "orchestrator", "watcher", "auditor",
        "gitlab-topo", "gitlab-deep",
        "jira-topo", "jira-deep",
        "confluence-topo", "confluence-deep",
        "graph-writer", "retriever", "visualizer"
    )]
    [string]$Role,

    [string]$RunId = "",
    [string]$AgentId = "",
    [string]$ScopeJson = "{}",
    [switch]$StartWatcherLoop
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
$env:PRIVATE_BRAIN_HOME = $BrainRoot

if (-not $RunId) {
    $RunId = Get-Date -Format "yyyyMMdd-HHmmss"
}
if (-not $AgentId) {
    $AgentId = "$Role-$RunId"
}

$agentsDir = Join-Path $BrainRoot "agents"
$preamble = Join-Path $agentsDir "_shared_preamble.md"
$roleFile = Join-Path $agentsDir "$Role.md"
if (-not (Test-Path $roleFile)) { throw "Missing role prompt: $roleFile" }

$outDir = Join-Path $BrainRoot ".brain\prompts\active"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outPrompt = Join-Path $outDir "$AgentId.md"

$shared = if (Test-Path $preamble) { Get-Content -Raw $preamble } else { "" }
$roleBody = Get-Content -Raw $roleFile
$header = @"
# SPAWNED AGENT INSTANCE
- agent_id: $AgentId
- role: $Role
- run_id: $RunId
- scope_json: $ScopeJson
- spawned_at: $(Get-Date -Format o)
- air_gapped: true
- audit_required: true

"@
Set-Content -Path $outPrompt -Value ($header + "`n" + $shared + "`n`n" + $roleBody) -Encoding UTF8

# register
$regDir = Join-Path $BrainRoot ".brain\state\agents"
New-Item -ItemType Directory -Force -Path $regDir | Out-Null
$reg = @{
    agent_id = $AgentId
    role = $Role
    run_id = $RunId
    scope = (ConvertFrom-Json $ScopeJson)
    prompt_path = $outPrompt
    status = "spawned"
    spawned_at = (Get-Date -Format o)
} | ConvertTo-Json -Depth 6
Set-Content -Path (Join-Path $regDir "$AgentId.json") -Value $reg -Encoding UTF8

$env:PYTHONPATH = Join-Path $BrainRoot "scripts"
& $Py -c @"
from audit_lib import audit
audit('agent_spawn', agent_id=r'''$AgentId''', role=r'''$Role''', run_id=r'''$RunId''', object_id=r'''$Role''', result='ok', detail=r'''prompt=$outPrompt''')
"@ | Out-Host

Write-Host "SPAWNED $AgentId" -ForegroundColor Green
Write-Host "PROMPT  $outPrompt"

# Actually launch workers (not register-only). Watcher + crawl/graph roles get a process.
$workerPid = $null
$logsDir = Join-Path $BrainRoot ".brain\logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null

if ($Role -eq "watcher" -or $StartWatcherLoop) {
    $pidFile = Join-Path $BrainRoot ".brain\state\watcher.pid"
    $p = Start-Process -FilePath $Py -ArgumentList @(
        (Join-Path $BrainRoot "scripts\watcher_loop.py"),
        "--agent-id", $AgentId,
        "--run-id", $RunId,
        "--interval", "30"
    ) -PassThru -WindowStyle Hidden
    Set-Content -Path $pidFile -Value $p.Id -Encoding ascii
    $workerPid = $p.Id
    Write-Host "watcher_loop pid=$($p.Id)"
} elseif ($Role -in @(
    "gitlab-topo", "gitlab-deep",
    "jira-topo", "jira-deep",
    "confluence-topo", "confluence-deep",
    "graph-writer", "retriever", "auditor", "visualizer"
)) {
    $workerPy = Join-Path $BrainRoot "scripts\agent_role_worker.py"
    if (-not (Test-Path $workerPy)) {
        # Fallback: lightweight inline worker that audits heartbeat + optional scope URL crawl
        $workerPy = Join-Path $BrainRoot "scripts\agent_swarm.py"
    }
    $outLog = Join-Path $logsDir "$AgentId.out.log"
    $argList = @()
    if (Test-Path (Join-Path $BrainRoot "scripts\agent_role_worker.py")) {
        $argList = @(
            (Join-Path $BrainRoot "scripts\agent_role_worker.py"),
            "--role", $Role,
            "--agent-id", $AgentId,
            "--run-id", $RunId,
            "--scope-json", $ScopeJson
        )
    } else {
        # swarm single-slice fallback
        $argList = @(
            (Join-Path $BrainRoot "scripts\agent_swarm.py"),
            "sweep",
            "--prompt", "role=$Role agent=$AgentId scope=$ScopeJson",
            "--agents", "1"
        )
    }
    $p = Start-Process -FilePath $Py -ArgumentList $argList `
        -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $outLog -RedirectStandardError $outLog
    $workerPid = $p.Id
    $regPath = Join-Path $regDir "$AgentId.json"
    try {
        $regObj = Get-Content -Raw $regPath | ConvertFrom-Json
        $regObj | Add-Member -NotePropertyName pid -NotePropertyValue $p.Id -Force
        $regObj | Add-Member -NotePropertyName status -NotePropertyValue "running" -Force
        $regObj | ConvertTo-Json -Depth 6 | Set-Content -Path $regPath -Encoding UTF8
    } catch {}
    Write-Host "WORKER $AgentId pid=$($p.Id) log=$outLog" -ForegroundColor Green
}

# stdout machine-readable for orchestrator
[pscustomobject]@{
    agent_id = $AgentId
    role = $Role
    run_id = $RunId
    prompt_path = $outPrompt
    pid = $workerPid
    status = $(if ($workerPid) { "running" } else { "spawned" })
} | ConvertTo-Json -Compress
