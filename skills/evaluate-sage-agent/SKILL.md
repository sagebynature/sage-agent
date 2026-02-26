---
name: evaluate-sage-agent
description: Validate, benchmark, and optimize a Sage agent configuration using sage-evaluator. Runs a full evaluation pipeline including format validation, suggestion generation, model benchmarking, and before/after comparison.
---

# Evaluate Agent

You are running a structured agent evaluation workflow. Follow each phase in order. Present results to the user between phases and get confirmation before proceeding.

## Phase 0: Ensure sage-evaluator is installed

Run this check first:

```bash
python -c "import sage_evaluator" 2>/dev/null || uv pip install sage-evaluator
```

If installation fails, stop and tell the user to install manually: `uv pip install sage-evaluator`

## Phase 1: Validate

Ask the user which agent to evaluate. They should provide a path to an `AGENTS.md` file or a directory containing one.

Run validation:

```bash
evaluate validate <path> --format json
```

- If validation **fails** (exit code 1), show the errors and stop. The agent must fix config errors before evaluation can proceed.
- If validation **passes**, summarize any warnings or info notices, then proceed.

## Phase 2: Analyze and Suggest

### Step 2a: Determine rubric

Read the agent's `AGENTS.md` file. Look at the `name`, `description`, and the markdown body (system prompt). Choose a rubric:

- If the agent is about **coding, engineering, development, debugging, code review, or programming** → use rubric `code_generation`
- If the agent is about **answering questions, research, knowledge, Q&A, or information retrieval** → use rubric `qa`
- Otherwise → use rubric `default`

Tell the user which rubric you selected and why. Let them override if they disagree.

### Step 2b: Run suggestions

```bash
evaluate suggest <path> --format json
```

Present the suggestions grouped by category:
- **Prompt improvements** — rewrites for clarity or precision
- **Tool extractions** — procedures that should become @tool functions
- **Guardrails** — safety or validation checks to add
- **Architecture** — model selection, subagent structure, tuning

For each suggestion, show the title, impact level, and a brief description. If there are before/after examples, show them.

Ask the user: **"Would you like me to apply any of these suggestions?"**

- If yes, proceed to Phase 3
- If no, ask if they want to skip to benchmarking (Phase 4) or stop

## Phase 3: Apply Changes and Version

### Step 3a: Create versioned backup

Before modifying the agent config, create a sequential versioned copy:

1. Check for existing versions: `AGENTS.v1.md`, `AGENTS.v2.md`, etc.
2. Find the next available version number
3. Copy the current `AGENTS.md` to `AGENTS.v<N>.md`

Example:
```bash
# If no versions exist yet:
cp AGENTS.md AGENTS.v1.md

# If AGENTS.v1.md already exists:
cp AGENTS.md AGENTS.v2.md
```

### Step 3b: Apply suggestions

Edit the original `AGENTS.md` to incorporate the accepted suggestions. Focus on:

- Rewriting prompt sections as suggested
- Adding permission or extension entries if recommended
- Adjusting model_params or max_turns if suggested
- Adding description if missing

After editing, run validation again to confirm the modified config is still valid:

```bash
evaluate validate <path>
```

### Step 3c: Re-validate

If validation fails after edits, fix the issues. Never leave the agent in a broken state.

## Phase 4: Benchmark

### Step 4a: Identify models

Read the agent's `model` field from the config. This is the **baseline model**.

Ask the user:

> Your agent uses `<model>` as its model. Would you like to benchmark against additional models for comparison?
>
> Options:
> 1. Just benchmark with the current model (baseline only)
> 2. I'll provide a list of models to compare
> 3. Discover available models from Azure (requires AZURE_AI_ACCOUNT_NAME)

**If option 2:** Ask the user for a comma-separated list of model IDs (e.g., `azure_ai/gpt-4o, azure_ai/claude-sonnet-4-6`).

**If option 3:** Run discovery:

```bash
evaluate discover --account-name $AZURE_AI_ACCOUNT_NAME --format json
```

Present the discovered models and let the user select which ones to include.

### Step 4b: Generate test task

Read the agent's system prompt and description. Generate a representative test task that would exercise the agent's core capabilities.

Present it to the user:

> Based on your agent's purpose, here's a suggested test task:
>
> **"<generated task>"**
>
> Would you like to use this task, or provide your own?

### Step 4c: Run benchmark

```bash
evaluate benchmark <path> \
  --intent "<task>" \
  --rubric <rubric> \
  -m <model1> -m <model2> \
  --format json
```

Present the results as a ranked table:
- Model name
- Quality score (if judge was used)
- Latency (ms)
- Token usage
- Estimated cost
- Composite score

Highlight the best-performing model and any notable findings (e.g., "Model X is 3x cheaper with only 5% lower quality").

## Phase 5: Compare (if changes were applied)

If Phase 3 created a versioned copy, run a before/after comparison:

```bash
evaluate compare <path>/AGENTS.v<N>.md <path>/AGENTS.md \
  --intent "<same task from Phase 4>" \
  --rubric <rubric> \
  -m <baseline model> \
  --format json
```

Present the comparison:
- **Before** (v<N>): quality, latency, cost
- **After** (current): quality, latency, cost
- **Delta**: improvement or regression in each metric

If the new version is worse, warn the user and offer to revert:

> The modified config scored lower than the original. Would you like to revert to the previous version?

## Phase 6: Summary

Present a final summary:

1. **Validation**: Pass/fail, number of issues found
2. **Suggestions**: Number of suggestions by category, how many were applied
3. **Benchmark**: Best model, quality score, cost per request
4. **Comparison** (if applicable): Before vs after delta
5. **Versioning**: Which version file was created

End with actionable next steps:
- If quality is low: suggest prompt rewrites or model upgrades
- If cost is high: suggest cheaper models that scored similarly
- If the agent has no permissions: suggest adding appropriate tool access
