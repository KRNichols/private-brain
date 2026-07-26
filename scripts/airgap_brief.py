#!/usr/bin/env python3
"""Air-gap day brief — MD both AIs can read (Codex ↔ Grok 4.5).

No secrets. Performance + events + golden surface snapshot + phase-2 asks.
Written under .brain/state/briefs/ and vault/briefs/.

  python airgap_brief.py
  python airgap_brief.py --json

User can say in Codex: "day brief" / "end of day" / "air gap brief"
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))
os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _j(p: Path) -> dict[str, Any]:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def gather() -> dict[str, Any]:
    st = _ROOT / ".brain" / "state"
    return {
        "ts": _ts(),
        "day": _day(),
        "organism": _j(st / "organism.json"),
        "ops": _j(st / "ops_metrics.json"),
        "golden": _j(st / "golden_config.json"),
        "mode": _j(st / "conversation_mode.json"),
        "cloud": _j(st / "cloud_ready.json"),
        "fire": _j(st / "fire_drill.json"),
        "godseye": _j(st / "godseye_metrics.json"),
    }


def render(d: dict[str, Any]) -> str:
    org = d.get("organism") or {}
    ops = d.get("ops") or {}
    gold = d.get("golden") or {}
    env = gold.get("env") or {}
    score = ops.get("score") if isinstance(ops.get("score"), dict) else {}
    graph = gold.get("graph") or ops.get("graph") or {}
    purity = gold.get("purity") or ops.get("purity") or {}
    mode = (d.get("mode") or {}).get("mode") or "beast"

    return f"""# Air-Gap Day Brief — Private Brain ↔ Grok / Codex

**Day:** `{d.get('day')}` · **UTC:** `{d.get('ts')}`  
**Classification:** share only this MD (or redacted copy). **No tokens. No day1.env.**

This brief is the **air-gap handshake** so two AIs (e.g. Grok 4.5 lab + Codex Corporate) can plan phase-2 without live network between them.

---

## 1 · Mission posture

| Signal | Value |
|--------|-------|
| Conversation mode | **{mode}** (beast=RAG on · normal=RAG off) |
| Organism band | **{org.get('band') or '—'}** alive={org.get('alive')} |
| Ops band/score | **{score.get('band') or ops.get('band') or '—'}** / {score.get('ops_100') or '—'} |
| LOCAL_READY | {(org.get('local_ready') or {}).get('ok')} |
| Fire drill | {(d.get('fire') or {}).get('band') or (d.get('fire') or {}).get('ok')} |
| GodsEye FPS (last) | {(d.get('godseye') or {}).get('fps') or '—'} |
| Cloud ready | {(d.get('cloud') or {}).get('ready')} |

---

## 2 · Control surface (non-secret)

| Plane | Value |
|-------|-------|
| Program | {env.get('program_id') or '—'} · {env.get('classification') or '—'} |
| Package route | {env.get('route') or '—'} |
| GitLab | {env.get('gitlab') or 'NOT SET'} |
| Jira | {env.get('jira') or 'NOT SET'} |
| Confluence | {env.get('confluence') or 'NOT SET'} |
| AWS region | {env.get('aws_region') or 'gov-region-1'} |
| SHIM | {env.get('llm_shim') or 'NOT SET'} |
| OpenSearch | {env.get('opensearch') or 'NOT SET'} |
| Neptune | {env.get('neptune') or 'NOT SET'} |
| Edge model target | gpt-5.1 sovereign |
| AWS model target | enterprise-frontier-model |
| Lab model | grok-4.5 |

---

## 3 · RAG-DAG health

| Metric | Value |
|--------|------:|
| Nodes | {graph.get('nodes') or '—'} |
| Edges | {graph.get('edges') or '—'} |
| Vectors | {(gold.get('vectors') or {}).get('vectors') or (ops.get('vectors') or {}).get('vectors') or '—'} |
| Parity | {(gold.get('vectors') or {}).get('parity') or (ops.get('vectors') or {}).get('parity')} |
| Pilot ops | {purity.get('pilot_ops_ready')} |
| Pilot ship | {purity.get('pilot_ready')} |
| Public ratio | {purity.get('public_ratio')} |
| Quarantine | {purity.get('quarantine_coverage')} |

