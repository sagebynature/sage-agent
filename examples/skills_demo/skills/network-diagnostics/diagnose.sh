#!/usr/bin/env bash
# diagnose.sh — Network diagnostic tool for the Apollo Agent network-diagnostics skill.
# Usage: bash diagnose.sh <command> [args...]

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: diagnose.sh <command> [args...]

Commands:
  ping <host> [count]       Ping a host (default count: 3)
  dns <hostname>            DNS lookup
  port <host> <port>        Check if a TCP port is open
  http <url>                Check HTTP endpoint status
  report <host>             Full diagnostic report

Examples:
  diagnose.sh ping google.com
  diagnose.sh dns github.com
  diagnose.sh port github.com 443
  diagnose.sh http https://api.github.com
  diagnose.sh report github.com
EOF
    exit 1
}

[[ $# -lt 1 ]] && usage

command="$1"
shift

case "$command" in
    ping)
        [[ $# -lt 1 ]] && { echo "Error: ping requires <host>"; exit 1; }
        host="$1"
        count="${2:-3}"
        echo "=== Ping: $host (count=$count) ==="
        if ping -c "$count" -W 5 "$host" 2>&1; then
            echo ""
            echo "Result: Host is REACHABLE"
        else
            echo ""
            echo "Result: Host is UNREACHABLE"
        fi
        ;;

    dns)
        [[ $# -lt 1 ]] && { echo "Error: dns requires <hostname>"; exit 1; }
        hostname="$1"
        echo "=== DNS Lookup: $hostname ==="

        # Try getent first (most portable), fall back to host, then nslookup
        if command -v getent &>/dev/null; then
            echo "--- getent hosts ---"
            getent hosts "$hostname" 2>&1 || echo "(no result)"
        fi

        if command -v host &>/dev/null; then
            echo "--- host ---"
            host "$hostname" 2>&1 || echo "(no result)"
        elif command -v nslookup &>/dev/null; then
            echo "--- nslookup ---"
            nslookup "$hostname" 2>&1 || echo "(no result)"
        fi
        ;;

    port)
        [[ $# -lt 2 ]] && { echo "Error: port requires <host> <port>"; exit 1; }
        host="$1"
        port="$2"
        echo "=== Port Check: $host:$port ==="

        # Use /dev/tcp (bash built-in), timeout after 5 seconds
        if timeout 5 bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null; then
            echo "Result: Port $port is OPEN on $host"
        else
            echo "Result: Port $port is CLOSED or FILTERED on $host"
        fi
        ;;

    http)
        [[ $# -lt 1 ]] && { echo "Error: http requires <url>"; exit 1; }
        url="$1"
        echo "=== HTTP Check: $url ==="

        if command -v curl &>/dev/null; then
            start_time=$(date +%s%N 2>/dev/null || echo "0")
            status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")
            end_time=$(date +%s%N 2>/dev/null || echo "0")

            if [[ "$start_time" != "0" && "$end_time" != "0" ]]; then
                elapsed_ms=$(( (end_time - start_time) / 1000000 ))
                echo "Status Code: $status_code"
                echo "Response Time: ${elapsed_ms}ms"
            else
                echo "Status Code: $status_code"
            fi

            if [[ "$status_code" =~ ^2 ]]; then
                echo "Result: Endpoint is HEALTHY"
            elif [[ "$status_code" == "000" ]]; then
                echo "Result: Endpoint is UNREACHABLE"
            else
                echo "Result: Endpoint returned non-2xx status"
            fi
        else
            echo "Error: curl is not installed"
            exit 1
        fi
        ;;

    report)
        [[ $# -lt 1 ]] && { echo "Error: report requires <host>"; exit 1; }
        host="$1"
        echo "╔══════════════════════════════════════════╗"
        echo "║     Network Diagnostic Report            ║"
        echo "║     Host: $host"
        echo "║     Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
        echo "╚══════════════════════════════════════════╝"
        echo ""

        # DNS
        echo "── DNS Resolution ──"
        ip=$(getent hosts "$host" 2>/dev/null | awk '{print $1; exit}' || echo "FAILED")
        if [[ "$ip" == "FAILED" || -z "$ip" ]]; then
            echo "  DNS: FAILED to resolve $host"
        else
            echo "  DNS: $host → $ip"
        fi
        echo ""

        # Ping
        echo "── Connectivity ──"
        if ping -c 2 -W 3 "$host" &>/dev/null; then
            avg=$(ping -c 2 -W 3 "$host" 2>/dev/null | tail -1 | awk -F'/' '{print $5}')
            echo "  Ping: REACHABLE (avg ${avg}ms)"
        else
            echo "  Ping: UNREACHABLE"
        fi
        echo ""

        # Common ports
        echo "── Port Scan ──"
        for port in 22 80 443 8080; do
            if timeout 3 bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null; then
                echo "  Port $port: OPEN"
            else
                echo "  Port $port: CLOSED"
            fi
        done
        echo ""
        echo "── End of Report ──"
        ;;

    *)
        echo "Error: unknown command '$command'"
        usage
        ;;
esac
