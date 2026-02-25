#!/usr/bin/env bash
# crypto.sh — Cryptographic operations for the Sage Agent crypto-toolkit skill.
# Usage: bash crypto.sh <command> [args...]

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: crypto.sh <command> [args...]

Commands:
  hash <algorithm> <input>      Hash a string (sha256, sha1, md5)
  hash-file <algorithm> <path>  Hash a file
  token <bytes>                 Generate a secure random hex token
  encode <input>                Base64 encode a string
  decode <base64_input>         Base64 decode a string
  uuid                          Generate a UUID v4

Examples:
  crypto.sh hash sha256 "hello world"
  crypto.sh hash-file sha256 /etc/hostname
  crypto.sh token 32
  crypto.sh encode "secret message"
  crypto.sh decode "c2VjcmV0IG1lc3NhZ2U="
  crypto.sh uuid
EOF
    exit 1
}

[[ $# -lt 1 ]] && usage

command="$1"
shift

case "$command" in
    hash)
        [[ $# -lt 2 ]] && { echo "Error: hash requires <algorithm> <input>"; exit 1; }
        algo="$1"
        input="$2"
        case "$algo" in
            sha256) echo -n "$input" | sha256sum | awk '{print $1}' ;;
            sha1)   echo -n "$input" | sha1sum   | awk '{print $1}' ;;
            md5)    echo -n "$input" | md5sum     | awk '{print $1}' ;;
            *)      echo "Error: unsupported algorithm '$algo'. Use sha256, sha1, or md5."; exit 1 ;;
        esac
        ;;

    hash-file)
        [[ $# -lt 2 ]] && { echo "Error: hash-file requires <algorithm> <path>"; exit 1; }
        algo="$1"
        filepath="$2"
        [[ ! -f "$filepath" ]] && { echo "Error: file not found: $filepath"; exit 1; }
        case "$algo" in
            sha256) sha256sum "$filepath" | awk '{print $1}' ;;
            sha1)   sha1sum "$filepath"   | awk '{print $1}' ;;
            md5)    md5sum "$filepath"     | awk '{print $1}' ;;
            *)      echo "Error: unsupported algorithm '$algo'. Use sha256, sha1, or md5."; exit 1 ;;
        esac
        ;;

    token)
        [[ $# -lt 1 ]] && { echo "Error: token requires <bytes>"; exit 1; }
        bytes="$1"
        # Generate cryptographically secure random bytes and hex-encode
        head -c "$bytes" /dev/urandom | od -An -tx1 | tr -d ' \n'
        echo
        ;;

    encode)
        [[ $# -lt 1 ]] && { echo "Error: encode requires <input>"; exit 1; }
        echo -n "$1" | base64
        ;;

    decode)
        [[ $# -lt 1 ]] && { echo "Error: decode requires <base64_input>"; exit 1; }
        echo -n "$1" | base64 -d
        echo
        ;;

    uuid)
        # Generate UUID v4 using /dev/urandom
        python3 -c "import uuid; print(uuid.uuid4())" 2>/dev/null \
            || cat /proc/sys/kernel/random/uuid 2>/dev/null \
            || { echo "Error: cannot generate UUID on this system"; exit 1; }
        ;;

    *)
        echo "Error: unknown command '$command'"
        usage
        ;;
esac