By source: `{json.dumps(graph.get('by_source') or {}, default=str)[:500]}`

---

## 4 · Events of the day (machine-derived)

- Organism last run: band=`{org.get('band')}` elapsed_ms=`{org.get('elapsed_ms')}`
- Sessions phase: `{json.dumps(org.get('sessions') or {}, default=str)[:300]}`
- Swarm: `{json.dumps(org.get('swarm') or {}, default=str)[:300]}`
- AWS phase: `{json.dumps(org.get('aws') or d.get('cloud') or {}, default=str)[:400]}`
- Golden paths: `.brain/state/GOLDEN_CONFIG.md` · `golden_join.json` for co-workers

*(Human: append free-text notes below the fold if needed.)*

### Human notes

- 

---

## 5 · Gaps & risks (honest)

- Windows live fire-drill: required after Monday walk-in if not yet green on work laptop.
- Internal URLs empty → Corporate knowledge not in DAG until crawl.
- SHIM empty → stuck on edge model until SSM.
- Public ratio high until internal re-ingest (ops quarantine may still ship).
- Confirm edge model slug `gpt-5.1` exists on company Codex account.

---

## 6 · Phase-2 questions for the other AI

1. What was hard-fail vs soft on first Corporate day?
2. Did cite-or-block fire correctly in real concerts?
3. Co-worker join kit used? Sessions ingest counts per user?
4. AWS SHIM latency / GSS availability?
5. Which max-agent N was stable without thrash?
6. What should auto-tune next (crawl depth, swarm size, golden compact size)?

---

## 7 · How to use this brief

| Side | Action |
|------|--------|
| **Codex (Corporate)** | End of day: say `day brief` or run `python scripts/airgap_brief.py` |
| **Grok 4.5 (lab)** | Read this MD offline; propose phase-2 PR plan |
| **Both** | Diff tomorrow's brief against today — performance trend |

**Files:**  
`.brain/state/briefs/DAY_BRIEF_{d.get('day')}.md`  
`vault/briefs/` when vault exists

---

*Air-gap only. No secrets. End of brief.*
"""


def write_brief() -> dict[str, Any]:
    d = gather()
    md = render(d)
    st = _ROOT / ".brain" / "state" / "briefs"
    st.mkdir(parents=True, exist_ok=True)
    day = d["day"]
    paths = {
        "md": st / f"DAY_BRIEF_{day}.md",
        "latest": st / "DAY_BRIEF_LATEST.md",
        "json": st / f"DAY_BRIEF_{day}.json",
    }
    paths["md"].write_text(md, encoding="utf-8")
    paths["latest"].write_text(md, encoding="utf-8")
    paths["json"].write_text(json.dumps(d, indent=2, default=str), encoding="utf-8")

    vault = _ROOT / "vault" / "briefs"
    if (_ROOT / "vault").is_dir():
        vault.mkdir(parents=True, exist_ok=True)
        vp = vault / f"DAY_BRIEF_{day}.md"
        vp.write_text(md, encoding="utf-8")
        paths["vault"] = vp

    # compact inject (~2k)
    compact = (
        f"AIRGAP_BRIEF {day} mode={((d.get('mode') or {}).get('mode'))} "
        f"band={(d.get('organism') or {}).get('band')} "
        f"ops={(d.get('ops') or {}).get('score')} "
        f"nodes={((d.get('golden') or {}).get('graph') or {}).get('nodes')} "
        f"full={paths['latest']}"
    )
    return {
        "ts": d["ts"],
        "paths": {k: str(v) for k, v in paths.items()},
        "compact": compact,
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    r = write_brief()
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print("Air-gap day brief:")
        for k, v in (r.get("paths") or {}).items():
            print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
