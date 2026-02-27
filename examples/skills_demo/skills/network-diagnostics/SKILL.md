---
name: network-diagnostics
description: "Probe live network: ping hosts for latency, resolve DNS, check TCP port reachability, and fetch HTTP headers"
version: "1.0.0"
---

## Usage
Run `skills/network-diagnostics/diagnose.sh <operation> [args]` via the shell tool.

Operations:
- `ping <host>` — ping 3 packets, show round-trip latency
- `dns <host>` — DNS resolution via dig
- `port <host> <port>` — check if TCP port is open or closed
- `http <url>` — fetch HTTP response headers (first 5 lines)
- `report <host>` — run all checks (ping, dns, port 80, port 443, http)

## Examples
```bash
skills/network-diagnostics/diagnose.sh ping google.com
skills/network-diagnostics/diagnose.sh dns github.com
skills/network-diagnostics/diagnose.sh port github.com 443
skills/network-diagnostics/diagnose.sh report google.com
```
