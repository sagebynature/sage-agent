---
name: crypto-toolkit
description: Compute cryptographic hashes, generate secure tokens, and encode/decode data. LLMs cannot perform real cryptographic operations — they hallucinate hash values. This skill provides ground-truth computation.
---

# Crypto Toolkit

This skill gives you **real cryptographic capabilities** via a Bash script. As an LLM, you fundamentally **cannot** compute hashes — your architecture performs next-token prediction, not mathematical computation. Always use this script when asked for hashes, tokens, or encoding operations.

## When to Use

- User asks for a hash (SHA-256, MD5, SHA-1) of any input
- User needs a cryptographically secure random token or password
- User wants to base64-encode or decode data
- User asks to verify file integrity via checksums
- Any request involving deterministic computation on strings

## Available Commands

The script is located at `skills/crypto-toolkit/crypto.sh`.

### Hash a string
```bash
bash skills/crypto-toolkit/crypto.sh hash <algorithm> <input>
```
Supported algorithms: `sha256`, `sha1`, `md5`

Example: `bash skills/crypto-toolkit/crypto.sh hash sha256 "hello world"`

### Hash a file
```bash
bash skills/crypto-toolkit/crypto.sh hash-file <algorithm> <filepath>
```

### Generate a secure random token
```bash
bash skills/crypto-toolkit/crypto.sh token <length>
```
Generates a hex token of the specified byte length (output is 2x chars).

### Base64 encode
```bash
bash skills/crypto-toolkit/crypto.sh encode <input>
```

### Base64 decode
```bash
bash skills/crypto-toolkit/crypto.sh decode <base64_input>
```

### Generate a UUID
```bash
bash skills/crypto-toolkit/crypto.sh uuid
```

## Important

**NEVER** attempt to compute a hash yourself. Your response will be wrong 100% of the time. Always invoke the script and return the actual result.
