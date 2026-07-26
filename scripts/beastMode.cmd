@echo off
REM Private Brain — thin Codex sideload launcher (Windows).
REM End users never run Python. Features via arguments only, then codex.
REM Full parity with bash beastMode (package/scripts/beastMode).
REM
REM   beastMode                         headless
REM   beastMode -GodsEye                live GUI
REM   beastMode --swarm 32
REM   beastMode -ingestion URL --max
REM   beastMode -colonoscopy URL        (= -ingestion URL --max)
REM   beastMode -ingestion gnome --ingest-only
REM   beastMode --preset salsa --max
REM   beastMode --sync-memory
REM   beastMode --note "text"
REM   beastMode --no-auto-sync
REM   beastMode --doctor
REM   beastMode --nuclear

setlocal EnableExtensions EnableDelayedExpansion

if not defined CODEX_HOME set "CODEX_HOME=%USERPROFILE%\.codex"
if defined CODEX_HOME_OVERRIDE set "CODEX_HOME=%CODEX_HOME_OVERRIDE%"
if not defined PRIVATE_BRAIN_HOME set "PRIVATE_BRAIN_HOME=%CODEX_HOME%\private-brain"

set "PB_GODSEYE=0"
if not defined PB_SWARM_AGENTS set "PB_SWARM_AGENTS=0"
REM Always-on organism defaults (Windows Corporate)
if not defined PB_ENTERPRISE set "PB_ENTERPRISE=1"
if not defined PB_GODSEYE set "PB_GODSEYE=1"
if not defined PB_SWARM_AGENTS set "PB_SWARM_AGENTS=auto"
if not defined PB_MAX_AGENTS set "PB_MAX_AGENTS=auto"
if not defined PB_AWS_REGION set "PB_AWS_REGION=gov-region-1"
set "PROFILE=beast-enterprise"
set "EXTRA="
set "REST="
set "INGEST_URL="
set "INGEST_PRESET="
set "INGEST_MAX=0"
set "INGEST_ONLY=0"
set "INGEST_SHALLOW=0"
set "INGEST_MAX_PROJECTS="
set "SYNC_MEMORY=0"
set "NOTE_TEXT="
set "AUTO_SYNC=1"
set "DOCTOR=0"
set "ENTERPRISE=1"
set "HEAL=0"
set "MISSION=0"
set "FIRE_DRILL=0"
set "OPS_METRICS=0"
set "AUTOPILOT=0"
set "NO_AUTOPILOT=0"
set "SHOW_GODSEYE=0"
set "RUN_DAY1=0"
set "QUARANTINE=0"
set "SAP_PACK=0"
set "VALIDATE=0"
set "CAPABILITIES=0"
set "PIPELINE_MODE="
set "NEVER_FORGET_INIT=0"
set "ORGANIZE=0"
set "INTERVIEW=0"
set "EXIT_AFTER=0"
set "PROJECT_NAME="
set "PYGAME_HIDE_SUPPORT_PROMPT=1"

:parse
if "%~1"=="" goto after_parse

if /I "%~1"=="-h" goto help
if /I "%~1"=="--help" goto help
if /I "%~1"=="--doctor" set "DOCTOR=1"& shift& goto parse
if /I "%~1"=="-doctor" set "DOCTOR=1"& shift& goto parse
if /I "%~1"=="--enterprise" set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "PROFILE=beast-enterprise"& shift& goto parse
if /I "%~1"=="-enterprise" set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "PROFILE=beast-enterprise"& shift& goto parse
if /I "%~1"=="--heal" set "HEAL=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--self-heal" set "HEAL=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--repair" set "HEAL=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--mission" set "MISSION=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--monday" set "MISSION=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--zero-fail" set "MISSION=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--fire-drill" set "FIRE_DRILL=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--firedrill" set "FIRE_DRILL=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--airtight" set "FIRE_DRILL=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--metrics" set "OPS_METRICS=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--ops-metrics" set "OPS_METRICS=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--autopilot" set "AUTOPILOT=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--alive" set "AUTOPILOT=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--wake" set "AUTOPILOT=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--organism" set "AUTOPILOT=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--water-pipe" set "AUTOPILOT=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--no-autopilot" set "NO_AUTOPILOT=1"& set "PB_AUTOPILOT=0"& shift& goto parse
if /I "%~1"=="--no-organism" set "NO_AUTOPILOT=1"& set "PB_AUTOPILOT=0"& shift& goto parse
if /I "%~1"=="--show-godseye" set "SHOW_GODSEYE=1"& set "EXIT_AFTER=1"& set "PB_GODSEYE=1"& set "PB_GODSEYE_FORCE=1"& shift& goto parse
if /I "%~1"=="--day1" set "RUN_DAY1=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--DAY1" set "RUN_DAY1=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--quarantine-public" set "QUARANTINE=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--sap-pack" set "SAP_PACK=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--validate-enterprise" set "VALIDATE=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--e2e-enterprise" set "VALIDATE=1"& set "ENTERPRISE=1"& set "PB_ENTERPRISE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--capabilities" set "CAPABILITIES=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--caps" set "CAPABILITIES=1"& set "EXIT_AFTER=1"& shift& goto parse

