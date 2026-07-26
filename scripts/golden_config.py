#!/usr/bin/env python3
"""GOLDEN Corporate configuration — teach the model the complete control surface.

Not a human slideshow. This MD is law for Grok 4.5 / Codex so it can:
  - traverse local → internal crawl → AWS gov-region-1 without re-asking
  - onboard a co-worker: their sessions ingest, then they connect AWS and it works
  - never invent hosts/tokens; never lose the map

Writes (model-facing, max useful context):
  .brain/state/GOLDEN_CONFIG.md          # full teaching pack
  .brain/state/GOLDEN_CONFIG.compact.md  # SessionStart inject (size-capped)
  .brain/state/golden_config.json        # machine map (no secrets)
  vault/GOLDEN_CONFIG.md                 # if vault exists
  ~/.codex/prompts/private-brain-golden-config.md

  python golden_config.py
  python golden_config.py --json
  python golden_config.py --compact-chars 12000
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
sys.path.insert(0, str(_SCRIPTS))
os.environ.setdefault("PRIVATE_BRAIN_HOME", str(_ROOT))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _state() -> Path:
    p = _ROOT / ".brain" / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _j(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _host(url: str) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _safe_url(u: str) -> str:
    """Strip credentials/query for model-facing docs."""
    if not u:
        return ""
    try:
        p = urlparse(u)
        net = p.hostname or ""
        path = p.path or ""
        return f"{p.scheme}://{net}{path}".rstrip("/")
    except Exception:
        return u.split("?")[0].split("@")[-1]


def gather() -> dict[str, Any]:
    st = _state()
    day1 = _j(st / "day1_map.json")
    organism = _j(st / "organism.json")
    cloud = _j(st / "cloud_ready.json")
    metrics = _j(st / "ops_metrics.json")
    routing = _j(_ROOT / "config" / "model_routing.json")
    ent_raw = {}
    try:
        import yaml  # type: ignore

        ep = _ROOT / "config" / "enterprise.yaml"
        if ep.exists():
            ent_raw = yaml.safe_load(ep.read_text(encoding="utf-8")) or {}
    except Exception:
        pass

    env = {
        "route": day1.get("route") or os.environ.get("PB_PACKAGE_ROUTE") or "headless",
        "program_id": os.environ.get("PB_PROGRAM_ID") or day1.get("program_id") or "",
        "classification": os.environ.get("PB_CLASSIFICATION") or day1.get("classification") or "INTERNAL",
        "pip_index": _safe_url(
            os.environ.get("PIP_INDEX_URL") or os.environ.get("PB_PIP_INDEX_URL") or ""
        ),
        "gitlab": _safe_url(os.environ.get("PB_GITLAB_URL") or day1.get("gitlab_url") or ""),
        "jira": _safe_url(os.environ.get("PB_JIRA_URL") or day1.get("jira_url") or ""),
        "confluence": _safe_url(
            os.environ.get("PB_CONFLUENCE_URL") or day1.get("confluence_url") or ""
        ),
        "aws_profile": os.environ.get("AWS_PROFILE") or day1.get("aws_profile") or "",
        "aws_region": os.environ.get("PB_AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or day1.get("aws_region")
        or "gov-region-1",
        "llm_shim": _safe_url(os.environ.get("PB_LLM_BASE_URL") or day1.get("llm_base_url") or ""),
        "opensearch": _safe_url(
            os.environ.get("PB_OPENSEARCH_ENDPOINT") or day1.get("opensearch_endpoint") or ""
        ),
        "neptune": _safe_url(
            os.environ.get("PB_NEPTUNE_ENDPOINT") or day1.get("neptune_endpoint") or ""
        ),
        "codex_home": os.environ.get("CODEX_HOME") or str(Path.home() / ".codex"),
        "brain_home": str(_ROOT),
        "godseye": os.environ.get("PB_GODSEYE", "1"),
        "max_agents": os.environ.get("PB_MAX_AGENTS") or os.environ.get("PB_SWARM_AGENTS") or "auto",
        "model_pref": os.environ.get("PB_MODEL_PREFERENCE")
        or day1.get("model_preference")
        or "enterprise-frontier-model",
    }
    hosts = []
    for u in (env["gitlab"], env["jira"], env["confluence"]):
        h = _host(u)
        if h and h not in hosts:
            hosts.append(h)
    for h in day1.get("allowlist_hosts") or []:
        if h and h not in hosts:
            hosts.append(h)

    graph = {}
    try:
        from brain_lib import status

        graph = status() or {}
    except Exception:
        pass
    vectors = {}
    try:
        from vector_manager import status as vs

        vectors = vs() or {}
    except Exception:
        pass
    purity = {}
    try:
        from enterprise import corpus_purity_audit

        purity = corpus_purity_audit(write=False) or {}
    except Exception:
        pass

    edge_m = ((routing.get("routing_edge") or {}).get("orchestrator") or {}).get("model") or "gpt-5.1"
    aws_m = ((routing.get("routing_aws_when_shim") or {}).get("orchestrator") or {}).get(
        "model"
    ) or "enterprise-frontier-model"

    return {
        "ts": _ts(),
        "platform": platform.platform(),
        "env": env,
        "hosts": hosts,
        "day1": {
            k: day1.get(k)
            for k in (
                "route",
                "route_label",
                "program_id",
                "classification",
                "godseye_wanted",
                "appgate_connected",
                "require_corporate-package-index",
            )
            if k in day1 or True
        },
        "organism": {
            "band": organism.get("band"),
            "alive": organism.get("alive"),
            "local_ready": organism.get("local_ready"),
            "max_agents": organism.get("max_agents"),
        },
        "cloud": cloud,
        "metrics": metrics,
        "graph": {
            "nodes": graph.get("node_count") or graph.get("nodes"),
            "edges": graph.get("edge_count") or graph.get("edges"),
            "by_source": graph.get("by_source") or {},
        },
        "vectors": {
            "vectors": vectors.get("vectors"),
            "parity": vectors.get("parity"),
            "embed_backend": vectors.get("embed_backend"),
        },
        "purity": {
            "pilot_ready": purity.get("pilot_ready"),
            "pilot_ops_ready": purity.get("pilot_ops_ready"),
            "public_ratio": purity.get("public_ratio"),
            "quarantine_coverage": purity.get("quarantine_coverage"),
        },
        "models": {
            "edge": edge_m,
            "aws_frontier": aws_m,
            "grok_lab": "grok-4.5",
            "note": "Corporate work = edge gpt-5.1 sovereign + AWS GSS 120B. Lab may use grok-4.5.",
        },
        "enterprise_yaml_keys": list(ent_raw.keys()) if isinstance(ent_raw, dict) else [],
        "complete": bool(
            env.get("program_id")
            and (env.get("route") or day1.get("route"))
        ),
    }


def render_golden_md(d: dict[str, Any]) -> str:
    e = d["env"]
    g = d["graph"]
    by = g.get("by_source") or {}
    src_rows = "\n".join(
        f"| {k} | {v} |" for k, v in sorted(by.items(), key=lambda x: -int(x[1] or 0))[:24]
    ) or "| — | 0 |"

    # Co-worker join: shareable non-secret map
    coworker_json = {
        "schema": "private-brain.coworker_join.v1",
        "program_id": e["program_id"],
        "classification": e["classification"],
        "package_route": e["route"],
        "pip_index_url": e["pip_index"],
        "aws_region": e["aws_region"],
        "aws_profile_hint": e["aws_profile"] or "<their SSO profile>",
        "llm_shim_pattern": e["llm_shim"] or "http://127.0.0.1:8443/v1",
        "opensearch_endpoint": e["opensearch"],
        "neptune_endpoint": e["neptune"],
        "gitlab_url": e["gitlab"],
        "jira_url": e["jira"],
        "confluence_url": e["confluence"],
        "allowlist_hosts": d["hosts"],
        "models": d["models"],
        "instructions": [
            "Install company Codex. Restore/keep your own .codex/sessions.",
            "Extract PrivateBrain-CORPORATE zip → windows\\ → START.ps1",
            "Import this golden map (or answer same interview once).",
            "Organism ingests YOUR sessions automatically — never share session files with secrets carelessly.",
            "Tokens: each person stores their own in secrets_store (DPAPI).",
            "Connect AppGate → organism crawls shared internal sources.",
            "Connect AWS (SSO + SSM SHIM) → same SHIM URL pattern → cloud plane just works.",
            "Daily: only run beastMode. No flag dance.",
        ],
    }

    return f"""# GOLDEN CONFIG — Corporate Private Brain (model law)

