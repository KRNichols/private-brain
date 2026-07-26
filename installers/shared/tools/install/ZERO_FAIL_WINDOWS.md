# ZERO-FAIL Windows first boot

**Mission:** works the first time on the Corporate Windows laptop. No go-back.

## Full access (authorized)

| Control | Setting |
|---------|---------|
| `sandbox_mode` | **`danger-full-access`** |
| `approval_policy` | **`never`** |
| CLI | `--dangerously-bypass-approvals-and-sandbox` |
| Hooks | `--dangerously-bypass-hook-trust` |
| Law | Sandbox helper is **broken** — never ask permission |

Install forces beast-enterprise + beast + nuclear profiles with the above.

## Product path (human)

```text
1. Quit Codex completely
2. Extract PrivateBrain-WINDOWS-READY.zip
3. Open folder → only README.md · DIAGRAM.md · tools/
4. PowerShell:
     cd …\windows   (or extracted root)
     Set-ExecutionPolicy -Scope Process Bypass
     .\tools\install\START.ps1
5. Open Codex → talk (beast auto-on)
6. Optional: stop beast mode (this session) · reopen → beast on
```

## Self-* organism (under the floor)

| Capability | Mechanism |
|------------|-----------|
| Self-heal | `enterprise.self_heal` · fire_drill stress · hooks ledger |
| Self-repair | chain seal · vector reindex · profile rewrite |
| Self-configure | day1 map · golden_join · organism |
| Self-learn | session harvest · smart_discover · distill |
| Self-vectorize | vector_manager reindex on parity fail |
| Self-judge | doctor · critic · fire_drill · brutal |
| Non-hallucinate | validate · critic · citation_gate · stop_validate |

## Gate before USB

On the build machine:

```text
PB_ENTERPRISE=1 python scripts/nuclear_zero_fail.py
```

Must print **NUCLEAR GREEN** / **AUTHORIZED FOR WINDOWS FIRST BOOT**.

If red: **do not ship**.