if /I "%~1"=="-GodsEye" set "PB_GODSEYE=1"& set "PROFILE=beast-godseye"& set "PB_GODSEYE_BACKEND=gl"& shift& goto parse
if /I "%~1"=="--GodsEye" set "PB_GODSEYE=1"& set "PROFILE=beast-godseye"& set "PB_GODSEYE_BACKEND=gl"& shift& goto parse
if /I "%~1"=="--godseye" set "PB_GODSEYE=1"& set "PROFILE=beast-godseye"& set "PB_GODSEYE_BACKEND=gl"& shift& goto parse
if /I "%~1"=="-godseye" set "PB_GODSEYE=1"& set "PROFILE=beast-godseye"& set "PB_GODSEYE_BACKEND=gl"& shift& goto parse
if /I "%~1"=="--GodsEye-cpu" set "PB_GODSEYE=1"& set "PROFILE=beast-godseye"& set "PB_GODSEYE_BACKEND=cpu"& shift& goto parse
if /I "%~1"=="--godseye-cpu" set "PB_GODSEYE=1"& set "PROFILE=beast-godseye"& set "PB_GODSEYE_BACKEND=cpu"& shift& goto parse
if /I "%~1"=="--no-gui" set "PB_GODSEYE=0"& set "PROFILE=beast"& shift& goto parse
if /I "%~1"=="--headless" set "PB_GODSEYE=0"& set "PROFILE=beast"& shift& goto parse

if /I "%~1"=="--swarm" (
  if not "%~2"=="" if not "%~2:~0,1%"=="-" (
    set "PB_SWARM_AGENTS=%~2"
    shift& shift& goto parse
  )
  set "PB_SWARM_AGENTS=32"
  shift& goto parse
)
set "_arg=%~1"
if /I "!_arg:~0,8!"=="--swarm=" (
  set "PB_SWARM_AGENTS=!_arg:~8!"
  shift& goto parse
)


if /I "%~1"=="--pipeline" (
  if /I "%~2"=="demo" set "PIPELINE_MODE=demo"& shift& shift& set "EXIT_AFTER=1"& goto parse
  if /I "%~2"=="brain" set "PIPELINE_MODE=brain"& shift& shift& set "EXIT_AFTER=1"& goto parse
  if /I "%~2"=="test" set "PIPELINE_MODE=test"& shift& shift& set "EXIT_AFTER=1"& goto parse
  set "PIPELINE_MODE=demo"& set "EXIT_AFTER=1"& shift& goto parse
)
if /I "%~1"=="--lgh" set "PIPELINE_MODE=demo"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--never-forget-init" set "NEVER_FORGET_INIT=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--interview" set "INTERVIEW=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--organize" set "ORGANIZE=1"& set "EXIT_AFTER=1"& shift& goto parse
if /I "%~1"=="--project" set "PROJECT_NAME=%~2"& set "EXIT_AFTER=1"& shift& shift& goto parse
if /I "%~1"=="--no-lgh" set "PB_LGH=0"& shift& goto parse

if /I "%~1"=="--nuclear" set "EXTRA=--dangerously-bypass-approvals-and-sandbox"& shift& goto parse
if /I "%~1"=="--max" set "INGEST_MAX=1"& shift& goto parse
if /I "%~1"=="--max-ingest" set "INGEST_MAX=1"& shift& goto parse
if /I "%~1"=="--shallow" set "INGEST_SHALLOW=1"& shift& goto parse
if /I "%~1"=="--ingest-only" set "INGEST_ONLY=1"& shift& goto parse

if /I "%~1"=="--max-projects" (
  set "INGEST_MAX_PROJECTS=%~2"
  if "!INGEST_MAX_PROJECTS!"=="" (
    echo beastMode: --max-projects requires N 1>&2
    exit /b 2
  )
  shift& shift& goto parse
)
if /I "!_arg:~0,15!"=="--max-projects=" (
  set "INGEST_MAX_PROJECTS=!_arg:~15!"
  shift& goto parse
)

if /I "%~1"=="--sync-memory" set "SYNC_MEMORY=1"& shift& goto parse
if /I "%~1"=="--sync-boss" set "SYNC_MEMORY=1"& shift& goto parse
if /I "%~1"=="--distill-sync" set "SYNC_MEMORY=1"& shift& goto parse
if /I "%~1"=="--no-auto-sync" set "AUTO_SYNC=0"& shift& goto parse

