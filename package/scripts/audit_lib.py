"""
Append-only audit log with hash chain for SAP / Coverity evidence.

Air-gapped: no network. Integrity is local chain of SHA-256 digests.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain_lib import ensure_tree, read_json, resolve_brain_root, utc_now, write_json

_audit_lock = threading.RLock()
# Cross-process lock (threads alone race when gitlab_ingest + orchestrate fork).
_LOCK_FD = None

SECRET_PATTERNS = [
    re.compile(r"glpat-[A-Za-z0-9_\-]{10,}", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?token|api[_-]?key|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
]


def audit_dir() -> Path:
    ensure_tree()
    d = resolve_brain_root() / ".brain" / "audit"
    d.mkdir(parents=True, exist_ok=True)
    (d / "packs").mkdir(parents=True, exist_ok=True)
    return d


def events_path() -> Path:
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    return audit_dir() / f"events-{day}.jsonl"


def chain_path() -> Path:
    return audit_dir() / "chain_tip.json"


def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def redact(text: str | None) -> tuple[str | None, bool]:
    if text is None:
        return None, False
    redacted = False
    out = text
    for pat in SECRET_PATTERNS:
        if pat.search(out):
            out = pat.sub("/**REDACTED**/", out)
            redacted = True
    return out, redacted


def load_chain_tip() -> dict[str, Any]:
    p = chain_path()
    if p.exists():
        return read_json(p)
    return {"seq": 0, "tip_hash": "GENESIS", "updated_at": utc_now()}


def _acquire_audit_lock(*, timeout_s: float = 30.0):
    """Exclusive cross-process lock around tip+append+tip-write.

    Retries until timeout. Concurrent agents/crawls must serialize here or the
    hash chain tips will race (prev_hash mismatch). Windows uses msvcrt; Unix fcntl.
    """
    global _LOCK_FD
    import time

    lock_path = audit_dir() / ".audit.write.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, "a+", encoding="utf-8")
    deadline = time.time() + max(1.0, timeout_s)
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            if os.name == "nt":
                import msvcrt  # type: ignore

                fd.seek(0)
                # NBLCK + retry (LK_LOCK can hang forever on some hosts)
                try:
                    msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    time.sleep(0.02)
                    continue
            else:
                import fcntl

                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _LOCK_FD = fd
            return fd
        except (OSError, BlockingIOError) as e:
            last_err = e
            time.sleep(0.02)
        except Exception as e:
            last_err = e
            time.sleep(0.05)
    # Last resort: blocking lock (prefer hang over silent race corruption)
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore

            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
        _LOCK_FD = fd
        return fd
    except Exception as e:
        try:
            fd.close()
        except Exception:
            pass
        raise TimeoutError(f"audit write lock unavailable: {last_err or e}") from e


def _release_audit_lock(fd) -> None:
    global _LOCK_FD
    try:
        if os.name == "nt":
            import msvcrt  # type: ignore

            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        fd.close()
    except Exception:
        pass
    if _LOCK_FD is fd:
        _LOCK_FD = None


def seal_broken_chain() -> dict[str, Any]:
    """
    Archive broken active event files as *.broken-<ts>, reset tip to GENESIS.
    verify_chain already ignores .broken- files. Use when multi-process races
    corrupted the day file (or after forensic review).

    Sealed archives remain on disk for forensics; they are NOT continuous with the
    new GENESIS→tip active chain. doctor/verify_chain report sealed_* separately.
    """
    ensure_tree()
    d = audit_dir()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sealed: list[str] = []
    with _audit_lock:
        fd = _acquire_audit_lock()
        try:
            for fp in list(d.glob("events-*.jsonl")):
                if ".broken-" in fp.name:
                    continue
                dest = fp.with_name(f"{fp.name}.broken-{stamp}")
                try:
                    fp.rename(dest)
                    sealed.append(dest.name)
                except OSError:
                    pass
            write_json(
                chain_path(),
                {
                    "seq": 0,
                    "tip_hash": "GENESIS",
                    "updated_at": utc_now(),
                    "sealed_at": stamp,
                    "sealed_files": sealed,
                },
            )
            marker = d / f"chain_seal-{stamp}.json"
            write_json(
                marker,
                {"sealed_at": stamp, "files": sealed, "reason": "broken_chain_repair"},
            )
        finally:
            _release_audit_lock(fd)
    # First event of the new active window (outside seal lock to avoid re-entry).
    try:
        audit(
            "chain_seal",
            agent_id="audit_lib",
            role="security_auditor",
            result="ok",
            detail=f"sealed={len(sealed)} stamp={stamp}",
            props={"sealed_files": sealed, "stamp": stamp, "reason": "broken_chain_repair"},
        )
    except Exception:
        pass
    return {"ok": True, "sealed": sealed, "stamp": stamp}


def audit(
    action: str,
    *,
    agent_id: str = "unknown",
    role: str = "unknown",
    run_id: str | None = None,
    object_id: str | None = None,
    result: str = "ok",
    detail: str | None = None,
    props: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one audit event; returns the event including chain fields."""
    ensure_tree()
    detail_r, was_redacted = redact(detail)
    with _audit_lock:
        fd = _acquire_audit_lock()
        try:
            tip = load_chain_tip()
            seq = int(tip.get("seq") or 0) + 1
            prev = tip.get("tip_hash") or "GENESIS"
            event: dict[str, Any] = {
                "event_id": str(uuid.uuid4()),
                "seq": seq,
                "ts": utc_now(),
                "action": action,
                "agent_id": agent_id,
                "role": role,
                "run_id": run_id or os.environ.get("PRIVATE_BRAIN_RUN_ID"),
                "object_id": object_id,
                "result": result,
                "detail": detail_r,
                "props": props or {},
                "prev_hash": prev,
                "redacted": was_redacted,
                "hostname": os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or "",
                "user": os.environ.get("USERNAME") or os.environ.get("USER") or "",
            }
            body = {k: v for k, v in event.items() if k != "event_hash"}
            event["event_hash"] = _hash(prev + _canonical(body))

            path = events_path()
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass

            write_json(
                chain_path(),
                {
                    "seq": seq,
                    "tip_hash": event["event_hash"],
                    "updated_at": utc_now(),
                    "last_event_id": event["event_id"],
                },
            )
            return event
        finally:
            _release_audit_lock(fd)


