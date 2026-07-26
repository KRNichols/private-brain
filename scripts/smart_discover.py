#!/usr/bin/env python3
"""
Smart discovery crawler — finds Codex workspace knowledge artifacts on disk
without hard-coding a single file list.

Discovery roots (in order):
  $CODEX_HOME
  %USERPROFILE%\\.codex  /  ~/.codex
  PRIVATE_BRAIN_HOME parent

What it hunts (recursive):
  sessions/YYYY/MM/DD/rollout-*.jsonl   ← primary conversation gold
  sessions/**/*.jsonl
  state_*.sqlite, logs_*.sqlite, memories_*.sqlite, goals_*.sqlite
  history.jsonl, config.toml (metadata only), AGENTS.md overlays

For each found artifact:
  classify → ingest → vectorize → rate → label/tag → audit

Then optional Codex-as-DAG-node validation via `codex exec`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audit_lib import audit, redact
from brain_lib import (
    STATE_DIR,
    build_snapshot,
    ensure_tree,
    read_json,
    status,
    utc_now,
    write_json,
)
from ingest_bus import ingest_edge, ingest_node
from knowledge_rater import rate_all
from vector_manager import reindex_all
from vector_manager import status as vec_status


@dataclass
class Find:
    path: Path
    kind: str  # rollout | sqlite_threads | sqlite_logs | sqlite_memories | agents_md | other_jsonl
    score: float  # discovery priority
    labels: list[str]
    tags: list[str]


def codex_homes() -> list[Path]:
    homes: list[Path] = []
    for key in ("CODEX_HOME",):
        v = os.environ.get(key)
        if v:
            homes.append(Path(v).expanduser())
    user = os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home())
    homes.append(Path(user) / ".codex")
    # de-dupe
    out = []
    seen = set()
    for h in homes:
        try:
            r = h.resolve()
        except Exception:
            r = h
        if r not in seen and r.is_dir():
            seen.add(r)
            out.append(r)
    return out


def classify(path: Path, rel: str) -> Find | None:
    name = path.name.lower()
    srel = rel.replace("\\", "/").lower()

    if name.startswith("rollout-") and name.endswith(".jsonl"):
        # boost if under sessions/yyyy/mm/dd
        score = 100.0
        if re.search(r"sessions/\d{4}/\d{2}/\d{2}/", srel):
            score = 120.0
        return Find(
            path,
            "rollout",
            score,
            labels=["session-rollout", "workspace-artifact"],
            tags=["codex", "session", "rollout", "auto-discovered", "corporate-workspace"],
        )

    if name.endswith(".jsonl") and "session" in srel:
        return Find(
            path,
            "other_jsonl",
            70.0,
            labels=["session-jsonl"],
            tags=["codex", "session", "auto-discovered"],
        )

    if name.startswith("state_") and name.endswith(".sqlite"):
        return Find(
            path,
            "sqlite_threads",
            90.0,
            labels=["codex-state-db"],
            tags=["codex", "sqlite", "threads", "auto-discovered"],
        )

    if name.startswith("logs_") and name.endswith(".sqlite"):
        return Find(
            path,
            "sqlite_logs",
            40.0,
            labels=["codex-logs-db"],
            tags=["codex", "sqlite", "logs", "auto-discovered"],
        )

    if name.startswith("memories_") and name.endswith(".sqlite"):
        return Find(
            path,
            "sqlite_memories",
            85.0,
            labels=["codex-memories-db"],
            tags=["codex", "sqlite", "memories", "auto-discovered"],
        )

    if name.startswith("goals_") and name.endswith(".sqlite"):
        return Find(
            path,
            "sqlite_goals",
            50.0,
            labels=["codex-goals-db"],
            tags=["codex", "sqlite", "goals", "auto-discovered"],
        )

    if name == "agents.md":
        return Find(
            path,
            "agents_md",
            30.0,
            labels=["agents-overlay"],
            tags=["codex", "agents", "auto-discovered"],
        )

    return None


def discover(max_files: int = 2000) -> list[Find]:
    finds: list[Find] = []
    for home in codex_homes():
        # Prefer walking sessions/ first (deep but bounded)
        sessions = home / "sessions"
        roots = []
        if sessions.is_dir():
            roots.append(sessions)
        roots.append(home)

        for root in roots:
            for dirpath, dirnames, filenames in os.walk(root):
                # skip huge/irrelevant
                base = Path(dirpath).name
                if base in ("node_modules", ".git", "vendor_imports", "plugins", "cache", "tmp", ".tmp", "Computer Use.app", "marketplace-cache", "ipc", "sqlite"):
                    dirnames[:] = []
                    continue
                # don't recurse into private-brain .brain content from home
                if "private-brain" in Path(dirpath).parts and ".brain" in Path(dirpath).parts:
                    dirnames[:] = []
                    continue
                for fn in filenames:
                    p = Path(dirpath) / fn
                    try:
                        rel = str(p.relative_to(home))
                    except ValueError:
                        rel = str(p)
                    f = classify(p, rel)
                    if f:
                        finds.append(f)
                    if len(finds) >= max_files * 3:
                        break
                if len(finds) >= max_files * 3:
                    break
    # unique by path, keep highest score
    best: dict[str, Find] = {}
    for f in finds:
        k = str(f.path.resolve())
        if k not in best or f.score > best[k].score:
            best[k] = f
    ordered = sorted(best.values(), key=lambda x: x.score, reverse=True)
    return ordered[:max_files]


# ── Ingest handlers ────────────────────────────────────────────


def _parse_rollout_messages(path: Path) -> dict[str, Any]:
    session_id = None
    meta: dict[str, Any] = {}
    turns: list[dict[str, Any]] = []
    n = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as e:
        return {"error": str(e)}

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        typ = obj.get("type")
        payload = obj.get("payload") or {}
        ts = obj.get("timestamp")
        if typ == "session_meta":
            session_id = payload.get("session_id") or payload.get("id")
            meta = {
                "cwd": payload.get("cwd"),
                "cli_version": payload.get("cli_version"),
                "source": payload.get("source"),
                "model_provider": payload.get("model_provider"),
                "started_at": payload.get("timestamp") or ts,
            }
            continue
        if typ == "turn_context":
            meta["model"] = payload.get("model") or meta.get("model")
            continue
        if typ == "response_item" and payload.get("type") == "message":
            role = payload.get("role")
            if role not in ("user", "assistant"):
                continue
            parts = []
            for c in payload.get("content") or []:
                if isinstance(c, dict):
                    parts.append(c.get("text") or c.get("input_text") or "")
            text = "\n".join(parts).strip()
            text, _ = redact(text)
            if len(text) < 8 or text.startswith("<recommended_plugins>"):
                continue
            n += 1
            turns.append({"role": role, "text": text[:20000], "ts": ts, "i": n})

    if not session_id:
        m = re.search(
            r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
            path.name,
            re.IGNORECASE,
        )
        session_id = m.group(1) if m else path.stem

    # date from path sessions/YYYY/MM/DD
    y = mth = d = None
    parts = path.parts
    for i, part in enumerate(parts):
        if part == "sessions" and i + 3 < len(parts):
            y, mth, d = parts[i + 1], parts[i + 2], parts[i + 3]
            break

    return {
        "session_id": session_id,
        "meta": meta,
        "turns": turns,
        "year": y,
        "month": mth,
        "day": d,
        "path": str(path),
    }


def ingest_rollout(f: Find, agent_id: str) -> dict[str, Any]:
    parsed = _parse_rollout_messages(f.path)
    if parsed.get("error"):
        return {"ok": False, "error": parsed["error"]}
    sid = parsed["session_id"]
    turns = parsed["turns"]
    title = turns[0]["text"][:120] if turns else sid
    title = re.sub(r"\s+", " ", title).strip()
    body = [f"# Codex Session {sid}", f"path: {parsed['path']}", f"model: {parsed['meta'].get('model')}", ""]
    for t in turns[:80]:
        body.append(f"## {t['role']}\n{t['text']}\n")
    content, _ = redact("\n".join(body))
    nid = f"codex:session:{sid}"
    ingest_node(
        nid,
        type="CodexSession",
        source="codex_session",
        title=title,
        tier="T3",
        tags=f.tags + (["dated"] if parsed.get("year") else []),
        labels=f.labels,
        content=content,
        props={
            "session_id": sid,
            "rollout_path": parsed["path"],
            "year": parsed.get("year"),
            "month": parsed.get("month"),
            "day": parsed.get("day"),
            "msg_count": len(turns),
            "cwd": parsed["meta"].get("cwd"),
            "model": parsed["meta"].get("model"),
            "ownership": "corporate_workspace_artifact",
            "discovery_score": f.score,
        },
        agent_id=agent_id,
        role="smart-discover",
    )
    turns_n = 0
    for t in turns[:40]:
        tid = f"codex:turn:{sid}:{t['i']}"
        ingest_node(
            tid,
            type="SessionTurn",
            source="codex_session",
            title=f"{t['role']}: {t['text'][:100]}",
            tier="T3",
            parent_id=nid,
            tags=f.tags + [t["role"]],
            labels=["session-turn"],
            content=t["text"],
            props={
                "session_id": sid,
                "role": t["role"],
                "ownership": "corporate_workspace_artifact",
            },
            agent_id=agent_id,
            role="smart-discover",
        )
        ingest_edge(nid, "HAS_TURN", tid, agent_id=agent_id)
        turns_n += 1
    return {"ok": True, "session": sid, "turns": turns_n}


def ingest_sqlite_threads(f: Find, agent_id: str) -> dict[str, Any]:
    n = 0
    try:
        con = sqlite3.connect(f"file:{f.path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        # discover tables
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "threads" not in tables:
            con.close()
            return {"ok": True, "skipped": True, "tables": tables}
        cols = [c[1] for c in con.execute("PRAGMA table_info(threads)").fetchall()]
        rows = con.execute("SELECT * FROM threads").fetchall()
        for r in rows:
            d = dict(r)
            sid = d.get("id")
            if not sid:
                continue
            title = d.get("title") or d.get("first_user_message") or d.get("preview") or sid
            title = re.sub(r"\s+", " ", str(title))[:200]
            body = json.dumps({k: d.get(k) for k in cols if k not in ()}, default=str)[:12000]
            body, _ = redact(body)
            ingest_node(
                f"codex:threadmeta:{sid}",
                type="CodexThreadMeta",
                source="codex_session",
                title=f"thread: {title}",
                tier="T3",
                tags=f.tags,
                labels=f.labels,
                content=body,
                props={
                    "session_id": sid,
                    "model": d.get("model"),
                    "cwd": d.get("cwd"),
                    "tokens_used": d.get("tokens_used"),
                    "rollout_path": d.get("rollout_path"),
                    "ownership": "corporate_workspace_artifact",
                    "discovery_score": f.score,
                },
                agent_id=agent_id,
                role="smart-discover",
            )
            # link to session if exists
            ingest_edge(f"codex:session:{sid}", "HAS_META", f"codex:threadmeta:{sid}", agent_id=agent_id)
            n += 1
        con.close()
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "threads": n}


def ingest_sqlite_memories(f: Find, agent_id: str) -> dict[str, Any]:
    n = 0
    try:
        con = sqlite3.connect(f"file:{f.path}?mode=ro", uri=True)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for table in tables:
            if table.startswith("sqlite_") or table.startswith("_"):
                continue
            try:
                rows = con.execute(f"SELECT * FROM [{table}] LIMIT 2000").fetchall()
                cols = [c[0] for c in con.execute(f"PRAGMA table_info([{table}])").fetchall()]
            except Exception:
                continue
            for i, row in enumerate(rows):
                d = {cols[j]: row[j] for j in range(min(len(cols), len(row)))}
                text = json.dumps(d, default=str)[:8000]
                text, _ = redact(text)
                if len(text) < 20:
                    continue
                nid = f"codex:memory:{table}:{i}:{abs(hash(text)) % 10**10}"
                ingest_node(
                    nid,
                    type="CodexMemory",
                    source="codex_session",
                    title=f"memory {table}#{i}",
                    tier="T3",
                    tags=f.tags + [table],
                    labels=f.labels,
                    content=text,
                    props={"table": table, "ownership": "corporate_workspace_artifact"},
                    agent_id=agent_id,
                    role="smart-discover",
                )
                n += 1
        con.close()
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "memories": n}


def ingest_agents_md(f: Find, agent_id: str) -> dict[str, Any]:
    try:
        text = f.path.read_text(encoding="utf-8", errors="ignore")[:20000]
    except OSError as e:
        return {"ok": False, "error": str(e)}
    text, _ = redact(text)
    nid = f"codex:agentsmd:{abs(hash(str(f.path))) % 10**10}"
    ingest_node(
        nid,
        type="AgentsOverlay",
        source="codex_session",
        title=f"AGENTS.md {f.path}",
        tier="T2",
        tags=f.tags,
        labels=f.labels,
        content=text,
        props={"path": str(f.path), "ownership": "corporate_workspace_artifact"},
        agent_id=agent_id,
        role="smart-discover",
    )
    return {"ok": True}


def ingest_find(f: Find, agent_id: str) -> dict[str, Any]:
    if f.kind == "rollout":
        return ingest_rollout(f, agent_id)
    if f.kind == "sqlite_threads":
        return ingest_sqlite_threads(f, agent_id)
    if f.kind == "sqlite_memories":
        return ingest_sqlite_memories(f, agent_id)
    if f.kind == "agents_md":
        return ingest_agents_md(f, agent_id)
    if f.kind in ("sqlite_logs", "sqlite_goals", "other_jsonl"):
        # light catalog of the file itself as an artifact pointer
        ingest_node(
            f"codex:artifact:{f.kind}:{abs(hash(str(f.path))) % 10**10}",
            type="CodexArtifact",
            source="codex_session",
            title=f"{f.kind}: {f.path.name}",
            tier="T3",
            tags=f.tags,
            labels=f.labels,
            content=f"Discovered artifact\npath={f.path}\nkind={f.kind}\nsize={f.path.stat().st_size}",
            props={"path": str(f.path), "kind": f.kind, "ownership": "corporate_workspace_artifact"},
            agent_id=agent_id,
            role="smart-discover",
        )
        return {"ok": True, "cataloged_pointer": True}
    return {"ok": False, "error": f"unknown kind {f.kind}"}


def load_cursor() -> dict:
    ensure_tree()
    p = STATE_DIR / "smart_discover_cursor.json"
    if p.exists():
        return read_json(p)
    return {"seen": {}}


def save_cursor(c: dict) -> None:
    write_json(STATE_DIR / "smart_discover_cursor.json", c)


def run_discover_ingest(
    *,
    max_files: int = 2000,
    force: bool = False,
    agent_id: str = "smart-discover",
) -> dict[str, Any]:
    ensure_tree()
    rid = os.environ.get("PRIVATE_BRAIN_RUN_ID") or f"discover-{utc_now()}"
    audit("crawl_start", agent_id=agent_id, role="smart-discover", run_id=rid, detail="smart_discover")

    finds = discover(max_files=max_files * 2)
    cursor = load_cursor()
    seen = cursor.setdefault("seen", {})

    report = {
        "discovered": len(finds),
        "by_kind": {},
        "ingested": 0,
        "skipped": 0,
        "errors": 0,
        "homes": [str(h) for h in codex_homes()],
        "samples": [],
    }
    for f in finds:
        report["by_kind"][f.kind] = report["by_kind"].get(f.kind, 0) + 1

    for f in finds:
        if report["ingested"] >= max_files:
            break
        key = str(f.path)
        try:
            mtime = f.path.stat().st_mtime
        except OSError:
            report["errors"] += 1
            continue
        if not force and seen.get(key) == mtime:
            report["skipped"] += 1
            continue
        try:
            res = ingest_find(f, agent_id)
            if res.get("ok"):
                report["ingested"] += 1
                seen[key] = mtime
                if len(report["samples"]) < 12:
                    report["samples"].append({"kind": f.kind, "path": str(f.path), "score": f.score, "result": {k: res[k] for k in res if k != "error"}})
            else:
                report["errors"] += 1
        except Exception as e:
            report["errors"] += 1
            audit("crawl_error", agent_id=agent_id, role="smart-discover", result="fail", detail=str(e)[:200], object_id=str(f.path))

    cursor["seen"] = seen
    cursor["last_run"] = utc_now()
    save_cursor(cursor)

    # Rate only when we actually ingested something (full rate_all on 5k nodes is slow)
    if report["ingested"] > 0 or force:
        try:
            rate = rate_all(persist=True)
            report["rating"] = {"rated": rate.get("rated"), "bands": rate.get("bands"), "avg": rate.get("avg")}
        except Exception as e:
            report["rating"] = {"error": str(e)[:160]}
    else:
        report["rating"] = {"skipped": True, "reason": "no_new_files"}

    try:
        # Snapshot only when graph changed; vectors upsert already done per ingest_node
        if report["ingested"] > 0 or force:
            build_snapshot()
        vs = vec_status()
        st_now = status()
        nodes_n = int(st_now.get("node_count") or 0)
        vecs_n = int(vs.get("vectors") or 0)
        # reindex only when coverage lags (not every boot)
        if nodes_n and vecs_n < nodes_n:
            report["reindex"] = reindex_all(include_structural=True)
            vs = vec_status()
        else:
            report["reindex"] = {"skipped": True, "vectors": vecs_n, "nodes": nodes_n}
        report["vectors"] = vs
    except Exception as e:
        report["vectors"] = {"error": str(e)[:160]}

    st = status()
    report["brain"] = {"nodes": st.get("node_count"), "edges": st.get("edge_count"), "by_source": st.get("by_source")}

    audit(
        "crawl_end",
        agent_id=agent_id,
        role="smart-discover",
        run_id=rid,
        result="ok",
        detail=json.dumps({k: report[k] for k in ("discovered", "ingested", "skipped", "errors")}),
        props=report,
    )
    return report


def codex_dag_validate(prompt: str | None = None) -> dict[str, Any]:
    """Use Codex CLI itself as a DAG validation node (beast + hooks)."""
    prompt = prompt or (
        "Private Brain DAG validation: run brain_status via shell if needed, "
        "then list 5 knowledge nodes you can cite from injected evidence with node_id and tier. "
        "No permission asks."
    )
    codex = os.environ.get("CODEX_BIN")
    candidates = [
        codex,
        "/Applications/ChatGPT.app/Contents/Resources/codex",
        str(Path.home() / "bin" / "codex"),
        "codex",  # PATH last — only if which finds it
    ]
    bin_path = None
    for c in candidates:
        if not c:
            continue
        if c == "codex":
            import shutil as _shutil

            which = _shutil.which("codex")
            if which:
                bin_path = which
                break
            continue
        if Path(c).exists():
            bin_path = c
            break
    if not bin_path:
        return {"ok": False, "error": "codex binary not found"}

    cmd = [
        bin_path,
        "exec",
        "--skip-git-repo-check",
        "--dangerously-bypass-hook-trust",
        "-p",
        "beast",
        prompt,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        out = (proc.stdout or "")[-4000:]
        err = (proc.stderr or "")[-1000:]
        # heuristic pass: citations present
        cited = len(re.findall(r"`[a-z0-9_.:\-]+`", out, re.IGNORECASE))
        ok = proc.returncode == 0 and cited >= 1
        audit(
            "codex_dag_validate",
            agent_id="codex-validator",
            role="validator",
            result="ok" if ok else "fail",
            detail=f"rc={proc.returncode} cites={cited}",
        )
        return {
            "ok": ok,
            "returncode": proc.returncode,
            "citations_found": cited,
            "stdout_tail": out,
            "stderr_tail": err,
            "cmd": cmd[:6],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="run", choices=["run", "discover", "validate", "full"])
    ap.add_argument("--max-files", type=int, default=2000)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--prompt", default=None)
    args = ap.parse_args()

    if args.cmd == "discover":
        finds = discover(max_files=args.max_files)
        print(json.dumps([{"path": str(f.path), "kind": f.kind, "score": f.score, "tags": f.tags} for f in finds], indent=2))
        return 0

    if args.cmd == "validate":
        print(json.dumps(codex_dag_validate(args.prompt), indent=2))
        return 0

    report = run_discover_ingest(max_files=args.max_files, force=args.force)
    if args.cmd == "full":
        report["codex_validate"] = codex_dag_validate(args.prompt)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