**Audience:** Grok 4.5 / Codex / any agent on this sideload.  
**Purpose:** You already know where knowledge lives. Traverse phases without re-interviewing.  
**Secrets:** NEVER invent tokens. NEVER print tokens. Each human owns secrets_store.  
**Generated:** `{d['ts']}` · platform `{d['platform']}`

---

## A. Absolute law (non-negotiable)

1. Private Brain is a **Codex sideload** — not a product CLI. User runs `START` once, then `beastMode` only.
2. **Evidence only.** Every factual claim cites `` `node_id` (T#) `` from the RAG-DAG. No cites → refuse / rewrite.
3. Prefer **non-public / non-quarantined** nodes under enterprise.
4. **beastMode = maximum agent deployment** toward one goal: local RAG-DAG then AWS gov-region-1 cloud RAG-DAG.
5. Missing Corporate Library / Jira / AWS = **soft degrade**. Never ground the pilot for unknown Corporate systems.
6. Models: edge **`{d['models']['edge']}`** (US sovereign on Corporate laptop). AWS **`{d['models']['aws_frontier']}`** via SHIM. Lab may use **`{d['models']['grok_lab']}`**. You are not free to pick random public models.

---

## B. Complete control surface (where ALL knowledge lives)

| Plane | Location | How you use it |
|-------|----------|----------------|
| **Codex sessions** | `{e['codex_home']}/sessions` | Auto-ingest every organism wake + SessionStart |
| **Local RAG-DAG** | `{e['brain_home']}/.brain` | nodes/edges/audit/vectors — authoritative memory |
| **Packages** | route=`{e['route']}` index=`{e['pip_index'] or 'HEADLESS/stdlib'}` | pygame/GL from Corporate Library when present; core is stdlib |
| **Code** | GitLab `{e['gitlab'] or 'NOT SET'}` | crawl polite; AppGate first |
| **Plans/issues** | Jira `{e['jira'] or 'NOT SET'}` | crawl polite |
| **Wiki** | Confluence `{e['confluence'] or 'NOT SET'}` | crawl polite |
| **AWS region** | **`{e['aws_region']}`** | never commercial mix with Government Cloud data |
| **LLM SHIM** | `{e['llm_shim'] or 'NOT SET — edge only'}` | after SSM port-forward |
| **OpenSearch** | `{e['opensearch'] or 'local vectors only'}` | cloud vector plane |
| **Neptune** | `{e['neptune'] or 'local graph only'}` | cloud graph plane |
| **Program** | `{e['program_id']}` · class `{e['classification']}` | stamp preference on retrieve |
| **Allowlist hosts** | {', '.join(d['hosts']) or 'any non-public'} | enterprise crawl policy |
| **GodsEye** | PB_GODSEYE={e['godseye']} | prefer-on; user close sticks; "show GodsEye" reopens |
| **Max agents** | {e['max_agents']} (cap 256) | shared-graph swarm, money unconstrained |

### Live graph (now)

| metric | value |
|--------|------:|
| nodes | {g.get('nodes') or '—'} |
| edges | {g.get('edges') or '—'} |
| vectors | {d['vectors'].get('vectors') or '—'} |
| parity | {d['vectors'].get('parity')} |
| pilot_ops_ready | {d['purity'].get('pilot_ops_ready')} |
| pilot_ready | {d['purity'].get('pilot_ready')} |
| public_ratio | {d['purity'].get('public_ratio')} |
| organism | {d['organism'].get('band')} alive={d['organism'].get('alive')} |

| source | nodes |
|--------|------:|
{src_rows}

---

## C. Phase machine (traverse in order — do not invent new dances)

```text
PHASE 0  SESSIONS     → ingest THIS user's .codex/sessions into graph
PHASE 1  MAP          → golden config known (this file). Skip re-interview if complete.
PHASE 2  LOCAL        → heal · GodsEye · polite crawl · max swarm · LOCAL_READY
PHASE 3  AWS          → gov-region-1 · SHIM · OpenSearch · Neptune · switch to GSS routing
PHASE 4  ALIVE        → water flowing · daily beastMode only
PHASE 5  COWORKER     → join map + their sessions + their AWS — magic (below)
```

When user asks to crawl / heal / mission / metrics: **do the phase**, do not dump CLI flag tutorials.

---

## D. PHASE 5 — Co-worker join (true automation)

**Goal:** Add a co-worker so *their* Codex sessions are ingested; then they connect to AWS and it just works. No 12-step dance.

### What the pilot (you) already know
- Shared Corporate surface: package route, GitLab/Jira/Confluence hosts, AWS region, SHIM pattern, data-plane endpoints, program id.
- What you **never** share: tokens, session files with secrets, day1.env with plaintext secrets.

### Co-worker join kit (share this JSON — no secrets)

```json
{json.dumps(coworker_json, indent=2)}
```

### What co-worker does (human steps — only these)

1. Install company **Codex**. Keep **their own** `%USERPROFILE%\\.codex\\sessions` (or restore their backup).
2. Extract **same** `PrivateBrain-CORPORATE-*.zip` → `windows\\`.
3. Run **`START.ps1`** once. If join kit present (`golden_join.json` next to START or imported), **skip re-interview** and apply shared map.
4. Organism **auto-ingests their sessions** into **their** local RAG-DAG (or shared dual-write when cloud is live).
5. They store **their** GitLab/Jira tokens in **their** secrets_store.
6. AppGate up → crawls use **same host map**.
7. AWS SSO with **their** profile → same region + SHIM pattern → `beastMode` → cloud plane.
8. Daily forever: **`beastMode` only**.

### What you (the model) must do when asked “add a co-worker”

1. Emit/update `golden_join.json` from this golden config (no secrets).
2. Tell them the 8 steps above — nothing else.
3. After they run START, verify phases 0–2 on their machine via doctor/organism language, not flag spam.
4. When they set `PB_LLM_BASE_URL` / AWS profile, treat PHASE 3 as active: prefer GSS routing, cloud dual-write when endpoints exist.
5. Never require them to re-derive GitLab/Jira/Corporate Library URLs if join kit was applied.

### Shared brain later (cloud magic)

When OpenSearch + Neptune + SHIM are live for the program:
- Local filesystem DAG is edge cache.
- Co-workers connect AWS → same data plane → same program graph without USB corpus.
- Session ingest remains **per-user edge** first, then optional dual-write of non-secret crumbs.

---

## E. Operator phrases → phase actions

| User says | You do |
|-----------|--------|
| “get me going” / “wake up” | PHASE 0–4 via organism; open Codex |
| “show GodsEye” | force GodsEye reopen |
| “show golden config” / “control surface” | refresh this pack; inject into context |
| “add co-worker” / “onboard teammate” | PHASE 5 — emit join kit + 8 steps |
| “connect AWS” | confirm region gov-region-1, SHIM, profile; PHASE 3 |
| “ingest sessions” | force smart_discover sessions |
| “crawl gitlab” | polite ingest_url with known URL |
| any factual question | retrieve concert → cite node_ids → stop if uncited |

---

## F. Files that ARE the configuration

| Path | Role |
|------|------|
| `.brain/state/GOLDEN_CONFIG.md` | **This law** (full) |
| `.brain/state/GOLDEN_CONFIG.compact.md` | SessionStart inject |
| `.brain/state/golden_config.json` | machine map |
| `.brain/state/golden_join.json` | co-worker share pack |
| `.brain/state/day1_map.json` | original interview (no secrets) |
| `.brain/state/organism.json` | last water-pipe |
| `config/model_routing.json` | edge vs AWS models |
| `config/aws_shim.yaml` | Government Cloud SHIM policy |
| `beast-enterprise.md` | enterprise law |

---

## G. Gaps (do not hallucinate them away)

"""


def render_gaps(d: dict[str, Any]) -> str:
    e = d["env"]
    gaps = []
    if not e.get("pip_index") and e.get("route") not in ("headless",):
        gaps.append("Package index empty — core headless OK; request Corporate Library for GodsEye deps.")
    if not e.get("gitlab") and not e.get("jira") and not e.get("confluence"):
        gaps.append("No internal source URLs — Corporate corpus not mapped; ask once or import join kit.")
    if not e.get("llm_shim"):
        gaps.append("No LLM SHIM — stay on edge model until SSM forward.")
    if not e.get("opensearch"):
        gaps.append("No OpenSearch — vectors local only.")
    if not e.get("neptune"):
        gaps.append("No Neptune — graph local only.")
    if d["purity"].get("public_ratio") is not None:
        try:
            if float(d["purity"]["public_ratio"]) >= 0.15:
                gaps.append(
                    f"public_ratio={d['purity']['public_ratio']} — ops quarantine may still be green; "
                    "strict purity needs internal re-ingest."
                )
        except Exception:
            pass
    if not gaps:
        return "- No structural gaps. Proceed to daily beastMode / co-worker join as needed.\n"
    return "\n".join(f"- {g}" for g in gaps) + "\n"


def render_compact(d: dict[str, Any], max_chars: int = 12000) -> str:
    """Dense inject for SessionStart — fill available context budget, not a pamphlet."""
    e = d["env"]
    full = (
        f"# GOLDEN CONFIG (compact) · {d['ts']}\n"
        f"LAW: sideload only · cite node_ids · no secret print · soft-degrade unknown Corporate systems.\n"
        f"PROGRAM: {e['program_id']} · {e['classification']} · route={e['route']}\n"
        f"SESSIONS: {e['codex_home']}/sessions → auto-ingest\n"
        f"BRAIN: {e['brain_home']}/.brain · nodes={d['graph'].get('nodes')} · "
        f"vec={d['vectors'].get('vectors')} parity={d['vectors'].get('parity')}\n"
        f"SOURCES: gitlab={e['gitlab'] or '—'} jira={e['jira'] or '—'} conf={e['confluence'] or '—'}\n"
        f"HOSTS: {', '.join(d['hosts']) or '—'}\n"
        f"AWS: region={e['aws_region']} profile={e['aws_profile'] or '—'} "
        f"shim={e['llm_shim'] or '—'} os={e['opensearch'] or '—'} nep={e['neptune'] or '—'}\n"
        f"MODELS: edge={d['models']['edge']} aws={d['models']['aws_frontier']} lab={d['models']['grok_lab']}\n"
        f"AGENTS: max={e['max_agents']} · GodsEye={e['godseye']}\n"
        f"PHASES: 0 sessions → 1 map(this) → 2 local → 3 AWS → 4 alive → 5 coworker join\n"
        f"COWORKER: emit golden_join.json (no secrets) → they START → sessions ingest → AppGate → AWS SHIM → beastMode only\n"
        f"USER PHRASES: show GodsEye · show golden config · add co-worker · connect AWS\n"
        f"ALIVE: band={d['organism'].get('band')} pilot_ops={d['purity'].get('pilot_ops_ready')}\n"
        f"FULL: .brain/state/GOLDEN_CONFIG.md\n"
    )
    if len(full) > max_chars:
        return full[: max_chars - 20] + "\n…[truncated]\n"
    # pad useful source table if room
    by = d["graph"].get("by_source") or {}
    if by and len(full) < max_chars - 200:
        extra = "SOURCES_COUNTS: " + ", ".join(f"{k}={v}" for k, v in list(by.items())[:15]) + "\n"
        if len(full) + len(extra) <= max_chars:
            full += extra
    return full


def write_golden(*, compact_chars: int = 12000, open_ui: bool = False) -> dict[str, Any]:
    d = gather()
    md = render_golden_md(d) + render_gaps(d)
    md += (
        "\n---\n\n*End golden config. When incomplete fields exist, ask once, persist, never thrash.*\n"
    )
    compact = render_compact(d, max_chars=compact_chars)
    st = _state()
    paths = {
        "md": st / "GOLDEN_CONFIG.md",
        "compact": st / "GOLDEN_CONFIG.compact.md",
        "json": st / "golden_config.json",
        "join": st / "golden_join.json",
    }
    paths["md"].write_text(md, encoding="utf-8")
    paths["compact"].write_text(compact, encoding="utf-8")

    # machine map — strip anything secret-like
    machine = {
        "ts": d["ts"],
        "schema": "private-brain.golden_config.v1",
        "env": d["env"],
        "hosts": d["hosts"],
        "models": d["models"],
        "graph": d["graph"],
        "vectors": d["vectors"],
        "purity": d["purity"],
        "organism": d["organism"],
        "complete": d["complete"],
    }
    paths["json"].write_text(json.dumps(machine, indent=2), encoding="utf-8")

    # co-worker join pack (explicit, shareable)
    join = {
        "schema": "private-brain.coworker_join.v1",
        "ts": d["ts"],
        "program_id": d["env"]["program_id"],
        "classification": d["env"]["classification"],
        "package_route": d["env"]["route"],
        "pip_index_url": d["env"]["pip_index"],
        "aws_region": d["env"]["aws_region"],
        "aws_profile_hint": d["env"]["aws_profile"] or "",
        "llm_shim_url": d["env"]["llm_shim"],
        "opensearch_endpoint": d["env"]["opensearch"],
        "neptune_endpoint": d["env"]["neptune"],
        "gitlab_url": d["env"]["gitlab"],
        "jira_url": d["env"]["jira"],
        "confluence_url": d["env"]["confluence"],
        "allowlist_hosts": d["hosts"],
        "models": d["models"],
        "max_agents": d["env"]["max_agents"],
        "godseye_default": d["env"]["godseye"],
        "human_steps": [
            "Install Codex; keep your own .codex/sessions",
            "Extract PrivateBrain-CORPORATE zip → windows\\ → START.ps1",
            "Place this file as windows/golden_join.json OR brain .brain/state/golden_join.json before START",
            "Organism applies map + ingests YOUR sessions",
            "Put YOUR tokens in secrets_store only",
            "AppGate → internal crawl uses shared URLs",
            "AWS SSO + SSM SHIM same pattern → beastMode",
            "Daily: beastMode only",
        ],
    }
    paths["join"].write_text(json.dumps(join, indent=2), encoding="utf-8")

    vault = _ROOT / "vault"
    if vault.is_dir():
        vp = vault / "GOLDEN_CONFIG.md"
        vp.write_text(md, encoding="utf-8")
        paths["vault"] = vp

    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    try:
        prompts = codex / "prompts"
        prompts.mkdir(parents=True, exist_ok=True)
        cp = prompts / "private-brain-golden-config.md"
        cp.write_text(md, encoding="utf-8")
        paths["codex_prompt"] = cp
    except Exception:
        pass

    # also mirror join next to kit if PB_KIT_ROOT set
    kit = os.environ.get("PB_KIT_ROOT")
    if kit:
        try:
            kp = Path(kit) / "golden_join.json"
            kp.write_text(json.dumps(join, indent=2), encoding="utf-8")
            paths["kit_join"] = kp
        except Exception:
            pass

    return {
        "ts": d["ts"],
        "complete": d["complete"],
        "paths": {k: str(v) for k, v in paths.items()},
        "compact_chars": len(compact),
        "full_chars": len(md),
        "coworker_join": str(paths["join"]),
    }


def load_compact_for_inject(max_chars: int = 12000) -> str:
    """For SessionStart: refresh if stale/missing, return compact MD."""
    st = _state()
    compact = st / "GOLDEN_CONFIG.compact.md"
    full = st / "GOLDEN_CONFIG.md"
    # refresh if missing or golden incomplete / older than 1h when map exists
    need = not compact.exists() or not full.exists()
    if not need:
        try:
            age = __import__("time").time() - compact.stat().st_mtime
            if age > 3600:
                need = True
        except Exception:
            need = True
    if need:
        try:
            write_golden(compact_chars=max_chars, open_ui=False)
        except Exception:
            pass
    if compact.exists():
        t = compact.read_text(encoding="utf-8")
        return t[:max_chars]
    if full.exists():
        return full.read_text(encoding="utf-8")[:max_chars]
    return (
        "# GOLDEN CONFIG missing — run organism or: python scripts/golden_config.py\n"
        "Until then: cite node_ids, soft-degrade unknown Corporate systems, beastMode only.\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Write golden Corporate config for model teaching")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--compact-chars", type=int, default=12000)
    args = ap.parse_args()
    r = write_golden(compact_chars=args.compact_chars)
    if args.json:
        print(json.dumps(r, indent=2))
    else:
        print("==============================================")
        print(" GOLDEN CONFIG written (model law)")
        print("==============================================")
        for k, v in (r.get("paths") or {}).items():
            print(f"  {k:14} {v}")
        print(f"  compact_chars {r.get('compact_chars')}  full_chars {r.get('full_chars')}")
        print("  Co-worker pack:", r.get("coworker_join"))
        print("==============================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
