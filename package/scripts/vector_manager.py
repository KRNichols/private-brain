#!/usr/bin/env python3
"""
Local vector manager — pure Python TF-IDF style (air-gapped, no model download).

Stores per-node vectors under .brain/index/embeddings/{safe_id}.json
Global vocab under .brain/index/embeddings/_vocab.json

Also used for hybrid retrieval (cosine over TF-IDF).
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

from brain_lib import (
    BRAIN,
    INDEX_DIR,
    ensure_tree,
    load_all_nodes,
    read_json,
    resolve_brain_root,
    safe_id,
    utc_now,
    write_json,
)

_lock = threading.Lock()
TOKEN_RE = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_\-./:]{1,64}")
# Process-local vector index for search (invalidated on upsert/reindex).
_vec_mem: list[dict[str, Any]] | None = None
_vocab_mem: dict[str, Any] | None = None
# On-disk aggregate pack (compact) — rebuilt after cold multi-file load; dropped on upsert.
_PACK_NAME = "_vectors_pack.json"
_REINDEX_LOCK_NAME = "_reindex.lock"


def _acquire_reindex_lock(timeout_s: float = 120.0):
    """Cross-process exclusive lock so concurrent reindex/doctor cannot wipe mid-flight."""
    ensure_tree()
    path = emb_dir() / _REINDEX_LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(path, "a+", encoding="utf-8")
    deadline = time.time() + timeout_s
    locked = False
    while time.time() < deadline:
        try:
            if os.name == "nt":
                # Best-effort on Windows; exclusive create of sidecar if msvcrt unavailable
                try:
                    import msvcrt

                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except Exception:
                    time.sleep(0.05)
                    continue
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break
        except OSError:
            time.sleep(0.1)
    if not locked:
        try:
            fh.close()
        except Exception:
            pass
        raise TimeoutError(f"reindex lock busy after {timeout_s}s: {path}")
    fh.seek(0)
    fh.truncate()
    fh.write(f"pid={os.getpid()} ts={utc_now()}\n")
    fh.flush()
    return fh


def _release_reindex_lock(fh) -> None:
    if fh is None:
        return
    try:
        if os.name == "nt":
            try:
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        fh.close()
    except Exception:
        pass


def _drop_vectors_pack() -> None:
    """Remove on-disk pack without ensure_tree (safe during bulk upsert)."""
    try:
        p = INDEX_DIR / "embeddings" / _PACK_NAME
        if p.exists():
            p.unlink()
    except OSError:
        pass


def invalidate_vector_cache() -> None:
    """Drop process mem + on-disk pack. Vocab mem cleared (callers that mutate vocab re-save)."""
    global _vec_mem, _vocab_mem
    _vec_mem = None
    _vocab_mem = None
    _drop_vectors_pack()


def emb_dir() -> Path:
    ensure_tree()
    d = INDEX_DIR / "embeddings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def vocab_path() -> Path:
    return emb_dir() / "_vocab.json"


def vector_path(node_id: str) -> Path:
    return emb_dir() / f"{safe_id(node_id)}.json"


def pack_path() -> Path:
    return emb_dir() / _PACK_NAME


def tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t.lower() for t in TOKEN_RE.findall(text)]


def embed_backend() -> str:
    """tfidf (default air-gapped) | bedrock-titan when configured + boto3 available."""
    want = (os.environ.get("PB_EMBED_BACKEND") or "").strip().lower()
    if want in ("tfidf", "local", "local-tfidf"):
        return "tfidf"
    if want in ("bedrock", "bedrock-titan", "titan") or os.environ.get("PB_OPENSEARCH_ENDPOINT"):
        if _bedrock_available():
            return "bedrock-titan"
    return "tfidf"


def _bedrock_available() -> bool:
    try:
        import boto3  # type: ignore

        return True
    except Exception:
        return False


def embed_titan(text: str) -> list[float] | None:
    """Optional Amazon Titan embed via Bedrock. Returns None if unavailable."""
    if not text or not _bedrock_available():
        return None
    try:
        import boto3  # type: ignore

        region = (
            os.environ.get("PB_BEDROCK_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or os.environ.get("AWS_REGION")
            or "gov-region-1"
        )
        model_id = os.environ.get("PB_TITAN_MODEL_ID") or "amazon.titan-embed-text-v2:0"
        client = boto3.client("bedrock-runtime", region_name=region)
        body = json.dumps({"inputText": text[:8000]})
        resp = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        payload = json.loads(resp["body"].read())
        emb = payload.get("embedding") or payload.get("embeddings")
        if isinstance(emb, list) and emb:
            return [float(x) for x in emb]
    except Exception:
        return None
    return None


def load_vocab() -> dict[str, Any]:
    global _vocab_mem
    if _vocab_mem is not None:
        return _vocab_mem
    p = vocab_path()
    if p.exists():
        _vocab_mem = read_json(p)
        return _vocab_mem
    _vocab_mem = {"df": {}, "n_docs": 0, "updated_at": None}
    return _vocab_mem


def save_vocab(v: dict[str, Any]) -> None:
    global _vocab_mem
    v["updated_at"] = utc_now()
    write_json(vocab_path(), v)
    _vocab_mem = v


def _load_text_for_node(node: dict[str, Any]) -> str:
    parts = [
        node.get("id") or "",
        node.get("title") or "",
        " ".join(node.get("tags") or []),
        " ".join(node.get("labels") or []),
        json.dumps(node.get("props") or {}),
    ]
    cpath = node.get("content_path")
    if cpath:
        fp = resolve_brain_root() / ".brain" / cpath
        if not fp.exists():
            fp = BRAIN / cpath
        if fp.exists():
            try:
                parts.append(fp.read_text(encoding="utf-8", errors="ignore")[:50000])
            except OSError:
                pass
    return "\n".join(parts)


def compute_tfidf(tokens: list[str], vocab: dict[str, Any]) -> dict[str, float]:
    if not tokens:
        return {}
    tf = Counter(tokens)
    n = max(1, int(vocab.get("n_docs") or 1))
    df = vocab.get("df") or {}
    vec: dict[str, float] = {}
    length = float(sum(tf.values())) or 1.0
    for term, cnt in tf.items():
        idf = math.log(1.0 + n / (1.0 + float(df.get(term, 0))))
        vec[term] = (cnt / length) * idf
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    # iterate smaller
    if len(a) > len(b):
        a, b = b, a
    return sum(v * b.get(k, 0.0) for k, v in a.items())


def upsert_vector(node_id: str, text: str | None = None, node: dict | None = None) -> dict[str, Any]:
    """Index or re-index a node. Local TF-IDF always; optional Titan dense when configured."""
    global _vec_mem
    ensure_tree()
    if text is None and node is not None:
        text = _load_text_for_node(node)
    text = text or ""
    tokens = tokenize(text)
    backend = embed_backend()
    dense = None
    if backend == "bedrock-titan":
        dense = embed_titan(text)
    with _lock:
        vocab = load_vocab()
        df = vocab.setdefault("df", {})
        # if re-indexing, we don't perfectly remove old DF — acceptable for local RAG
        seen_terms = set(tokens)
        for term in seen_terms:
            df[term] = int(df.get(term, 0)) + 1
        # cap vocab size (raised for full-corpus max-out)
        if len(df) > 200000:
            rare = [k for k, v in df.items() if v <= 1]
            for k in rare[: max(0, len(df) - 150000)]:
                df.pop(k, None)
        vocab["n_docs"] = int(vocab.get("n_docs") or 0) + 1
        vec = compute_tfidf(tokens, vocab)
        save_vocab(vocab)
        rec = {
            "id": node_id,
            "dims": len(vec),
            "vector": vec,
            "token_count": len(tokens),
            "updated_at": utc_now(),
            "algo": "tfidf-l2-v1",
            "embed_backend": backend,
        }
        if dense is not None:
            rec["dense"] = dense
            rec["dense_dims"] = len(dense)
            rec["dense_algo"] = "bedrock-titan"
        write_json(vector_path(node_id), rec)
        # Invalidate vector mem + pack only; vocab stays in _vocab_mem (just saved).
        _vec_mem = None
        _drop_vectors_pack()
    return {
        "id": node_id,
        "dims": len(vec),
        "token_count": len(tokens),
        "embed_backend": backend,
        "dense": dense is not None,
    }


def _write_vectors_pack(recs: list[dict[str, Any]]) -> None:
    """Compact single-file pack for fast cold load in next process."""
    try:
        payload = {"n": len(recs), "algo": "tfidf-l2-v1", "vectors": recs}
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        p = pack_path()
        # Unique tmp — concurrent pack writers must not clobber shared path.tmp
        tmp = p.parent / f".{p.name}.{os.getpid()}.{threading.get_ident()}.{time.time_ns()}.tmp"
        try:
            tmp.write_text(data, encoding="utf-8")
            os.replace(tmp, p)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
    except OSError:
        pass


def _all_vectors() -> list[dict[str, Any]]:
    """Load embedding records once per process (or after invalidation).

    Prefers compact on-disk pack when present (written after first multi-file load).
    Pack is deleted on upsert/reindex so invalidation stays correct.
    """
    global _vec_mem
    if _vec_mem is not None:
        return _vec_mem
    d = emb_dir()
    pack = d / _PACK_NAME
    if pack.exists():
        try:
            payload = read_json(pack)
            vecs = payload.get("vectors")
            if isinstance(vecs, list) and vecs:
                _vec_mem = vecs
                return _vec_mem
        except Exception:
            pass
    recs: list[dict[str, Any]] = []
    for fp in d.glob("*.json"):
        name = fp.name
        if name.startswith("_"):
            continue
        try:
            with fp.open("rb") as f:
                recs.append(json.loads(f.read()))
        except Exception:
            continue
    _vec_mem = recs
    # Persist pack async so this cold search isn't billed for pack I/O.
    if len(recs) >= 32:
        try:
            threading.Thread(
                target=_write_vectors_pack,
                args=(list(recs),),
                daemon=True,
                name="pb-vec-pack",
            ).start()
        except Exception:
            pass
    return recs


def search_vectors(text: str, limit: int = 20) -> list[dict[str, Any]]:
    """Cosine search over all stored embeddings (memory-cached index)."""
    ensure_tree()
    vocab = load_vocab()
    q = compute_tfidf(tokenize(text), vocab)
    if not q:
        return []
    hits: list[tuple[float, dict]] = []
    for rec in _all_vectors():
        score = cosine(q, rec.get("vector") or {})
        if score <= 0:
            continue
        hits.append((score, {"id": rec.get("id"), "score": score, "dims": rec.get("dims")}))
    hits.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in hits[:limit]]


def _prune_orphan_vectors(keep_sids: set[str] | None = None) -> int:
    """Delete embedding files not belonging to keep_sids (defaults to all node ids)."""
    if keep_sids is None:
        keep_sids = {safe_id(n["id"]) for n in load_all_nodes() if n.get("id")}
    pruned = 0
    d = emb_dir()
    for fp in list(d.glob("*.json")):
        if fp.name.startswith("_"):
            continue
        if fp.stem not in keep_sids:
            try:
                fp.unlink()
                pruned += 1
            except OSError:
                pass
    if pruned:
        invalidate_vector_cache()
    return pruned


def reindex_all(
    limit: int | None = None,
    *,
    include_structural: bool = True,
) -> dict[str, Any]:
    """Rebuild vectors for nodes. Default: every node (max coverage).

    Set include_structural=False to skip pure Group/Repo/Space shells without content.
    Full reindex (limit=None) rebuilds vocab once, overwrites all vectors, prunes orphans
    so status().vectors matches node count after concert/swarm lag.

    Bulk path avoids per-node vocab saves. Cross-process lock prevents concurrent
    reindex/doctor from destroying mid-flight vectors (no wipe-before-write).
    """
    lock_fh = None
    try:
        lock_fh = _acquire_reindex_lock(timeout_s=180.0)
    except TimeoutError as e:
        return {
            "reindexed": 0,
            "error": str(e),
            "vectors": status().get("vectors"),
            "total_nodes": len(load_all_nodes()),
        }

    try:
        nodes = load_all_nodes()
        if not include_structural:
            ranked = []
            for n in nodes:
                if n.get("type") in (
                    "Group",
                    "Subgroup",
                    "JiraProject",
                    "Space",
                    "Branch",
                    "Repo",
                ) and not n.get("content_path"):
                    continue
                ranked.append(n)
            nodes = ranked or nodes
        if limit:
            nodes = nodes[:limit]
        full = limit is None

        # Phase 1: tokenize outside lock (I/O heavy)
        prepared: list[tuple[str, list[str]]] = []
        for node in nodes:
            nid = node.get("id")
            if not nid:
                continue
            prepared.append((str(nid), tokenize(_load_text_for_node(node))))

        # Phase 2: build DF / vocab in one pass
        df: dict[str, int] = {}
        for _, tokens in prepared:
            for term in set(tokens):
                df[term] = int(df.get(term, 0)) + 1
        if len(df) > 200000:
            rare = [k for k, v in df.items() if v <= 1]
            for k in rare[: max(0, len(df) - 150000)]:
                df.pop(k, None)
        vocab: dict[str, Any] = {
            "df": df,
            "n_docs": len(prepared),
            "updated_at": utc_now(),
        }

        # Phase 3: overwrite vectors (no pre-wipe — concurrent readers keep coverage)
        global _vec_mem
        recs: list[dict[str, Any]] = []
        with _lock:
            invalidate_vector_cache()
            # Drop pack only; keep per-node files until overwritten/pruned
            _drop_vectors_pack()
            save_vocab(vocab)
            now = utc_now()
            for nid, tokens in prepared:
                vec = compute_tfidf(tokens, vocab)
                rec = {
                    "id": nid,
                    "dims": len(vec),
                    "vector": vec,
                    "token_count": len(tokens),
                    "updated_at": now,
                    "algo": "tfidf-l2-v1",
                }
                write_json(vector_path(nid), rec)
                recs.append(rec)
            _vec_mem = recs
            if recs:
                _write_vectors_pack(recs)

        pruned = 0
        missing: list[dict[str, Any]] = []
        if full:
            # Parity vs *current* graph only. Do not retain prepared ids that
            # disappeared mid-reindex (that left vectors = nodes+1 flakes).
            live = [nd for nd in load_all_nodes() if nd.get("id")]
            keep = {safe_id(nd["id"]) for nd in live}
            pruned = _prune_orphan_vectors(keep)
            if pruned:
                _vec_mem = None

            # Fill any missing vectors if nodes arrived mid-reindex
            for nd in live:
                nid = str(nd["id"])
                if not vector_path(nid).exists():
                    missing.append(nd)
            for nd in missing:
                upsert_vector(str(nd["id"]), node=nd)

            # Second pass: re-snapshot live set (writers during fill) and re-prune
            live2 = [nd for nd in load_all_nodes() if nd.get("id")]
            keep2 = {safe_id(nd["id"]) for nd in live2}
            pruned += _prune_orphan_vectors(keep2)
            for nd in live2:
                nid = str(nd["id"])
                if not vector_path(nid).exists():
                    upsert_vector(nid, node=nd)
                    missing.append(nd)

            _vec_mem = None
            try:
                fresh = _all_vectors()
                if fresh:
                    _write_vectors_pack(fresh)
            except Exception:
                pass

        st = status()
        return {
            "reindexed": len(prepared),
            "pruned_orphans": pruned,
            "filled_missing": len(missing) if full else 0,
            "vectors": st.get("vectors"),
            "vocab_terms": len(load_vocab().get("df") or {}),
            "include_structural": include_structural,
            "total_nodes": len(load_all_nodes()),
            "parity": st.get("parity"),
        }
    finally:
        _release_reindex_lock(lock_fh)


def status() -> dict[str, Any]:
    ensure_tree()
    n = len([p for p in emb_dir().glob("*.json") if not p.name.startswith("_")])
    v = load_vocab()
    try:
        nodes_n = len(load_all_nodes())
    except Exception:
        nodes_n = None
    backend = embed_backend()
    return {
        "vectors": n,
        "nodes": nodes_n,
        "parity": (nodes_n == n) if nodes_n is not None else None,
        "vocab_terms": len(v.get("df") or {}),
        "n_docs": v.get("n_docs"),
        "algo": "tfidf-l2-v1",
        "embed_backend": backend,
        "titan_available": backend == "bedrock-titan",
        "path": str(emb_dir()),
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["status", "reindex", "search"])
    ap.add_argument(
        "query",
        nargs="?",
        default="",
        help="Search text (search cmd); same as --text",
    )
    ap.add_argument("--text", default="", help="Search text (alias of positional query)")
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args()
    text = (args.text or args.query or "").strip()
    if args.cmd == "status":
        print(json.dumps(status(), indent=2))
    elif args.cmd == "reindex":
        print(json.dumps(reindex_all(args.limit if args.limit != 15 else None), indent=2))
    else:
        print(json.dumps(search_vectors(text, limit=args.limit), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
