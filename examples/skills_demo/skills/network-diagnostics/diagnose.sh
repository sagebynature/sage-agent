#!/usr/bin/env bash
# diagnose.sh — Network diagnostics: ping, DNS, port check, HTTP headers
# Usage: diagnose.sh <operation> [args...]

set -uo pipefail

OPERATION="${1:-}"

do_ping() {
    local host="$1"
    echo "=== Ping: $host ==="
    ping -c 3 -W 3 "$host" 2>&1 || echo "  [ping failed or host unreachable]"
}

do_dns() {
    local host="$1"
    echo "=== DNS: $host ==="
    dig +short "$host" 2>&1 || echo "  [dig failed]"
}

do_port() {
    local host="$1"
    local port="$2"
    echo "=== Port check: $host:$port ==="
    if nc -z -w3 "$host" "$port" 2>/dev/null; then
        echo "  open"
    else
        echo "  closed"
    fi
}

do_http() {
    local url="$1"
    echo "=== HTTP headers: $url ==="
    curl -sI --max-time 5 "$url" 2>&1 | head -5 || echo "  [curl failed]"
}

do_report() {
    local host="$1"
    echo "=============================="
    echo " Network Report: $host"
    echo "=============================="
    do_ping "$host"
    echo ""
    do_dns "$host"
    echo ""
    do_port "$host" 80
    echo ""
    do_port "$host" 443
    echo ""
    do_http "https://$host"
}

case "$OPERATION" in
    ping)
        if [ -z "${2:-}" ]; then
            echo "Usage: diagnose.sh ping <host>" >&2
            exit 1
        fi
        do_ping "$2"
        ;;
    dns)
        if [ -z "${2:-}" ]; then
            echo "Usage: diagnose.sh dns <host>" >&2
            exit 1
        fi
        do_dns "$2"
        ;;
    port)
        if [ -z "${2:-}" ] || [ -z "${3:-}" ]; then
            echo "Usage: diagnose.sh port <host> <port>" >&2
            exit 1
        fi
        do_port "$2" "$3"
        ;;
    http)
        if [ -z "${2:-}" ]; then
            echo "Usage: diagnose.sh http <url>" >&2
            exit 1
        fi
        do_http "$2"
        ;;
    report)
        if [ -z "${2:-}" ]; then
            echo "Usage: diagnose.sh report <host>" >&2
            exit 1
        fi
        do_report "$2"
        ;;
    *)
        echo "Usage: diagnose.sh <ping|dns|port|http|report> [args...]" >&2
        echo ""
        echo "Operations:"
        echo "  ping <host>          — ping 3 packets"
        echo "  dns <host>           — DNS resolution"
        echo "  port <host> <port>   — TCP port check"
        echo "  http <url>           — HTTP response headers"
        echo "  report <host>        — full diagnostic report"
        exit 1
        ;;
esac