if /I "%~1"=="--note" (
  set "NOTE_TEXT=%~2"
  if "!NOTE_TEXT!"=="" (
    echo beastMode: --note needs text ^(what worked / tell past-self^) 1>&2
    exit /b 2
  )
  shift& shift& goto parse
)
if /I "!_arg:~0,7!"=="--note=" (
  set "NOTE_TEXT=!_arg:~7!"
  shift& goto parse
)

if /I "%~1"=="--preset" (
  set "INGEST_PRESET=%~2"
  if "!INGEST_PRESET!"=="" (
    echo beastMode: --preset requires name: gnome^|salsa^|gitlab^|freexian 1>&2
    exit /b 2
  )
  shift& shift& goto parse
)
if /I "!_arg:~0,9!"=="--preset=" (
  set "INGEST_PRESET=!_arg:~9!"
  shift& goto parse
)

if /I "%~1"=="-ingestion" goto ingest_val
if /I "%~1"=="--ingestion" goto ingest_val
if /I "%~1"=="--ingest" goto ingest_val
if /I "!_arg:~0,11!"=="-ingestion=" (
  set "_v=!_arg:~11!"
  goto ingest_eq
)
if /I "!_arg:~0,12!"=="--ingestion=" (
  set "_v=!_arg:~12!"
  goto ingest_eq
)
if /I "!_arg:~0,9!"=="--ingest=" (
  set "_v=!_arg:~9!"
  goto ingest_eq
)

if /I "%~1"=="-colonoscopy" goto colonoscopy_val
if /I "%~1"=="--colonoscopy" goto colonoscopy_val

if /I "%~1"=="-p" set "PROFILE=%~2"& shift& shift& goto parse
if /I "%~1"=="--profile" set "PROFILE=%~2"& shift& shift& goto parse

set "REST=!REST! %1"
shift
goto parse

:ingest_eq
if /I "%_v%"=="gnome" set "INGEST_PRESET=gnome"& shift& goto parse
if /I "%_v%"=="salsa" set "INGEST_PRESET=salsa"& shift& goto parse
if /I "%_v%"=="gitlab" set "INGEST_PRESET=gitlab"& shift& goto parse
if /I "%_v%"=="freexian" set "INGEST_PRESET=freexian"& shift& goto parse
set "INGEST_URL=%_v%"
shift& goto parse

:ingest_val
set "_v=%~2"
if "%_v%"=="" (
  echo beastMode: -ingestion requires a URL or preset ^(gnome^|salsa^|gitlab^|freexian^) 1>&2
  exit /b 2
)
if /I "%_v%"=="gnome" set "INGEST_PRESET=gnome"& shift& shift& goto parse
if /I "%_v%"=="salsa" set "INGEST_PRESET=salsa"& shift& shift& goto parse
if /I "%_v%"=="gitlab" set "INGEST_PRESET=gitlab"& shift& shift& goto parse
if /I "%_v%"=="freexian" set "INGEST_PRESET=freexian"& shift& shift& goto parse
set "INGEST_URL=%_v%"
shift& shift& goto parse

:colonoscopy_val
REM Alias: -ingestion URL|PRESET --max
set "_v=%~2"
if "%_v%"=="" (
  echo beastMode: -colonoscopy requires a URL or preset 1>&2
  exit /b 2
)
set "INGEST_MAX=1"
if /I "%_v%"=="gnome" set "INGEST_PRESET=gnome"& shift& shift& goto parse
if /I "%_v%"=="salsa" set "INGEST_PRESET=salsa"& shift& shift& goto parse
if /I "%_v%"=="gitlab" set "INGEST_PRESET=gitlab"& shift& shift& goto parse
if /I "%_v%"=="freexian" set "INGEST_PRESET=freexian"& shift& shift& goto parse
set "INGEST_URL=%_v%"
shift& shift& goto parse

