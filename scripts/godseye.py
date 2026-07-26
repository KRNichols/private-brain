"""GodsEye live GUI — one window max. Never reopen after user closes it."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _root() -> Path:
    return Path(
        os.environ.get("PRIVATE_BRAIN_HOME")
        or (Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "private-brain")
    ).expanduser().resolve()


def _state() -> Path:
    p = _root() / ".brain" / "state"
    p.mkdir(parents=True, exist_ok=True)
    return p


def enabled() -> bool:
    """GodsEye feature allowed (env or flag file). Does NOT mean window must be open."""
    v = os.environ.get("PB_GODSEYE", "").strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    return (_state() / "godseye.on").exists()


def user_dismissed() -> bool:
    """True if user closed the GUI — auto-boot must not force it back open."""
    return (_state() / "godseye.dismissed").exists()


def mark_dismissed() -> None:
    """User closed the window (or asked to stop). Persist until explicit start."""
    st = _state()
    (st / "godseye.dismissed").write_text(f"closed_at={time.time()}\n", encoding="utf-8")
    for name in ("godseye.pid", "visualizer.pid", "gui.lock"):
        p = st / name
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def clear_dismissed() -> None:
    p = _state() / "godseye.dismissed"
    try:
        if p.exists():
            p.unlink()
    except Exception:
        pass


def set_enabled(on: bool) -> None:
    flag = _state() / "godseye.on"
    if on:
        flag.write_text("1\n", encoding="utf-8")
        os.environ["PB_GODSEYE"] = "1"
        clear_dismissed()  # explicit enable = user wants the GUI again
    else:
        if flag.exists():
            flag.unlink()
        os.environ["PB_GODSEYE"] = "0"
        mark_dismissed()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    except Exception:
        return False
    try:
        out = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "stat="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not out or out[0] in ("Z", "z"):
            return False
        return True
    except subprocess.CalledProcessError:
        return False
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False


def _read_pid(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _kill_pid(pid: int, grace_sec: float = 0.8) -> bool:
    if not _pid_alive(pid):
        return True

    def _sig(sig: int) -> None:
        try:
            os.killpg(pid, sig)
            return
        except Exception:
            pass
        try:
            os.kill(pid, sig)
        except Exception:
            pass

    _sig(signal.SIGTERM)
    deadline = time.time() + grace_sec
    while time.time() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    _sig(signal.SIGKILL)
    time.sleep(0.1)
    return not _pid_alive(pid)


def _pgrep_gui_pids(root: Path) -> list[int]:
    pids: set[int] = set()
    state = root / ".brain" / "state"
    for name in ("godseye.pid", "visualizer.pid"):
        pid = _read_pid(state / name)
        if pid and _pid_alive(pid):
            pids.add(pid)

    me = os.getpid()
    try:
        out = subprocess.check_output(
            ["ps", "-ax", "-o", "pid=,command="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                sp = line.split(None, 1)
                pid = int(sp[0])
                cmd = sp[1] if len(sp) > 1 else ""
            except Exception:
                continue
            if pid == me:
                continue
            low = cmd.lower()
            if "live_gui.py" in low or "graph_gl.py" in low or "visualizer" in low:
                pids.add(pid)
    except Exception:
        try:
            out = subprocess.check_output(
                ["wmic", "process", "get", "ProcessId,CommandLine", "/FORMAT:CSV"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines():
                low = line.lower()
                if "live_gui.py" in low or "graph_gl.py" in low or "visualizer" in low:
                    parts = line.split(",")
                    try:
                        pid = int(parts[-1].strip())
                        if pid != me:
                            pids.add(pid)
                    except Exception:
                        pass
        except Exception:
            pass
    return sorted(pids)


def terminate_existing_guis(root: Path | None = None, *, mark_user_dismissed: bool = False) -> dict:
    """Kill all GUI windows. If mark_user_dismissed, boot will not reopen them."""
    root = root or _root()
    found = _pgrep_gui_pids(root)
    killed: list[int] = []
    failed: list[int] = []
    for pid in found:
        if _kill_pid(pid):
            killed.append(pid)
        else:
            failed.append(pid)

    state = root / ".brain" / "state"
    for name in ("godseye.pid", "visualizer.pid", "gui.lock"):
        p = state / name
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    if mark_user_dismissed:
        mark_dismissed()

    return {"found": found, "killed": killed, "failed": failed, "cleared": True}


def _write_both_pids(root: Path, pid: int) -> None:
    state = root / ".brain" / "state"
    state.mkdir(parents=True, exist_ok=True)
    for name in ("godseye.pid", "visualizer.pid"):
        (state / name).write_text(str(pid), encoding="utf-8")


def _live_pid(root: Path) -> int | None:
    state = root / ".brain" / "state"
    for pfile in (state / "godseye.pid", state / "visualizer.pid"):
        pid = _read_pid(pfile)
        if pid and _pid_alive(pid):
            return pid
    # process table fallback
    found = _pgrep_gui_pids(root)
    return found[0] if found else None


def ensure_gui(*, replace: bool = False, force: bool = False) -> dict:
    """
    GodsEye window lifecycle:

    - If user closed it (dismissed) → do NOT reopen unless force=True
      (explicit CLI start/restart only). Checked BEFORE live-pid so a
      dying window after close never reports \"already\" and gets re-adopted.
    - If a window is already running (and not dismissed) → leave it alone.
    - Boot/concert must call ensure_gui() with defaults (replace=False, force=False)
      so closing the window sticks.
    - replace=True only for explicit restart (kills orphans then starts one).
    - Backend auto-selected from importable modules (gl|cpu|off) via capabilities.
    """
    # Pick best available backend from what's installed (home full stack / Corporate Library subset)
    try:
        from capabilities import apply_env_hints, probe, write_state

        caps = probe()
        write_state(caps)
        apply_env_hints(caps)
        feat = caps.get("features") or {}
        if feat.get("godseye_backend") == "off" and force:
            return {
                "godseye": True,
                "gui": "error",
                "error": "pygame not available — install from Corporate Library / Protected Gateway or pip; core RAG stays headless",
                "capabilities": feat,
            }
    except Exception:
        pass

    if not enabled() and not force:
        return {"godseye": False, "gui": "off"}

    root = _root()

    # User closed it — respect that unless explicit force/restart.
    # Must come before live-pid: mark_dismissed unlinks pid files but the
    # process can still be alive briefly; pgrep fallback must not reopen.
    if user_dismissed() and not force and not replace:
        return {
            "godseye": True,
            "gui": "dismissed",
            "detail": "user closed GodsEye; will not auto-reopen (run: godseye.py start)",
        }

    # Already open? Never kill on boot.
    live = _live_pid(root)
    if live and not replace:
        _write_both_pids(root, live)
        return {"godseye": True, "gui": "already", "pid": live}

    reaped = {"found": [], "killed": [], "failed": []}
    if replace:
        reaped = terminate_existing_guis(root, mark_user_dismissed=False)
        clear_dismissed()
    elif force:
        clear_dismissed()

    # Windows Corporate: Scripts first; Mac/home: bin first
    if sys.platform.startswith("win"):
        candidates = [
            root / "venv" / "Scripts" / "python.exe",
            root / "venv" / "Scripts" / "python",
            root / "venv" / "bin" / "python3",
        ]
    else:
        candidates = [
            root / "venv" / "bin" / "python3",
            root / "venv" / "bin" / "python",
            root / "venv" / "Scripts" / "python.exe",
        ]
    py = next((c for c in candidates if c.exists()), Path(sys.executable))

    # Backend: true OpenGL (graph_gl) vs CPU pygame (live_gui)
    backend = (os.environ.get("PB_GODSEYE_BACKEND") or "gl").strip().lower()
    gl_path = root / "visualizer" / "graph_gl.py"
    cpu_path = root / "visualizer" / "live_gui.py"

    def _gl_importable() -> bool:
        try:
            r = subprocess.run(
                [str(py), "-c", "from OpenGL.GL import glClear; import pygame"],
                capture_output=True,
                timeout=8,
            )
            return r.returncode == 0
        except Exception:
            return False

    gui = None
    chosen = backend
    if backend in ("gl", "opengl", "truegl", "gpu"):
        if gl_path.exists() and _gl_importable():
            gui = gl_path
            chosen = "gl"
        elif cpu_path.exists():
            gui = cpu_path
            chosen = "cpu-fallback"
        else:
            return {"godseye": True, "gui": "error", "error": "graph_gl.py missing and no live_gui", "reaped": reaped}
    elif backend in ("cpu", "software", "live_gui"):
        gui = cpu_path if cpu_path.exists() else gl_path
        chosen = "cpu"
    else:  # auto
        if gl_path.exists() and _gl_importable():
            gui = gl_path
            chosen = "gl"
        else:
            gui = cpu_path if cpu_path.exists() else gl_path
            chosen = "cpu"

    if not gui or not gui.exists():
        return {"godseye": True, "gui": "error", "error": "no visualizer module", "reaped": reaped}

    # If somehow still alive after replace check
    live = _live_pid(root)
    if live and not replace:
        return {"godseye": True, "gui": "already", "pid": live, "backend": chosen}

    log = root / ".brain" / "logs" / "godseye.out"
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.Popen(
            [str(py), str(gui)],
            stdout=open(log, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={
                **os.environ,
                "PB_GODSEYE": "1",
                "PRIVATE_BRAIN_HOME": str(root),
                "PB_GODSEYE_BACKEND": chosen if chosen.startswith("gl") else os.environ.get("PB_GODSEYE_BACKEND", "gl"),
            },
        )
        clear_dismissed()
        _write_both_pids(root, proc.pid)
        return {
            "godseye": True,
            "gui": "started",
            "pid": proc.pid,
            "backend": chosen,
            "module": str(gui.name),
            "reaped": reaped,
            "killed_prior": reaped.get("killed") or [],
        }
    except Exception as e:
        return {"godseye": True, "gui": "error", "error": str(e)[:200], "reaped": reaped}


def main() -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="GodsEye single-window GUI control")
    ap.add_argument(
        "cmd",
        nargs="?",
        default="status",
        choices=["status", "start", "stop", "kill", "restart"],
    )
    args = ap.parse_args()
    root = _root()

    if args.cmd == "status":
        pids = _pgrep_gui_pids(root)
        print(
            json.dumps(
                {
                    "enabled": enabled(),
                    "dismissed": user_dismissed(),
                    "pids": pids,
                    "alive": [_pid_alive(p) for p in pids],
                },
                indent=2,
            )
        )
        return 0
    if args.cmd == "kill":
        # kill windows but leave dismissed so boot won't reopen
        print(json.dumps(terminate_existing_guis(root, mark_user_dismissed=True), indent=2))
        return 0
    if args.cmd == "stop":
        print(json.dumps(terminate_existing_guis(root, mark_user_dismissed=True), indent=2))
        set_enabled(False)
        return 0
    if args.cmd == "start":
        set_enabled(True)  # also clears dismissed
        print(json.dumps(ensure_gui(replace=False, force=True), indent=2))
        return 0
    if args.cmd == "restart":
        set_enabled(True)
        print(json.dumps(ensure_gui(replace=True, force=True), indent=2))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
