# Build SAP / Coverity evidence pack from local audit chain + inventory.
# Air-gapped: no network.

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

$stamp = Get-Date -Format "yyyyMMddTHHmmssZ"
$pack = Join-Path $BrainRoot ".brain\audit\packs\$stamp"
New-Item -ItemType Directory -Force -Path $pack | Out-Null

Write-Host "Building audit pack → $pack" -ForegroundColor Cyan

& $Py -c @"
import json, shutil
from pathlib import Path
from audit_lib import verify_chain, scan_content_for_secrets, inventory_package, audit_dir, utc_now, audit
from brain_lib import status

pack = Path(r'''$pack''')
chain = verify_chain()
secrets = scan_content_for_secrets()
inv = inventory_package()
st = status()

(pack / 'chain_verify.json').write_text(json.dumps(chain, indent=2), encoding='utf-8')
(pack / 'secret_scan.json').write_text(json.dumps({'hits': secrets, 'count': len(secrets)}, indent=2), encoding='utf-8')
(pack / 'file_inventory.json').write_text(json.dumps(inv, indent=2), encoding='utf-8')
(pack / 'coverage.json').write_text(json.dumps({
    'status': st,
    'cursors': st.get('cursors'),
    'generated_at': utc_now(),
}, indent=2), encoding='utf-8')

# copy recent event files
ad = audit_dir()
ev_dir = pack / 'events'
ev_dir.mkdir(exist_ok=True)
for fp in sorted(ad.glob('events-*.jsonl'))[-14:]:
    shutil.copy2(fp, ev_dir / fp.name)

summary = f'''# Private Brain Audit Pack

Generated: {utc_now()}
Air-gapped: YES (local evidence only)

## Chain verification
- ok: {chain.get('ok')}
- events_checked: {chain.get('events_checked')}
- errors: {len(chain.get('errors') or [])}

## Corpus
- nodes: {st.get('node_count')}
- edges: {st.get('edge_count')}
- by_source: {st.get('by_source')}
- by_tier: {st.get('by_tier')}

## Secret pattern scan (hygiene, not egress)
- hits: {len(secrets)}

## Coverity intake
- See file_inventory.json for package source inventory.
- Python/PowerShell entrypoints under scripts/ and visualizer/.

## How to use for SAP
1. Verify chain_verify.json ok=true
2. Review events/ for agent_id, role, action, object_id timelines
3. Review watcher findings if present
4. Submit file_inventory + scripts to static analysis as required
'''
(pack / 'SUMMARY.md').write_text(summary, encoding='utf-8')
audit('audit_pack', agent_id='auditor', role='auditor', result='ok', detail=f'pack={pack.name}', props={'events': chain.get('events_checked')})
print(str(pack))
"@

Write-Host "Audit pack complete." -ForegroundColor Green
