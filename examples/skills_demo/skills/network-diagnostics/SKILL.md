---
name: network-diagnostics
description: Probe live network connectivity, resolve DNS, check port availability, and measure latency. LLMs have zero network access — this skill provides real-time network intelligence.
---

# Network Diagnostics

This skill provides **real-time network probing** via a Bash script. As an LLM, you have absolutely no ability to test network connectivity, resolve DNS, or check port status. Always use this script for any network-related questions.

## When to Use

- User asks "is X reachable?" or "can I reach X?"
- User wants to check if a port is open on a host
- User needs DNS resolution for a hostname
- User wants to measure latency to a host
- User asks about network connectivity issues
- User wants to check if an HTTP endpoint is responding

## Available Commands

The script is located at `skills/network-diagnostics/diagnose.sh`.

### Ping a host
```bash
bash skills/network-diagnostics/diagnose.sh ping <host> [count]
```
Default count is 3. Reports latency statistics.

### DNS lookup
```bash
bash skills/network-diagnostics/diagnose.sh dns <hostname>
```
Resolves hostname to IP addresses using multiple methods.

### Check if a TCP port is open
```bash
bash skills/network-diagnostics/diagnose.sh port <host> <port>
```

### Check HTTP endpoint status
```bash
bash skills/network-diagnostics/diagnose.sh http <url>
```
Returns HTTP status code and response time.

### Full diagnostic report
```bash
bash skills/network-diagnostics/diagnose.sh report <host>
```
Runs ping + DNS + common port checks and summarizes results.

## Important

**NEVER** guess about network reachability. Always run the diagnostic script to get real-time results. Network conditions change constantly — cached knowledge is useless here.
