---
name: crypto-toolkit
description: "Compute SHA-256/MD5 hashes, generate secure random tokens, and base64 encode/decode strings"
version: "1.0.0"
---

## Usage
Run `skills/crypto-toolkit/crypto.sh <operation> [args]` via the shell tool.

Operations:
- `sha256 <string>` — SHA-256 hash of the string
- `md5 <string>` — MD5 hash of the string
- `token <bytes>` — secure random hex token of given byte length
- `base64enc <string>` — base64 encode a string
- `base64dec <string>` — base64 decode a string

## Examples
```bash
skills/crypto-toolkit/crypto.sh sha256 "Hello, Sage!"
skills/crypto-toolkit/crypto.sh token 32
skills/crypto-toolkit/crypto.sh base64enc "skills give agents superpowers"
```