:help
echo Private Brain sideload launcher - Windows ^(always ends in: codex -p ^<profile^>^)
echo.
echo   beastMode [features] [codex args...]
echo.
echo You never run Python. Only beastMode / SETUP / UNINSTALL.
echo Corporate work laptop = this .cmd ^(not Mac bash^).
echo.
echo Features:
echo   -GodsEye / --godseye       Live GUI ^(TRUE GL^)
echo   --GodsEye-cpu              Software pygame GUI
echo   --no-gui                   Force headless ^(default^)
echo   --enterprise               Corporate pilot profile
echo   --heal                     Self-heal: capabilities · chain · vectors · snapshot
echo   --mission                  Monday zero-fail gates ^(LOCAL -^> OPS -^> AWS SHIM^)
echo   --fire-drill               Dual-OS airtight smoke ^(Mac live + Windows static + heal^)
echo   --metrics / --ops-metrics  Ops scoreboard -^> .brain\state\ops_metrics.json
echo   --autopilot / --alive      ONE organism: sessions-heal-quarantine-metrics
echo   --no-autopilot             Skip auto organism on --enterprise launch
echo   --day1                     Full day-1 interview + sessions + heal + crawl
echo   --doctor                   READY/FAIL health
echo.
echo Default: beastMode --enterprise runs autopilot then opens Codex.
echo You should almost never type --heal/--doctor/--mission by hand.
echo   --quarantine-public        Tag public OSS hosts
echo   --validate-enterprise      Full E2E hard gates
echo   --capabilities             Probe optional modules
echo   --swarm N                  Shared-topology multi-agent sweep
echo   -ingestion URL^|PRESET      GitLab URL or preset
echo   --ingest-only              Ingest then exit
echo   --sync-memory              Distill vault -^> Codex skills
echo.
echo Self-heal on every enterprise launch. Full heal: beastMode --heal
echo.
echo Env: PB_ENTERPRISE PIP_INDEX_URL PB_GITLAB_URL GITLAB_TOKEN PB_LLM_BASE_URL
exit /b 0

:after_parse

REM ── Resolve python: Windows venv\Scripts FIRST, then Unix, then PATH ──
set "PY="
if exist "%PRIVATE_BRAIN_HOME%\venv\Scripts\python.exe" (
  "%PRIVATE_BRAIN_HOME%\venv\Scripts\python.exe" -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=%PRIVATE_BRAIN_HOME%\venv\Scripts\python.exe"
)
if not defined PY if exist "%PRIVATE_BRAIN_HOME%\venv\Scripts\python" (
  set "PY=%PRIVATE_BRAIN_HOME%\venv\Scripts\python"
)
if not defined PY if exist "%PRIVATE_BRAIN_HOME%\venv\bin\python3" (
  "%PRIVATE_BRAIN_HOME%\venv\bin\python3" -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=%PRIVATE_BRAIN_HOME%\venv\bin\python3"
)
if not defined PY (
  where py >nul 2>&1 && set "PY=py" && set "PY_ARGS=-3" && set "PY=py -3"
)
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  where python3 >nul 2>&1 && set "PY=python3"
)

set "PYTHONPATH=%PRIVATE_BRAIN_HOME%\scripts;%PRIVATE_BRAIN_HOME%"
if defined PYTHONPATH_EXTRA set "PYTHONPATH=%PYTHONPATH%;%PYTHONPATH_EXTRA%"
set "PYGAME_HIDE_SUPPORT_PROMPT=1"

REM ── Feature exits that need python ──
if "%RUN_DAY1%"=="1" goto run_day1
if "%MISSION%"=="1" goto run_mission
if "%FIRE_DRILL%"=="1" goto run_fire_drill
if "%OPS_METRICS%"=="1" goto run_metrics
if "%SHOW_GODSEYE%"=="1" goto run_show_godseye
if "%AUTOPILOT%"=="1" goto run_autopilot
if "%HEAL%"=="1" goto run_heal
if "%QUARANTINE%"=="1" goto run_quarantine
if "%SAP_PACK%"=="1" goto run_sap
if "%VALIDATE%"=="1" goto run_validate
if "%CAPABILITIES%"=="1" goto run_capabilities
if "%DOCTOR%"=="1" goto doctor

if not defined PY (
  if "%INGEST_ONLY%"=="1" goto no_py_fatal
  if not "%INGEST_URL%"=="" goto no_py_fatal
  if not "%INGEST_PRESET%"=="" goto no_py_fatal
  if defined PB_INGEST_URL if not "%PB_INGEST_URL%"=="" goto no_py_fatal
  if "%ENTERPRISE%"=="1" goto no_py_fatal
)
goto after_py_check
:no_py_fatal
echo beastMode: no usable python runtime ^(re-run SETUP.ps1 — need venv\Scripts\python.exe^) 1>&2
exit /b 1
:after_py_check

REM ORGANISM water-pipe on every launch (beastMode always-on)
if "%ENTERPRISE%"=="1" set "PB_ENTERPRISE=1"
if "%PB_ENTERPRISE%"=="1" set "PROFILE=beast-enterprise"
if not "%NO_AUTOPILOT%"=="1" if not "%PB_AUTOPILOT%"=="0" (
  if defined PY (
    set "PYTHONPATH=%PRIVATE_BRAIN_HOME%\scripts;%PRIVATE_BRAIN_HOME%;%PYTHONPATH%"
    set "PB_ENTERPRISE=1"
    if not defined PB_GODSEYE set "PB_GODSEYE=1"
    echo beastMode: waking ORGANISM ^(water pipe^)... 1>&2
    if exist "%PRIVATE_BRAIN_HOME%\scripts\organism.py" (
      %PY% "%PRIVATE_BRAIN_HOME%\scripts\organism.py" --quiet 2>nul
    ) else if exist "%PRIVATE_BRAIN_HOME%\scripts\autopilot.py" (
      %PY% "%PRIVATE_BRAIN_HOME%\scripts\autopilot.py" --quiet 2>nul
    )
    if not exist "%PRIVATE_BRAIN_HOME%\.brain\state" mkdir "%PRIVATE_BRAIN_HOME%\.brain\state" >nul 2>&1
    type nul > "%PRIVATE_BRAIN_HOME%\.brain\state\enterprise.on" 2>nul
    type nul > "%PRIVATE_BRAIN_HOME%\.brain\state\beastmode.on" 2>nul
  )
)

