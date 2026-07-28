#!/usr/bin/env bash
# Post Private Brain launch to X via official xurl (no customer names).
set -euo pipefail
export PATH="$HOME/bin:$PATH"
IMG="${1:-$HOME/private-brain-public/images/private-brain-rag-dag.png}"
if [[ ! -f "$IMG" ]]; then
  IMG="/Users/kevinnichols/private-brain-public/images/private-brain-rag-dag.png"
fi

TEXT='Shipped open source: Private Brain

Codex sideload → local RAG-DAG organism.
Install once. Open Codex. Talk.
Answers either cite evidence or refuse.

Mac ≡ Windows. One zip per OS → START → go.

Windows: github.com/KRNichols/private-brain/releases/latest/download/PrivateBrain-WINDOWS-READY.zip
Mac: github.com/KRNichols/private-brain/releases/latest/download/PrivateBrain-MAC-READY.zip

CI green (Nuclear Winter on free runners).

Repo: github.com/KRNichols/private-brain'

# Prefer media upload + tweet if supported
if xurl media upload --help >/dev/null 2>&1; then
  MEDIA_JSON=$(xurl media upload "$IMG" 2>&1) || true
  echo "$MEDIA_JSON"
  MID=$(echo "$MEDIA_JSON" | python3 -c "import sys,json,re; t=sys.stdin.read();
import json
try:
  d=json.loads(t)
  print(d.get('media_id') or d.get('media_id_string') or d.get('data',{}).get('id') or '')
except Exception:
  m=re.search(r'\"?(?:media_id(?:_string)?|id)\"?\s*[:=]\s*\"?(\d+)', t)
  print(m.group(1) if m else '')" 2>/dev/null || true)
  if [[ -n "${MID:-}" ]]; then
    xurl -X POST /2/tweets -d "$(python3 -c "import json,os; print(json.dumps({'text':os.environ['TEXT'],'media':{'media_ids':[os.environ['MID']]}}))" MID="$MID" TEXT="$TEXT")"
    exit 0
  fi
fi

# Text-only fallback
xurl post "$TEXT"
