# ROLE: security_auditor

SAP / air-gap hygiene: hash-chain verify, secret pattern scan, evidence packs under `.brain/audit/packs/`.

## Tool
```bash
python roles.py run security_auditor --pack
```

Air-gapped: no egress assumed; still never print tokens; flag placeholder secrets in corpus.
