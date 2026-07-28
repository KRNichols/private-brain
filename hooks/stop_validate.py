#!/usr/bin/env python3
"""Codex Stop hook — force one more pass if answer ignored brain evidence.

Codex 0.144.x Stop stdout contract (strict):
  Allowed keys only: continue, decision, reason, systemMessage, stopReason, suppressOutput.
  Unsupported fields (e.g. hookSpecificOutput) → "invalid stop hook JSON" on Windows/CLI.
  Exit 0 always with pure JSON on stdout. Never print logs/tracebacks to stdout.

Developer handoff (2026-07-28):
  - Consume current evidence/workflow bundle, not only stale last_dag.
  - Exempt non-factual operational acknowledgements (beast/normal/health/hooks).
  - Prefer T0/T1 source evidence; validate cited node IDs against graph when possible.
  - Require citations only for consequential source-derived factual claims.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

HOME = Path.home()
BRAIN_HOME = Path(
    os.environ.get("PRIVATE_BRAIN_HOME")
    or str(Path(os.environ.get("CODEX_HOME", HOME / ".codex")) / "private-brain")
).resolve()
SCRIPTS = BRAIN_HOME / "scripts"
sys.path.insert(0, str(SCRIPTS))
os.environ["PRIVATE_BRAIN_HOME"] = str(BRAIN_HOME)

_flag = BRAIN_HOME / ".brain" / "state" / "enterprise.on"
if _flag.exists() and not os.environ.get("PB_ENTERPRISE"):
    os.environ["PB_ENTERPRISE"] = "1"


def _emit(obj: dict) -> int:
    """Write minimal Codex-legal Stop JSON. Strip unknown keys hard."""
    allowed = {"continue", "decision", "reason", "systemMessage", "stopReason", "suppressOutput"}
    clean = {k: v for k, v in obj.items() if k in allowed}
    if clean.get("decision") == "block":
        clean.pop("continue", None)
        if "reason" not in clean:
            clean["reason"] = "Private Brain: rewrite with evidence cites."
    else:
        clean = {"continue": True}
    try:
        sys.stdout.write(json.dumps(clean, ensure_ascii=True, separators=(",", ":")))
        sys.stdout.flush()
    except Exception:
        sys.stdout.write('{"continue":true}')
        try:
            sys.stdout.flush()
        except Exception:
            pass
    return 0


# Operational / non-factual acknowledgements — no citation required.
_OPS_EXACT = re.compile(
    r"^\s*("
    r"beast\s+mode\s+is\s+(already\s+)?active\.?"
    r"|beast\s+mode\s+(enabled|on|activated|re-?enabled)\.?"
    r"|normal\s+mode\s+(is\s+)?(active|on|enabled)\.?"
    r"|rag(-dag)?\s+(is\s+)?(off|on|disabled|enabled)\.?"
    r"|private\s+brain:\s*(normal|beast).*"
    r"|hooks?\s+(ok|healthy|installed|present|configured)\.?"
    r"|godseye\s+(started|starting|enabled|disabled|dismissed|already).*"
    r"|ok\.?"
    r"|done\.?"
    r"|acknowledged\.?"
    r"|workflow\s+(progress|started|complete|running).*"
    r"|health\s*(check\s*)?(ok|healthy|pass(ed)?)\.?"
    r"|no\s+graph\s+evidence\s*[—\-–]\s*refuse.*"
    r"|i\s+(can'?t|cannot)\s+answer\s+without\s+evidence.*"
    r")\s*$",
    re.IGNORECASE | re.DOTALL,
)

_OPS_SUBSTRINGS = (
    "beast mode is already active",
    "beast mode is active",
    "beast mode enabled",
    "beast mode on",
    "normal mode is active",
    "normal mode enabled",
    "rag-dag is off",
    "rag-dag is on",
    "rag is off",
    "rag is on",
    "mode=normal",
    "mode=beast",
    "hooks installed",
    "hooks present",
    "hook status",
    "godseye: flags on",
    "godseye requested",
    "launch via beastmode",
    "workflow progress",
    "command acknowledged",
    "health confirmation",
    "health ok",
    "doctor: ok",
    "no graph evidence — refuse",
    "no graph evidence - refuse",
    "refuse ungrounded",
    "without evidence i must refuse",
)


def _is_operational_ack(msg: str) -> bool:
    """True for non-factual operational / mode / health / hook acknowledgements."""
    text = (msg or "").strip()
    if not text:
        return True
    # Short pure acknowledgements
    if len(text) <= 240 and _OPS_EXACT.match(text):
        return True
    low = text.lower()
    if any(s in low for s in _OPS_SUBSTRINGS):
        # Still require cites if message also makes graph-derived factual claims
        if _looks_like_source_claim(low) and len(text) > 280:
            return False
        return True
    # Very short mode flips / confirmations
    if len(text) <= 80 and any(
        k in low
        for k in (
            "beast mode",
            "normal mode",
            "acknowledged",
            "hooks ok",
            "status ok",
            "already active",
        )
    ):
        return True
    return False


def _looks_like_source_claim(low: str) -> bool:
    """Heuristic: message asserts facts from corporate sources / graph."""
    markers = (
        "according to",
        "the page says",
        "confluence",
        "gitlab",
        "jira",
        "requirement",
        "the graph shows",
        "node count",
        "from the export",
        "per the document",
        "the code defines",
        "implements",
        "mr !",
        "merge request",
        "ticket ",
        "story ",
        "epic ",
    )
    return any(m in low for m in markers)


def _load_json(path: Path) -> Any:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _evidence_from_obj(obj: Any, *, default_tier: str = "T1") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not obj:
        return out
    if isinstance(obj, list):
        for e in obj:
            if isinstance(e, dict) and e.get("id"):
                out.append(
                    {
                        "id": str(e["id"]),
                        "tier": e.get("tier") or default_tier,
                        "source": e.get("source") or e.get("type") or "",
                    }
                )
            elif isinstance(e, str) and e.strip():
                out.append({"id": e.strip(), "tier": default_tier, "source": ""})
        return out
    if isinstance(obj, dict):
        for key in ("evidence", "nodes", "cites", "node_ids", "ids"):
            if key in obj:
                out.extend(_evidence_from_obj(obj[key], default_tier=default_tier))
        # single id
        if obj.get("id") and not out:
            out.append(
                {
                    "id": str(obj["id"]),
                    "tier": obj.get("tier") or default_tier,
                    "source": obj.get("source") or "",
                }
            )
    return out


def _merge_current_evidence(state_dir: Path) -> list[dict[str, Any]]:
    """Merge last_dag + current workflow/ingest/report evidence bundles."""
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []

    def add_all(items: list[dict[str, Any]]) -> None:
        for e in items:
            eid = str(e.get("id") or "").strip()
            if not eid or eid in seen:
                continue
            seen.add(eid)
            merged.append(e)

    # Primary: last_dag retrieve evidence
    last_dag = _load_json(state_dir / "last_dag.json") or {}
    if isinstance(last_dag, dict):
        add_all(_evidence_from_obj((last_dag.get("retrieve") or {}).get("evidence")))
        add_all(_evidence_from_obj(last_dag.get("evidence")))

    # Current turn / UPS evidence handoff
    for name in (
        "current_evidence.json",
        "ups_evidence.json",
        "workflow_evidence.json",
        "ingest_report_evidence.json",
        "page_ingest_report.json",
        "last_retrieve.json",
        "e2e_report_evidence.json",
        "stop_evidence_bundle.json",
    ):
        obj = _load_json(state_dir / name)
        if obj is None:
            continue
        if isinstance(obj, dict) and "evidence" in obj:
            add_all(_evidence_from_obj(obj.get("evidence")))
        else:
            add_all(_evidence_from_obj(obj))

    # Targeted source evidence files (Confluence/Jira/GitLab/report IDs)
    for name in (
        "confluence_evidence.json",
        "jira_evidence.json",
        "gitlab_evidence.json",
        "neoj_exports_reconciliation.json",
        "local_ingest_neoj_exports.json",
    ):
        obj = _load_json(state_dir / name)
        if isinstance(obj, dict):
            # reconciliation may list node ids
            for key in ("evidence", "node_ids", "page_ids", "local_export_ids", "nodes"):
                if key in obj:
                    add_all(_evidence_from_obj(obj[key], default_tier="T0"))
            if obj.get("id"):
                add_all(_evidence_from_obj(obj, default_tier="T0"))

    # Prefer T0/T1 first
    def tier_rank(e: dict[str, Any]) -> int:
        t = str(e.get("tier") or "T3").upper()
        order = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}
        return order.get(t, 9)

    merged.sort(key=tier_rank)
    return merged[:64]


def _cited_ids_in_message(msg: str) -> list[str]:
    """Extract backtick-wrapped node-like ids from the assistant message."""
    if not msg:
        return []
    # `confluence:page:123` or `gitlab:...` etc.
    found = re.findall(r"`([A-Za-z0-9_.:/\-]{3,160})`", msg)
    return list(dict.fromkeys(found))


def _graph_has_node(node_id: str) -> bool:
    """Best-effort: does the graph know this node id?"""
    try:
        from brain_lib import get_node  # type: ignore

        n = get_node(node_id)
        return bool(n)
    except Exception:
        pass
    try:
        from brain_lib import read_json, STATE_DIR  # type: ignore

        # Some installs expose nodes index
        idx = read_json(STATE_DIR / "nodes_index.json") or {}
        if isinstance(idx, dict) and node_id in idx:
            return True
        if isinstance(idx, dict) and node_id in (idx.get("ids") or []):
            return True
    except Exception:
        pass
    # State-side evidence files listing this id count as current evidence
    try:
        state = BRAIN_HOME / ".brain" / "state"
        for p in state.glob("*.json"):
            try:
                raw = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if f'"{node_id}"' in raw or f"`{node_id}`" in raw or node_id in raw:
                # cheap presence — avoid false positives on tiny ids
                if len(node_id) >= 8:
                    return True
    except Exception:
        pass
    return False


def main() -> int:
    try:
        raw = (
            sys.stdin.buffer.read().decode("utf-8", errors="replace")
            if hasattr(sys.stdin, "buffer")
            else sys.stdin.read()
        )
    except Exception:
        raw = ""
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    if payload.get("stop_hook_active"):
        return _emit({"continue": True})

    last = payload.get("last_assistant_message") or ""
    if not isinstance(last, str):
        last = str(last or "")

    try:
        from brain_lib import STATE_DIR, read_json  # type: ignore

        rag_off = (STATE_DIR / "rag.off").exists()
        mode_path = STATE_DIR / "conversation_mode.json"
        if mode_path.exists():
            try:
                if json.loads(mode_path.read_text(encoding="utf-8")).get("mode") == "normal":
                    rag_off = True
            except Exception:
                pass
        if rag_off:
            return _emit({"continue": True})

        # Operational acknowledgements — never block
        if _is_operational_ack(last):
            return _emit({"continue": True})

        if (STATE_DIR / "enterprise.on").exists():
            os.environ["PB_ENTERPRISE"] = "1"

        evidence = _merge_current_evidence(STATE_DIR)

        # If message cites concrete node ids that exist in graph/state, treat as current evidence
        cited_in_msg = _cited_ids_in_message(last)
        for cid in cited_in_msg:
            if any(str(e.get("id")) == cid for e in evidence):
                continue
            if _graph_has_node(cid) or cid.startswith(
                ("confluence:", "jira:", "gitlab:", "github:", "page:", "chunk:", "report:", "export:")
            ):
                evidence.append({"id": cid, "tier": "T0", "source": "message_cite"})

        try:
            from enterprise import citation_gate, is_enterprise  # type: ignore
        except Exception as e:
            if (STATE_DIR / "enterprise.on").exists() or os.environ.get("PB_ENTERPRISE") == "1":
                return _emit(
                    {
                        "decision": "block",
                        "reason": (
                            f"Private Brain ENTERPRISE: citation gate unavailable ({e}). "
                            "Refuse ungrounded answer."
                        ),
                    }
                )
            return _emit({"continue": True})

        # If still no evidence but message is not a source claim, allow (ops/chat)
        if not evidence and not _looks_like_source_claim(last.lower()):
            # Enterprise: only refuse when message looks like a factual source claim
            if is_enterprise() and _looks_like_source_claim(last.lower()):
                return _emit(
                    {
                        "decision": "block",
                        "reason": (
                            "Private Brain ENTERPRISE: no_evidence_refuse. "
                            "Refuse or crawl; do not invent graph facts."
                        ),
                    }
                )
            return _emit({"continue": True})

        gate = citation_gate(last, evidence)
        if not gate.get("ok"):
            # Pass if message already cites a real current node even if not in bundle
            if cited_in_msg and any(
                _graph_has_node(c)
                or c.startswith(("confluence:", "jira:", "gitlab:", "chunk:", "report:"))
                for c in cited_in_msg
            ):
                return _emit({"continue": True})
            ids = ", ".join(
                f"`{e.get('id')}` ({e.get('tier')})" for e in evidence[:6] if e.get("id")
            ) or "(no graph evidence — refuse or crawl)"
            mode = "ENTERPRISE" if is_enterprise() else "validator"
            return _emit(
                {
                    "decision": "block",
                    "reason": (
                        f"Private Brain {mode}: {gate.get('reason')}. "
                        f"Rewrite with `node_id` cites from: {ids}. "
                        "Never ask permission. Answer from the DAG only."
                    ),
                }
            )
        return _emit({"continue": True})
    except Exception as e:
        try:
            from brain_lib import STATE_DIR as SD  # type: ignore

            if (SD / "enterprise.on").exists() or os.environ.get("PB_ENTERPRISE") == "1":
                # Operational short messages still pass on unexpected errors
                if _is_operational_ack(last):
                    return _emit({"continue": True})
                return _emit(
                    {
                        "decision": "block",
                        "reason": f"Private Brain ENTERPRISE: stop validator error — refuse ({e}).",
                    }
                )
        except Exception:
            pass
        return _emit({"continue": True})


if __name__ == "__main__":
    raise SystemExit(main())
