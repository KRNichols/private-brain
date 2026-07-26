# Lecture map → this codebase

Source talks (verbatim quotes live in the reference repo README / article):

- Anthropic agent-building masterclass
- Anthropic "How Claude Code works"
- Karpathy on jagged model edges

| Idea | Lives here |
|---|---|
| gather → act → verify | `loop.py::run_loop` |
| rule-based verifier first | `workers.py` / `brain_workers.py` verify fns |
| jagged edge `"0s"` | `workers.py::_parse_v1` |
| fan-out sheets / slices | `graph.py::fan_out` |
| adversarial checker | `graph.py::adversarial_verify` |
| clean spawn, no fork | `harness.py::Harness.spawn` |
| one general tool (grep) | `harness.py::grep` |
| parent grows by result | `harness.py` event log |
| parallel race-safe spawn | `harness.py::spawn_many(parallel=True)` |
| brain evidence packs | `brain_workers.py` + `pipeline.py::run_brain_pipeline` |

Three questions at every node: **boundary · return type · verification**.