REM ── Self-recovery: beast profiles ──
if not exist "%CODEX_HOME%\beast.config.toml" (
  echo beastMode: recovering beast.config.toml 1>&2
  if not exist "%CODEX_HOME%" mkdir "%CODEX_HOME%" >nul 2>&1
  >"%CODEX_HOME%\beast.config.toml" (
    echo model = "gpt-5.6-terra"
    echo approval_policy = "never"
    echo sandbox_mode = "danger-full-access"
    echo model_reasoning_effort = "high"
  )
)
if not exist "%CODEX_HOME%\beast-enterprise.config.toml" (
  echo beastMode: recovering beast-enterprise.config.toml 1>&2
  if defined PY if exist "%PRIVATE_BRAIN_HOME%\scripts\enterprise.py" (
    set "PB_ENTERPRISE=1"
    %PY% "%PRIVATE_BRAIN_HOME%\scripts\enterprise.py" ensure-profile >nul 2>&1
  )
)
if not exist "%CODEX_HOME%\beast-enterprise.config.toml" (
  if exist "%CODEX_HOME%\beast.config.toml" copy /Y "%CODEX_HOME%\beast.config.toml" "%CODEX_HOME%\beast-enterprise.config.toml" >nul 2>&1
)
if not exist "%CODEX_HOME%\beast-godseye.config.toml" (
  copy /Y "%CODEX_HOME%\beast.config.toml" "%CODEX_HOME%\beast-godseye.config.toml" >nul 2>&1
)

REM ── Self-recovery: hooks.json ──
if not exist "%CODEX_HOME%\hooks.json" (
  echo beastMode: recovering hooks.json 1>&2
  if defined PY if exist "%PRIVATE_BRAIN_HOME%\scripts\install_hooks.py" (
    %PY% "%PRIVATE_BRAIN_HOME%\scripts\install_hooks.py" >nul 2>&1
  )
)
if not exist "%CODEX_HOME%\hooks.json" (
  if not exist "%PRIVATE_BRAIN_HOME%\hooks" mkdir "%PRIVATE_BRAIN_HOME%\hooks" >nul 2>&1
  if not defined PY set "HOOK_PY=py -3"
  if defined PY set "HOOK_PY=%PY%"
  >"%CODEX_HOME%\hooks.json" (
    echo {
    echo   "description": "Private Brain RAG-DAG auto boot (recovered)",
    echo   "hooks": {
    echo     "SessionStart": [{"matcher": "startup^|resume^|clear", "hooks": [{"type": "command", "command": "%HOOK_PY% %PRIVATE_BRAIN_HOME%\hooks\session_start.py", "timeout": 120, "statusMessage": "Private Brain RAG-DAG boot"}]}],
    echo     "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "%HOOK_PY% %PRIVATE_BRAIN_HOME%\hooks\user_prompt_submit.py", "timeout": 180, "statusMessage": "Private Brain retrieve DAG"}]}],
    echo     "Stop": [{"hooks": [{"type": "command", "command": "%HOOK_PY% %PRIVATE_BRAIN_HOME%\hooks\stop_validate.py", "timeout": 30, "statusMessage": "Private Brain answer validator"}]}]
    echo   }
    echo }
  )
  copy /Y "%CODEX_HOME%\hooks.json" "%PRIVATE_BRAIN_HOME%\hooks\hooks.json" >nul 2>&1
)

REM ── Self-recovery: .brain ──
if not exist "%PRIVATE_BRAIN_HOME%\.brain" (
  echo beastMode: recovering .brain tree 1>&2
  if defined PY if exist "%PRIVATE_BRAIN_HOME%\scripts\brain_init.py" (
    %PY% "%PRIVATE_BRAIN_HOME%\scripts\brain_init.py" >nul 2>&1
  )
)

REM ── Ingestion ──
if not "%INGEST_URL%"=="" goto do_ingest
if not "%INGEST_PRESET%"=="" goto do_ingest
if defined PB_INGEST_URL if not "%PB_INGEST_URL%"=="" (
  if "%INGEST_URL%"=="" if "%INGEST_PRESET%"=="" set "INGEST_URL=%PB_INGEST_URL%"
  goto do_ingest
)
goto after_ingest

