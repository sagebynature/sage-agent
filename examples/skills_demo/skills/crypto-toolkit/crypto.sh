#!/usr/bin/env bash
# crypto.sh — Cryptographic toolkit: hashing, tokens, base64
# Usage: crypto.sh <operation> [args...]

set -euo pipefail

OPERATION="${1:-}"

case "$OPERATION" in
    sha256)
        if [ -z "${2:-}" ]; then
            echo "Usage: crypto.sh sha256 <string>" >&2
            exit 1
        fi
        echo -n "$2" | sha256sum | awk '{print $1}'
        ;;
    md5)
        if [ -z "${2:-}" ]; then
            echo "Usage: crypto.sh md5 <string>" >&2
            exit 1
        fi
        echo -n "$2" | md5sum | awk '{print $1}'
        ;;
    token)
        BYTES="${2:-32}"
        openssl rand -hex "$BYTES"
        ;;
    base64enc)
        if [ -z "${2:-}" ]; then
            echo "Usage: crypto.sh base64enc <string>" >&2
            exit 1
        fi
        echo -n "$2" | base64
        ;;
    base64dec)
        if [ -z "${2:-}" ]; then
            echo "Usage: crypto.sh base64dec <string>" >&2
            exit 1
        fi
        echo -n "$2" | base64 --decode
        ;;
    *)
        echo "Usage: crypto.sh <sha256|md5|token|base64enc|base64dec> [args...]" >&2
        echo ""
        echo "Operations:"
        echo "  sha256 <string>    — SHA-256 hash"
        echo "  md5 <string>       — MD5 hash"
        echo "  token <bytes>      — secure random hex token"
        echo "  base64enc <string> — base64 encode"
        echo "  base64dec <string> — base64 decode"
        exit 1
        ;;
esac
