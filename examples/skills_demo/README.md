# Skills Demo — Sage

This demo shows a Sage agent augmented with **skills** — external scripts that
give it real-world capabilities no LLM has natively.  The agent is a DevOps
assistant that refuses to hallucinate answers and instead delegates computation
to the appropriate skill script.

## Why Skills?

LLMs predict tokens — they cannot:

- Compute cryptographic hashes (they fabricate plausible-looking values)
- Probe live network connectivity (they have no network access)
- Read files from disk (they have no filesystem access)
- Perform reliable arithmetic on real datasets

Skills fill these gaps by running real code and returning ground-truth results.

## Directory Structure

```
skills_demo/
├── AGENTS.md               # Agent definition (model, tools, system prompt)
├── run_demo.py             # Interactive demo runner
├── skills/
│   ├── crypto-toolkit/     # SHA-256/MD5 hashing, secure tokens, base64
│   │   ├── SKILL.md
│   │   └── crypto.sh
│   ├── network-diagnostics/# Ping, DNS, port checks, latency
│   │   ├── SKILL.md
│   │   └── diagnose.sh
│   ├── dependency-auditor/ # Audit package.json / requirements.txt
│   │   ├── SKILL.md
│   │   └── audit.js
│   └── data-cruncher/      # Statistical analysis on CSV/JSON
│       ├── SKILL.md
│       └── analyze.py
└── sample_data/
    ├── metrics.csv         # Server metrics (cpu, memory, response times)
    ├── package.json        # Sample Node.js project
    ├── requirements.txt    # Sample Python project
    └── server_logs.txt     # Sample log file
```

## Prerequisites

```bash
# From the project root
pip install sage-agent    # or: make install

# Set your LLM provider key
export OPENAI_API_KEY=sk-...      # or AZURE_OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
# Alternatively, copy .env.example → .env and fill in the key
```

Node.js is required for the dependency-auditor skill (`audit.js`).

## Running the Demo

```bash
# Run all four scenarios end-to-end
python3 examples/skills_demo/run_demo.py

# Run a single scenario
python3 examples/skills_demo/run_demo.py --scenario crypto
python3 examples/skills_demo/run_demo.py --scenario network
python3 examples/skills_demo/run_demo.py --scenario dependencies
python3 examples/skills_demo/run_demo.py --scenario data

# Interactive chat mode
python3 examples/skills_demo/run_demo.py --interactive

# Override the model
python3 examples/skills_demo/run_demo.py --model openai/gpt-4o

# Enable debug logging for agent internals
python3 examples/skills_demo/run_demo.py --verbose
```

## Demo Scenarios

| Scenario | Skill | What it proves |
|---|---|---|
| `crypto` | `crypto-toolkit` (Bash) | Real SHA-256/MD5 hashes and CSPRNG tokens |
| `network` | `network-diagnostics` (Bash) | Live ping, DNS, and port probing |
| `dependencies` | `dependency-auditor` (Node.js) | Actual file parsing of `package.json` / `requirements.txt` |
| `data` | `data-cruncher` (Python) | Precise statistics — mean, std dev, percentiles, outliers |

## Skills

### `crypto-toolkit`

Wraps standard Unix utilities (`sha256sum`, `openssl`, `base64`) to provide
deterministic cryptographic output the LLM could never produce on its own.

Example prompts:
- *"What is the SHA-256 hash of 'Hello, Sage!'?"*
- *"Generate a 32-byte secure random token for use as an API key."*
- *"Base64 encode the string 'skills give agents superpowers'."*

### `network-diagnostics`

Uses `ping`, `dig`, `nc`, and `curl` to probe real network state at runtime.

Example prompts:
- *"Is google.com reachable? What's the latency?"*
- *"Run a full diagnostic report on github.com."*

### `dependency-auditor`

Parses `package.json` and `requirements.txt` with Node.js to report dependency
counts, version patterns (exact, caret, tilde, unpinned), and risk flags.

Example prompts:
- *"Audit the dependencies in sample_data/package.json."*
- *"Are there any unpinned packages in sample_data/requirements.txt?"*

### `data-cruncher`

Runs a Python/pandas analysis pipeline on CSV or JSON files, computing
descriptive statistics, correlations, and IQR-based outlier detection.

Example prompts:
- *"Give me a full statistical summary of sample_data/metrics.csv."*
- *"What's the correlation between cpu_usage and response_time_ms?"*
- *"Are there any outliers in the response_time_ms column?"*

## How It Works

1. `Agent.from_config("AGENTS.md")` loads the agent and auto-discovers the
   `skills/` directory alongside it.
2. Each `SKILL.md` is parsed for its `name`, `description`, and usage
   instructions, which are injected into the agent's system prompt.
3. When the LLM receives a prompt that matches a skill, it calls the `shell`
   tool to execute the corresponding script (`crypto.sh`, `diagnose.sh`, etc.).
4. The script output is returned to the LLM, which formats it for the user.

See [ADR-009](../../.docs/adrs/009-markdown-agent-definitions.md) and
[ADR-010](../../.docs/adrs/010-directory-subagents-and-delegate-tool.md) for the
design rationale behind skills and agent definitions.