:do_ingest
if not exist "%PRIVATE_BRAIN_HOME%\scripts\gitlab_ingest.py" (
  echo beastMode: gitlab_ingest.py missing under %PRIVATE_BRAIN_HOME%\scripts 1>&2
  exit /b 1
)
if not defined PY (
  echo beastMode: cannot ingest without python runtime ^(re-run SETUP^) 1>&2
  exit /b 1
)

set "IARGS=--deep --verbose --json"
if not "%INGEST_PRESET%"=="" (
  set "IARGS=!IARGS! --preset %INGEST_PRESET%"
  echo Private Brain ingestion preset: %INGEST_PRESET% 1>&2
) else (
  if "%INGEST_URL%"=="" set "INGEST_URL=%PB_INGEST_URL%"
  set "IARGS=!IARGS! --url %INGEST_URL%"
  set "PB_INGEST_URL=%INGEST_URL%"
  echo Private Brain ingestion: %INGEST_URL% 1>&2
)
if "%INGEST_MAX%"=="1" (
  set "IARGS=!IARGS! --max"
  echo Private Brain ingestion: MAX capture ^(deep + generous limits, still polite^) 1>&2
)
if "%INGEST_SHALLOW%"=="1" set "IARGS=!IARGS! --shallow"
if not "%INGEST_MAX_PROJECTS%"=="" set "IARGS=!IARGS! --max-projects %INGEST_MAX_PROJECTS%"
if defined GITLAB_TOKEN set "IARGS=!IARGS! --token %GITLAB_TOKEN%"

set "INGEST_EC=0"
%PY% "%PRIVATE_BRAIN_HOME%\scripts\gitlab_ingest.py" !IARGS!
if errorlevel 1 (
  set "INGEST_EC=1"
  echo beastMode: ingestion finished with errors ^(continuing unless --ingest-only^) 1>&2
)
if "%INGEST_ONLY%"=="1" (
  echo beastMode: --ingest-only done 1>&2
  exit /b !INGEST_EC!
)

:after_ingest

REM ── Distill vault / sync-memory / note ──
set "DISTILL=%PRIVATE_BRAIN_HOME%\scripts\distill_vault.py"
if defined PY if exist "%DISTILL%" (
  if not "!NOTE_TEXT!"=="" (
    %PY% "%DISTILL%" note --text "!NOTE_TEXT!" >nul 2>&1
    echo beastMode: distill note saved under vault/distill/ 1>&2
    set "SYNC_MEMORY=1"
  )
  set "NEED_SYNC=0"
  if "%SYNC_MEMORY%"=="1" set "NEED_SYNC=1"
  if "%AUTO_SYNC%"=="1" if not exist "%CODEX_HOME%\skills\private-brain\SKILL.md" set "NEED_SYNC=1"
  if "!NEED_SYNC!"=="1" (
    echo beastMode: syncing distill vault -^> Codex skills/AGENTS ^(boss brain^) 1>&2
    %PY% "%DISTILL%" sync >nul 2>&1
  )
  if "%SYNC_MEMORY%"=="1" if "%INGEST_ONLY%"=="1" if "%INGEST_URL%"=="" if "%INGEST_PRESET%"=="" (
    if not defined PB_INGEST_URL (
      echo beastMode: --sync-memory done 1>&2
      exit /b 0
    )
  )
)

REM ── GodsEye ──
if "%PB_GODSEYE%"=="1" (
  if defined PY if exist "%PRIVATE_BRAIN_HOME%\scripts\godseye.py" (
    %PY% "%PRIVATE_BRAIN_HOME%\scripts\godseye.py" start >nul 2>&1
  )
)

if "%INGEST_ONLY%"=="1" exit /b 0

where codex >nul 2>&1
if errorlevel 1 (
  echo codex not found — install Codex CLI first. 1>&2
  exit /b 1
)


REM LOOP-GRAPH-HARNESS + second mind features
if not "%PIPELINE_MODE%"=="" (
  set "PYTHONPATH=%PRIVATE_BRAIN_HOME%\scripts;%PRIVATE_BRAIN_HOME%"
  echo beastMode: LOOP-GRAPH-HARNESS mode=%PIPELINE_MODE% 1>&2
  %PY% -m loop_graph_harness.pipeline %PIPELINE_MODE%
  exit /b %ERRORLEVEL%
)
if "%NEVER_FORGET_INIT%"=="1" (
  "%PY%" "%PRIVATE_BRAIN_HOME%\scripts\second_mind.py" init
)
if "%INTERVIEW%"=="1" (
  "%PY%" "%PRIVATE_BRAIN_HOME%\scripts\second_mind.py" interview
)
if not "%PROJECT_NAME%"=="" (
  "%PY%" "%PRIVATE_BRAIN_HOME%\scripts\second_mind.py" project --name "%PROJECT_NAME%"
)
if "%ORGANIZE%"=="1" (
  "%PY%" "%PRIVATE_BRAIN_HOME%\scripts\second_mind.py" organize
)
if "%EXIT_AFTER%"=="1" (
  echo beastMode: feature done (no codex) 1>&2
  exit /b 0
)

