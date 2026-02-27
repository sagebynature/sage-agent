# Sage CI & Headless Mode (`sage exec`)

The `sage exec` command is the primary entry point for running Sage agents in non-interactive environments such as CI/CD pipelines, automated cron jobs, or embedded within other applications.

While `sage agent run` is optimized for interactive CLI use and `sage tui` provides a rich terminal interface, `sage exec` is designed for **predictable output, strict error handling, and automated lifecycle management**.

---

## 1. When to use `sage exec`

Use `sage exec` when you need to:
- Run an agent as part of a **GitHub Action** or GitLab CI pipeline.
- Pipe data into an agent via `stdin` from another tool.
- Parse agent output programmatically using `jsonl` and tools like `jq`.
- Enforce strict timeouts and handle specific failure modes via exit codes.
- Ensure the agent never prompts for interactive input (default "deny" policy).

---

## 2. CLI Reference

The command follows the pattern: `sage exec <config_path> [OPTIONS]`

### Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `config_path` | Path to the `AGENTS.md` configuration file for the agent. | Yes |

### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--input` | `-i` | TEXT | None | Input string to send to the agent. |
| `--stdin` | | Flag | False | Read user input from `stdin` instead of `--input`. |
| `--output` | `-o` | CHOICE | `text` | Output format: `text`, `jsonl`, or `quiet`. |
| `--timeout`| | FLOAT | 0 | Max wall-clock seconds. Exit code 5 on breach. (0 = no limit) |
| `--yes` | | Flag | False | Auto-approve all `ASK`-gated tool calls (Danger: non-interactive override). |
| `--deny-all`| | Flag | True | Auto-deny `ASK`-gated calls. This is the default behavior. |

---

## 3. Exit Codes

`sage exec` uses specific exit codes to help scripts determine why an agent stopped. These are defined in `sage/cli/exit_codes.py` as `SageExitCode`.

| Code | Enum Name | Meaning |
|------|-----------|---------|
| `0` | `SUCCESS` | Agent completed successfully with a final response. |
| `1` | `ERROR` | Generic or unclassified internal Sage error. |
| `2` | `CONFIG_ERROR` | Configuration loading or YAML validation failed. |
| `3` | `PERMISSION_DENIED` | A critical tool execution was denied by the permission policy. |
| `4` | `MAX_TURNS` | Agent reached `max_turns` without producing a final response. |
| `5` | `TIMEOUT` | Execution exceeded the value set by `--timeout`. |
| `6` | `TOOL_ERROR` | A tool invocation failed and the agent could not recover. |
| `7` | `PROVIDER_ERROR` | The LLM provider (e.g., OpenAI, Anthropic) call failed. |

---

## 4. Output Modes

The `--output` flag determines how `sage exec` communicates with the calling process.

### `text` (Default)
Prints only the agent's final response to `stdout`. All intermediate lifecycle events (tool calls, internal reasoning) are suppressed.

**Example:**
```bash
$ sage exec AGENTS.md -i "What is 2+2?"
The answer is 4.
```

### `jsonl`
Outputs newline-delimited JSON. Every significant event in the agent's lifecycle is emitted as a JSON object. This is the preferred mode for programmatic integration.

**Example Output:**
```json
{"event": "start", "data": {"agent": "assistant"}}
{"event": "tool_call", "data": {"tool": "shell", "args": {"command": "ls"}}}
{"event": "tool_result", "data": {"output": "README.md\nsrc/"}}
{"event": "result", "data": {"output": "I see a README and a src directory."}}
```

### `quiet`
Suppresses all output to `stdout`. Useful when you only care about the exit code (e.g., a smoke test or health check).

**Example:**
```bash
$ sage exec AGENTS.md -i "Test" --output quiet
$ echo $?
0
```

---

## 5. Timeout Behavior

Headless agents are often subject to strict time limits. The `--timeout` option enforces an `asyncio` wall-clock limit on the entire execution (including all tool calls and LLM requests).

- If the timeout is reached, the agent is immediately cancelled.
- The command exits with **Exit Code 5** (`TIMEOUT`).
- Any partial output generated before the timeout may still be visible if using `jsonl` mode.

---

## 6. Permission Policy (ASK/DENY)

By default, `sage exec` operates in a "safe" mode where any tool call requiring user approval (configured as `ask` in `AGENTS.md`) is **automatically denied**.

- This prevents the process from hanging indefinitely while waiting for a terminal that isn't there.
- Use `--deny-all` to explicitly state this behavior (though it is the default).
- Use `--yes` to auto-approve all gated calls. **Warning:** Only use `--yes` in trusted environments where you have verified the agent's instructions and tool access.

---

## 7. Usage Examples

### Basic Execution
```bash
sage exec ./my-agent/AGENTS.md --input "Generate a summary of README.md"
```

### Piping Data via Stdin
You can pipe input into an agent using the `--stdin` flag. Use this instead of `--input` when the input comes from another command.
```bash
cat logs/error.log | sage exec AGENTS.md --stdin
```

### Parsing JSONL with `jq`
Extract only the final result from a complex agent run:
```bash
sage exec AGENTS.md -i "Analyze the codebase" --output jsonl | jq -r 'select(.event=="result") | .data.output'
```

---

## 8. GitHub Actions Integration

To use Sage in a GitHub Action, you should install `sage-agent` and run it with `uv` for speed and reliability.

```yaml
name: Sage Code Review
on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      - name: Run Sage
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          uv pip install sage-agent
          uv run sage exec AGENTS.md \
            --input "Review the changes in this PR." \
            --deny-all \
            --output jsonl \
            --timeout 300 \
            | tee review.jsonl
```

---

## 9. Scripting & Error Handling

When embedding Sage in a bash script, always check the exit code to handle different failure modes gracefully.

```bash
#!/bin/bash

# Run the agent
sage exec docs-agent/AGENTS.md -i "Check for broken links" --timeout 60

EXIT_CODE=$?

case $EXIT_CODE in
  0)
    echo "Check completed successfully."
    ;;
  2)
    echo "Error: Configuration is invalid."
    exit 1
    ;;
  5)
    echo "Error: The agent timed out."
    exit 1
    ;;
  *)
    echo "Sage failed with exit code $EXIT_CODE"
    exit $EXIT_CODE
    ;;
esac
```

---

## 10. Summary Checklist for CI

- [ ] Use `sage exec` instead of `sage agent run`.
- [ ] Set a `--timeout` to prevent hung runners.
- [ ] Use `--output jsonl` if you need to parse the result.
- [ ] Ensure `OPENAI_API_KEY` (or relevant provider keys) are in the environment secrets.
- [ ] Check exit codes for automated failure reporting.
