#!/usr/bin/env python3
"""Phase-2 handoff — air-gapped directive from Codex (gpt-5.1) → Grok 4.5 parent.

Pure MD. No secrets. Designed so Monday night you sit Grok next to the laptop
with only this file (and day brief) and Grok can generate phase-2 work.

  python phase2_handoff.py
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


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _j(p: Path) -> Any:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_handoff() -> dict[str, Any]:
    # Phase-2 requires golden map (Phase-1 law) — write if missing
    try:
        from golden_config import write_golden
        st = _state() if "_state" in dir() else None
        from brain_lib import STATE_DIR
        if not (STATE_DIR / "golden_config.json").exists() or not (STATE_DIR / "golden_join.json").exists():
            write_golden()
    except Exception:
        try:
            from golden_config import write_golden
            write_golden()
        except Exception:
            pass

    st = _ROOT / ".brain" / "state"
    org = _j(st / "organism.json")
    ops = _j(st / "ops_metrics.json")
    gold = _j(st / "golden_config.json")
    heal = _j(st / "heal_ledger.json")
    fire = _j(st / "fire_drill.json")
    mode = _j(st / "conversation_mode.json")

    # ensure day brief exists
    try:
        from airgap_brief import write_brief

        brief = write_brief()
    except Exception as e:
        brief = {"error": str(e)}

    md = f"""# PHASE-2 HANDOFF — Codex (gpt-5.1 sovereign) → Grok 4.5

**From:** Private Brain sideload on Corporate/edge laptop (GPT-5.1 US sovereign)  
**To:** Grok 4.5 (parent architect)  
**UTC:** `{_ts()}`  
**Channel:** air-gapped MD only — no tokens, no day1.env, no session dumps  

You are the parent. Codex is the edge learner with keys to the kingdom (Corporate Package Index/GitLab/Jira/Confluence/AWS APIs + full system access). Read this + `DAY_BRIEF_LATEST.md` and produce **Phase-2 plan + concrete patches**.

---

## Directive (what Codex is becoming)

A **self-contained, self-learning, self-healing, self-configuring** super-app that sideloads Codex so that:

1. Pure **conversation** drives forensics, crawl, heal, metrics, co-worker join — **zero flags** for the human.
2. **Normal mode** turns RAG off; **beast mode** turns it back on.
3. Full system access (local admin) + sandbox bypass; heal ledger prevents repair thrash.
4. When human navigates Corporate Library, Codex uses **Corporate Package Index Corporate Package Index API** knowledge; same for GitLab/Jira/Confluence REST.
5. Golden config is model law; co-worker gets `golden_join.json` → their sessions ingest → AWS connect → magic.
6. Edge model gpt-5.1; cloud enterprise-frontier-model gov-region-1 when SHIM exists.

---

## Live snapshot (machine)

```json
{json.dumps({
  "mode": mode,
  "organism_band": org.get("band"),
  "alive": org.get("alive"),
  "ops": ops.get("score"),
  "graph": gold.get("graph"),
  "env_nonsecret": gold.get("env"),
  "models": gold.get("models"),
  "fire_drill": {"band": fire.get("band"), "ok": fire.get("ok")},
  "heal_ledger": {
    "healed": len((heal or {}).get("healed") or {}),
    "failed": len((heal or {}).get("failed") or {}),
  },
  "day_brief": brief.get("paths") if isinstance(brief, dict) else brief,
}, indent=2, default=str)[:6000]}
```

---

## What worked (assume true if band WATER_FLOWING / fire green)

- Organism water-pipe, golden config inject, conversational mode switch
- Full danger-full-access enterprise profile + CLI bypass
- Air-gap day brief path
- Kingdom keys doc (API surface)

## What Monday must prove (fill after walk-in)

- [ ] gpt-5.1 accepted by company Codex account  
- [ ] Tools run with **zero permission popups** under local admin  
- [ ] Sessions restored + ingested  
- [ ] Corporate Library Corporate Package Index pip works or conscious headless  
- [ ] At least one internal API crawl (GitLab/Jira/Conf) with AppGate  
- [ ] Conversational forensics: human said “fire drill” / “doctor” / “heal” without flags  
- [ ] Day brief generated EOD for this handoff  

## Gaps for Phase-2 design (Grok: prioritize)

1. Real multi-user dual-write when OpenSearch/Neptune live  
2. Corporate Package Index/GitLab/Jira/Confluence client modules hardened + rate-limit policy as first-class agents  
3. Heal ledger coverage for every access-class failure  
4. Reduce SessionStart inject pressure without losing kingdom keys  
5. True multi-agent LLM fan-out if Codex multi_agent API allows  
6. Corporate Library package discovery via Corporate Package Index AQL when token present  
7. Simulation harness: conversational ops suite (no flags) as regression  

---

## Phase-2 output format (Grok must return)

1. Ordered PR plan (files + why)  
2. Any new conversational phrases  
3. Metrics to add to day brief  
4. Risks to human-life zero-fail pilot path  

---

## Files to read together

- `.brain/state/briefs/DAY_BRIEF_LATEST.md`
- `.brain/state/GOLDEN_CONFIG.md`
- `docs/KINGDOM_KEYS.md`
- this file

*End handoff. Parent AI owns phase-2 architecture.*
"""

    out_dir = st / "briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "md": out_dir / "PHASE2_HANDOFF.md",
        "latest": out_dir / "PHASE2_HANDOFF_LATEST.md",
    }
    paths["md"].write_text(md, encoding="utf-8")
    paths["latest"].write_text(md, encoding="utf-8")
    vault = _ROOT / "vault" / "briefs"
    if (_ROOT / "vault").is_dir():
        vault.mkdir(parents=True, exist_ok=True)
        vp = vault / "PHASE2_HANDOFF.md"
        vp.write_text(md, encoding="utf-8")
        paths["vault"] = vp
    return {"paths": {k: str(v) for k, v in paths.items()}, "preview": md[:4000]}


def main() -> int:
    r = write_handoff()
    print(json.dumps(r["paths"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