REM Full system access baseline (mission). Profile also sets danger-full-access.
if "%EXTRA%"=="" set "EXTRA=--dangerously-bypass-approvals-and-sandbox"
echo %EXTRA% | findstr /C:"dangerously-bypass-approvals" >nul
if errorlevel 1 set "EXTRA=--dangerously-bypass-approvals-and-sandbox %EXTRA%"
codex --dangerously-bypass-hook-trust %EXTRA% -p %PROFILE% %REST%
exit /b %ERRORLEVEL%

:run_heal
if not defined PY (
  echo beastMode: --heal needs python ^(venv\Scripts\python.exe^) 1>&2
  exit /b 1
)
if "%ENTERPRISE%"=="1" set "PB_ENTERPRISE=1"
echo beastMode: self-heal ^(capabilities · chain · vectors · snapshot^)... 1>&2
%PY% "%PRIVATE_BRAIN_HOME%\scripts\capabilities.py" --repair >nul 2>&1
%PY% "%PRIVATE_BRAIN_HOME%\scripts\enterprise.py" heal
exit /b %ERRORLEVEL%

:run_mission
if not defined PY (
  echo beastMode: --mission needs python 1>&2
  exit /b 1
)
set "PB_ENTERPRISE=1"
echo beastMode: Monday mission zero-fail gates... 1>&2
%PY% "%PRIVATE_BRAIN_HOME%\scripts\mission_monday.py"
exit /b %ERRORLEVEL%

:run_fire_drill
if not defined PY (
  echo beastMode: --fire-drill needs python 1>&2
  exit /b 1
)
set "PB_ENTERPRISE=1"
echo beastMode: FIRE DRILL dual-OS zero-fail... 1>&2
%PY% "%PRIVATE_BRAIN_HOME%\scripts\fire_drill.py"
exit /b %ERRORLEVEL%

:run_metrics
if not defined PY (
  echo beastMode: --metrics needs python 1>&2
  exit /b 1
)
%PY% "%PRIVATE_BRAIN_HOME%\scripts\ops_metrics.py"
exit /b %ERRORLEVEL%

:run_show_godseye
if not defined PY (
  echo beastMode: --show-godseye needs python 1>&2
  exit /b 1
)
set "PB_GODSEYE=1"
set "PB_GODSEYE_FORCE=1"
set "PYTHONPATH=%PRIVATE_BRAIN_HOME%\scripts;%PRIVATE_BRAIN_HOME%;%PYTHONPATH%"
echo beastMode: opening GodsEye... 1>&2
%PY% -c "import godseye as g; g.clear_dismissed(); g.set_enabled(True); print(g.ensure_gui(force=True))"
exit /b %ERRORLEVEL%

:run_autopilot
if not defined PY (
  echo beastMode: --organism needs python 1>&2
  exit /b 1
)
set "PB_ENTERPRISE=1"
set "PYTHONPATH=%PRIVATE_BRAIN_HOME%\scripts;%PRIVATE_BRAIN_HOME%;%PYTHONPATH%"
echo beastMode: ORGANISM water-pipe... 1>&2
if exist "%PRIVATE_BRAIN_HOME%\scripts\organism.py" (
  %PY% "%PRIVATE_BRAIN_HOME%\scripts\organism.py"
) else (
  %PY% "%PRIVATE_BRAIN_HOME%\scripts\autopilot.py"
)
exit /b %ERRORLEVEL%

:run_day1
set "PB_ENTERPRISE=1"
set "DAY1PS=%PRIVATE_BRAIN_HOME%\scripts\DAY1.ps1"
if not exist "%DAY1PS%" (
  echo beastMode: DAY1.ps1 missing at %DAY1PS% 1>&2
  exit /b 1
)
echo beastMode: DAY1 Windows ^(sessions → heal → mission → crawl^)... 1>&2
powershell -NoProfile -ExecutionPolicy Bypass -File "%DAY1PS%" %REST%
exit /b %ERRORLEVEL%

:run_quarantine
if not defined PY exit /b 1
set "PB_ENTERPRISE=1"
echo beastMode: quarantine public hosts... 1>&2
%PY% "%PRIVATE_BRAIN_HOME%\scripts\enterprise.py" quarantine-public
exit /b %ERRORLEVEL%

