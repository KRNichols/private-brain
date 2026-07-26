#!/usr/bin/env python3
"""Local secrets store — never commit; prefer OS vault over plaintext day1.env.

Windows: DPAPI (CryptProtectData) when available.
macOS/Linux: keyring if installed; else restricted file under .brain/secrets/.

  from secrets_store import put_secret, get_secret, store_tokens_from_env, redact_env_echo
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

SECRET_KEYS = (
    "GITLAB_TOKEN",
    "JIRA_TOKEN",
    "JIRA_API_TOKEN",
    "CONFLUENCE_TOKEN",
    "CONFLUENCE_API_TOKEN",
    "PIP_INDEX_URL",  # may embed credentials
    "PB_PIP_INDEX_URL",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
)


def _brain() -> Path:
    if os.environ.get("PRIVATE_BRAIN_HOME"):
        return Path(os.environ["PRIVATE_BRAIN_HOME"]).expanduser()
    codex = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
    return codex / "private-brain"


def secrets_dir() -> Path:
    d = _brain() / ".brain" / "secrets"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except Exception:
        pass
    return d


def _file_path(name: str) -> Path:
    safe = hashlib.sha256(name.encode()).hexdigest()[:24]
    return secrets_dir() / f"{safe}.bin"


def _dpapi_protect(data: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        blob_in = DATA_BLOB(len(data), ctypes.create_string_buffer(data, len(data)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return None
        try:
            out = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return out
    except Exception:
        return None


def _dpapi_unprotect(data: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
        blob_in = DATA_BLOB(len(data), ctypes.create_string_buffer(data, len(data)))
        blob_out = DATA_BLOB()
        if not crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            return None
        try:
            out = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            kernel32.LocalFree(blob_out.pbData)
        return out
    except Exception:
        return None


def put_secret(name: str, value: str) -> dict[str, Any]:
    """Store secret; returns backend used. Never prints value."""
    if not value:
        return {"ok": False, "error": "empty"}
    name = str(name)
    # 1) keyring
    try:
        import keyring  # type: ignore

        keyring.set_password("private-brain", name, value)
        return {"ok": True, "backend": "keyring", "name": name}
    except Exception:
        pass
    # 2) Windows DPAPI
    protected = _dpapi_protect(value.encode("utf-8"))
    if protected is not None:
        p = _file_path(name)
        p.write_bytes(b"DPAPI:" + base64.b64encode(protected))
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
        return {"ok": True, "backend": "dpapi", "name": name, "path": str(p)}
    # 3) Restricted file (xor with machine salt — better than day1.env plaintext)
    salt = hashlib.sha256(
        (str(_brain()) + os.environ.get("USERNAME", "") + os.environ.get("USER", "")).encode()
    ).digest()
    raw = value.encode("utf-8")
    xored = bytes(b ^ salt[i % len(salt)] for i, b in enumerate(raw))
    p = _file_path(name)
    p.write_bytes(b"XOR1:" + base64.b64encode(xored))
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
    return {"ok": True, "backend": "file_xor", "name": name, "path": str(p)}


def get_secret(name: str) -> str | None:
    name = str(name)
    try:
        import keyring  # type: ignore

        v = keyring.get_password("private-brain", name)
        if v:
            return v
    except Exception:
        pass
    p = _file_path(name)
    if not p.exists():
        # fall back to process env (not ideal; for already-loaded sessions)
        return os.environ.get(name) or None
    data = p.read_bytes()
    if data.startswith(b"DPAPI:"):
        raw = _dpapi_unprotect(base64.b64decode(data[6:]))
        return raw.decode("utf-8") if raw else None
    if data.startswith(b"XOR1:"):
        xored = base64.b64decode(data[5:])
        salt = hashlib.sha256(
            (str(_brain()) + os.environ.get("USERNAME", "") + os.environ.get("USER", "")).encode()
        ).digest()
        raw = bytes(b ^ salt[i % len(salt)] for i, b in enumerate(xored))
        return raw.decode("utf-8")
    return None


def store_tokens_from_env(*, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Move known secret env vars into the store (values stay in process env for tools)."""
    keys = keys or SECRET_KEYS
    out: dict[str, Any] = {"stored": [], "skipped": []}
    for k in keys:
        v = os.environ.get(k)
        if not v:
            out["skipped"].append(k)
            continue
        r = put_secret(k, v)
        if r.get("ok"):
            out["stored"].append({"name": k, "backend": r.get("backend")})
        else:
            out["skipped"].append(k)
    # index of what we hold (no values)
    idx = secrets_dir() / "index.json"
    try:
        prev = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
    except Exception:
        prev = {}
    prev["keys"] = sorted(set((prev.get("keys") or []) + [x["name"] for x in out["stored"]]))
    prev["backends"] = {x["name"]: x["backend"] for x in out["stored"]}
    idx.write_text(json.dumps(prev, indent=2), encoding="utf-8")
    try:
        os.chmod(idx, 0o600)
    except Exception:
        pass
    return out


def load_secrets_into_env(*, keys: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Populate os.environ from store without printing values."""
    keys = keys or SECRET_KEYS
    loaded = []
    for k in keys:
        if os.environ.get(k):
            continue
        v = get_secret(k)
        if v:
            os.environ[k] = v
            loaded.append(k)
    return {"loaded": loaded}


def redact_env_echo(line: str) -> str:
    """Scrub token-like assignments from logs / day1.env display."""
    import re

    out = line
    for k in SECRET_KEYS:
        out = re.sub(
            rf"({re.escape(k)}\s*[=:]\s*)([\"']?)([^\s\"']+)(\2)",
            rf"\1\2/**REDACTED**/\4",
            out,
            flags=re.I,
        )
    return out


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Private Brain secrets store")
    ap.add_argument("cmd", choices=["put", "get", "store-env", "load-env", "list"])
    ap.add_argument("--name", default="")
    ap.add_argument("--value", default="")
    args = ap.parse_args()
    if args.cmd == "put":
        if not args.name or not args.value:
            print(json.dumps({"ok": False, "error": "need --name and --value"}))
            return 2
        print(json.dumps(put_secret(args.name, args.value)))
        return 0
    if args.cmd == "get":
        v = get_secret(args.name)
        # never print secret; only presence
        print(json.dumps({"ok": v is not None, "name": args.name, "present": bool(v)}))
        return 0
    if args.cmd == "store-env":
        print(json.dumps(store_tokens_from_env(), indent=2))
        return 0
    if args.cmd == "load-env":
        print(json.dumps(load_secrets_into_env(), indent=2))
        return 0
    if args.cmd == "list":
        idx = secrets_dir() / "index.json"
        if idx.exists():
            print(idx.read_text(encoding="utf-8"))
        else:
            print(json.dumps({"keys": []}))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