def _inventory_sealed(d: Path) -> dict[str, Any]:
    """Count forensic sealed archives (*.broken-*). Not part of active chain."""
    sealed_files = sorted(p for p in d.glob("events-*.jsonl*") if ".broken-" in p.name)
    sealed_events = 0
    for fp in sealed_files:
        try:
            with fp.open(encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        sealed_events += 1
        except OSError:
            continue
    seals = sorted(d.glob("chain_seal-*.json"))
    last_seal: dict[str, Any] | None = None
    if seals:
        try:
            last_seal = read_json(seals[-1])
            if isinstance(last_seal, dict):
                last_seal = {**last_seal, "marker": seals[-1].name}
            else:
                last_seal = {"marker": seals[-1].name}
        except Exception:
            last_seal = {"marker": seals[-1].name}
    tip = load_chain_tip()
    tip_seal = tip.get("sealed_at") if isinstance(tip, dict) else None
    return {
        "sealed_files": [p.name for p in sealed_files],
        "sealed_file_count": len(sealed_files),
        "sealed_events": sealed_events,
        "seal_markers": len(seals),
        "last_seal": last_seal,
        "tip_sealed_at": tip_seal,
        "chain_window": "active_post_seal" if sealed_files or seals else "full_active",
    }


def verify_chain(max_files: int = 60) -> dict[str, Any]:
    """Verify hash chain across recent *active* event files.

    events_checked = active GENESIS→tip window only (post last seal_broken_chain).
    Sealed ``events-*.jsonl.broken-*`` archives are forensic history after a repair
    seal; they are not hash-continuous with the active tip and are reported separately
    as sealed_events / last_seal so doctor does not look under-counted vs history.
    """
    d = audit_dir()
    # only active day files — sealed .broken-* history is archival, not chain continuity
    files = sorted(
        p for p in d.glob("events-*.jsonl") if ".broken-" not in p.name
    )[-max_files:]
    prev = "GENESIS"
    count = 0
    errors: list[str] = []
    last_hash = "GENESIS"
    for fp in files:
        with fp.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    errors.append(f"{fp.name}:{line_no} invalid json")
                    continue
                count += 1
                if ev.get("prev_hash") != prev:
                    errors.append(
                        f"{fp.name}:{line_no} prev_hash mismatch seq={ev.get('seq')} "
                        f"expected={prev[:12]}… got={str(ev.get('prev_hash'))[:12]}…"
                    )
                body = {k: v for k, v in ev.items() if k != "event_hash"}
                calc = _hash(str(ev.get("prev_hash")) + _canonical(body))
                if calc != ev.get("event_hash"):
                    errors.append(f"{fp.name}:{line_no} event_hash mismatch seq={ev.get('seq')}")
                prev = ev.get("event_hash") or prev
                last_hash = prev
    tip = load_chain_tip()
    tip_ok = (tip.get("tip_hash") == last_hash) or count == 0
    if count and not tip_ok:
        errors.append("chain_tip.json does not match last event hash")

    sealed = _inventory_sealed(d)
    if sealed["sealed_events"]:
        note = (
            f"events_checked={count} is the active GENESIS→tip chain only "
            f"(chain_window={sealed['chain_window']}). "
            f"Sealed archives hold {sealed['sealed_events']} forensic events in "
            f"{sealed['sealed_file_count']} file(s); not continuous with active tip."
        )
    else:
        note = "No sealed archives; full active chain verified."

    return {
        "ok": len(errors) == 0,
        "events_checked": count,
        "files": [p.name for p in files],
        "tip_hash": last_hash,
        "errors": errors,
        "verified_at": utc_now(),
        "audit_dir": str(d),
        "path": str(events_path()),
        "sealed_files": sealed["sealed_files"],
        "sealed_file_count": sealed["sealed_file_count"],
        "sealed_events": sealed["sealed_events"],
        "seal_markers": sealed["seal_markers"],
        "last_seal": sealed["last_seal"],
        "tip_sealed_at": sealed["tip_sealed_at"],
        "chain_window": sealed["chain_window"],
        "note": note,
    }


def scan_content_for_secrets(
    root: Path | None = None,
    *,
    max_files: int = 120,
    max_hits: int = 20,
) -> list[dict[str, Any]]:
    """Local pattern scan of content/ (chunks skipped for speed — content is enough)."""
    brain = resolve_brain_root() / ".brain"
    hits: list[dict[str, Any]] = []
    scanned = 0
    # Prefer content/ only; newest files first (mtime) for live risk
    d = brain / "content"
    if not d.is_dir():
        return hits
    files = sorted(d.glob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)
    for fp in files:
        if not fp.is_file():
            continue
        if scanned >= max_files or len(hits) >= max_hits:
            break
        scanned += 1
        try:
            text = fp.read_text(encoding="utf-8", errors="ignore")[:50000]
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                hits.append(
                    {
                        "path": str(fp.relative_to(brain)),
                        "pattern": pat.pattern[:80],
                        "span": m.group(0)[:20] + "…",
                    }
                )
                break
    return hits


def inventory_package() -> dict[str, Any]:
    """File inventory for Coverity intake (local package only)."""
    root = resolve_brain_root()
    files = []
    for fp in root.rglob("*"):
        if not fp.is_file():
            continue
        rel = str(fp.relative_to(root))
        if any(x in rel for x in (".brain/", "venv/", "__pycache__", ".pyc")):
            continue
        files.append(
            {
                "path": rel,
                "bytes": fp.stat().st_size,
                "ext": fp.suffix.lower(),
            }
        )
    by_ext: dict[str, int] = {}
    for f in files:
        by_ext[f["ext"] or "(none)"] = by_ext.get(f["ext"] or "(none)", 0) + 1
    return {
        "root": str(root),
        "file_count": len(files),
        "by_ext": by_ext,
        "files": files,
        "generated_at": utc_now(),
        "note": "Air-gapped package inventory for static analysis intake (e.g. Coverity).",
    }