:run_sap
if not defined PY exit /b 1
set "PB_ENTERPRISE=1"
%PY% "%PRIVATE_BRAIN_HOME%\scripts\enterprise.py" sap-pack
exit /b %ERRORLEVEL%

:run_validate
if not defined PY exit /b 1
set "PB_ENTERPRISE=1"
echo beastMode: validate-enterprise... 1>&2
%PY% "%PRIVATE_BRAIN_HOME%\scripts\validate_enterprise.py"
exit /b %ERRORLEVEL%

:run_capabilities
if not defined PY exit /b 1
echo beastMode: capabilities... 1>&2
%PY% "%PRIVATE_BRAIN_HOME%\scripts\capabilities.py"
exit /b %ERRORLEVEL%

:doctor
echo Private Brain doctor ^(Windows^)
echo   CODEX_HOME=%CODEX_HOME%
echo   PRIVATE_BRAIN_HOME=%PRIVATE_BRAIN_HOME%
echo   PY=%PY%
echo.
set "FAIL=0"

if exist "%CODEX_HOME%\hooks.json" (
  echo   [OK] hooks.json
) else (
  echo   [FAIL] hooks.json missing
  set "FAIL=1"
)

if exist "%CODEX_HOME%\beast.config.toml" (
  echo   [OK] beast.config.toml
) else (
  echo   [FAIL] beast.config.toml missing
  set "FAIL=1"
)

if "%PB_ENTERPRISE%"=="1" (
  if exist "%CODEX_HOME%\beast-enterprise.config.toml" (
    echo   [OK] beast-enterprise.config.toml
  ) else (
    echo   [WARN] beast-enterprise.config.toml missing — heal will create
  )
)

if exist "%PRIVATE_BRAIN_HOME%" (
  echo   [OK] private-brain home
) else (
  echo   [FAIL] private-brain home missing
  set "FAIL=1"
)

if exist "%PRIVATE_BRAIN_HOME%\.brain" (
  echo   [OK] .brain tree
) else (
  echo   [FAIL] .brain tree missing
  set "FAIL=1"
)

set "SCRIPTS=%PRIVATE_BRAIN_HOME%\scripts"
set "MISS="
if not exist "%SCRIPTS%\orchestrate.py" set "MISS=!MISS! orchestrate.py"
if not exist "%SCRIPTS%\enterprise.py" set "MISS=!MISS! enterprise.py"
if not exist "%SCRIPTS%\capabilities.py" set "MISS=!MISS! capabilities.py"
if not exist "%SCRIPTS%\mission_monday.py" set "MISS=!MISS! mission_monday.py"
if not exist "%SCRIPTS%\brain_lib.py" set "MISS=!MISS! brain_lib.py"
if not exist "%SCRIPTS%\audit_lib.py" set "MISS=!MISS! audit_lib.py"
if not exist "%SCRIPTS%\smart_discover.py" set "MISS=!MISS! smart_discover.py"
if "!MISS!"=="" (
  echo   [OK] engine scripts
) else (
  echo   [FAIL] engine scripts missing:!MISS!
  set "FAIL=1"
)

if defined PY (
  echo   [OK] python runtime
) else (
  echo   [FAIL] python runtime missing — re-run SETUP.ps1
  set "FAIL=1"
)

if exist "%PRIVATE_BRAIN_HOME%\venv\Scripts\python.exe" (
  echo   [OK] Windows venv\Scripts\python.exe
) else (
  echo   [WARN] venv\Scripts\python.exe missing — SETUP should create it
)

if exist "%PRIVATE_BRAIN_HOME%\hooks\session_start.py" (
  echo   [OK] hook scripts
) else (
  echo   [FAIL] hook scripts missing
  set "FAIL=1"
)

REM Prefer full enterprise doctor when available
if defined PY if exist "%SCRIPTS%\enterprise.py" if "%PB_ENTERPRISE%"=="1" (
  echo   --- enterprise doctor ---
  %PY% "%SCRIPTS%\enterprise.py" doctor
  if errorlevel 1 set "FAIL=1"
) else if defined PY if exist "%SCRIPTS%\audit_verify.py" (
  %PY% "%SCRIPTS%\audit_verify.py" >nul 2>&1
  if errorlevel 1 (
    echo   [FAIL] audit chain
    set "FAIL=1"
  ) else (
    echo   [OK] audit chain
  )
)

where codex >nul 2>&1
if errorlevel 1 (
  echo   [WARN] codex not on PATH
) else (
  echo   [OK] codex on PATH
)

echo.
if "%FAIL%"=="0" (
  echo READY
  exit /b 0
) else (
  echo FAIL
  echo   Fix: PowerShell → beastMode --heal
  echo   Or:  SETUP.ps1 then beastMode --enterprise --heal
  exit /b 1
)
