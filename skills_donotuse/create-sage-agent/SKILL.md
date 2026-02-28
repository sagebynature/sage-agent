---
name: create-sage-agent
description: Create a new Sage agent from a natural language description. Generates AGENTS.md with inferred config, identifies subagent opportunities, validates the result, and hands off to evaluate-sage-agent for optimization.
---

# Create Sage Agent

You are guiding the user through creating a new Sage agent. Follow each phase in order.

## Phase 1: Gather Intent

Ask the user:

> **What should this agent do?**
>
> Describe the agent's purpose, what tasks it should handle, and any specific tools or capabilities it needs. The more detail you provide, the better the generated config will be.

Wait for their response before proceeding.

## Phase 2: Analyze Intent

Read the user's description carefully. Determine:

### 2a: Core capabilities

From the description, identify what the agent needs:

| Signal in description | Permission to infer |
|---|---|
| read files, analyze code, review, inspect, search | `read: allow` |
| edit files, write code, refactor, modify, create files | `read: allow` and `edit: allow` |
| run commands, execute, build, test, deploy, install | `shell: allow` (or pattern-based for restricted commands) |
| fetch URLs, call APIs, search the web, HTTP requests | `web: allow` |
| remember context, recall past conversations, learn | `memory: allow` |
| delegate, coordinate, manage tasks | `task: allow` |

If the description has no tool signals, the agent will be text-only (no permission block).

### 2b: Subagent opportunities

Look for signs that the task should be decomposed:

**Multiple distinct responsibilities:**
If the description mentions several different roles (e.g., "research topics, write articles, and review for quality"), suggest breaking these into subagents:
- A parent coordinator that delegates
- Specialist subagents for each responsibility

**Different permission scopes:**
If different parts of the task need different tool access (e.g., "review code read-only, then run tests"), suggest separate subagents with tailored permissions.

**Pipeline patterns:**
If the description implies sequential stages (e.g., "first gather data, then analyze, then generate a report"), suggest subagents for each stage.

If you identify subagent opportunities, present them to the user:

> I notice this agent has multiple distinct responsibilities. I'd suggest breaking it into:
>
> - **<parent-name>** (coordinator): Delegates tasks to specialist subagents
>   - **<sub1-name>**: <responsibility> (permissions: <list>)
>   - **<sub2-name>**: <responsibility> (permissions: <list>)
>
> This gives each subagent focused permissions and a clear role. Would you like to use this structure, or keep it as a single agent?

### 2c: Rubric classification

Classify the agent for later evaluation:
- Coding/engineering/development → `code_generation`
- Q&A/research/knowledge → `qa`
- General purpose → `default`

### 2d: Complexity assessment

Estimate `max_turns` based on task complexity:
- Simple Q&A or text generation → `5`
- Moderate tool use (read files, search) → `10`
- Complex multi-step workflows → `15-20`

## Phase 3: Resolve Model

Determine the model to use:

```bash
python -c "
from sage.main_config import load_main_config, resolve_main_config_path
try:
    mc = load_main_config(resolve_main_config_path(None))
    print(mc.defaults.model if mc.defaults and mc.defaults.model else '')
except Exception:
    print('')
"
```

- If a default model is found, use it.
- If no default model, ask the user to specify one (e.g., `azure_ai/gpt-4o`, `azure_ai/claude-sonnet-4-6`).

## Phase 4: Generate Draft

Generate the `AGENTS.md` file content. Follow this structure exactly:

```markdown
---
name: <agent-name>
model: <model>
description: <one-line description>
permission:
  <category>: <action>
max_turns: <number>
model_params:
  temperature: <0.0-1.0>
  max_tokens: <number>
---

<system prompt body - detailed instructions for the agent>
```

**Naming convention:** Use lowercase kebab-case for the agent name (e.g., `code-reviewer`, `research-assistant`).

**System prompt guidelines:**
- Start with a clear role statement: "You are a ..."
- List specific responsibilities and boundaries
- Include output format expectations if relevant
- Add safety constraints if the agent has shell or edit permissions
- Keep it focused — avoid generic filler

**If subagents were accepted**, generate:
- Parent `AGENTS.md` with a `subagents:` list
- Separate `<subagent-name>.md` files for each subagent, or inline definitions

### Example single agent:

```yaml
---
name: code-reviewer
model: azure_ai/gpt-4o
description: Reviews code for quality, security, and correctness
permission:
  read: allow
  shell:
    "*": ask
    "git log*": allow
    "git diff*": allow
max_turns: 10
model_params:
  temperature: 0.0
  max_tokens: 4096
---

You are a senior code reviewer. Your job is to analyze code for:

1. **Correctness** — Does the logic match the intent? Check edge cases.
2. **Security** — Any injection risks, secrets in code, or unsafe input handling?
3. **Clarity** — Are names descriptive? Is the code self-documenting?
4. **Performance** — Any unnecessary allocations or O(n^2) loops?

You have read-only file access and can inspect git history. You cannot modify files.
For each issue found, state: the file and line, the problem, and a concrete fix.
```

### Example with subagents:

```yaml
---
name: dev-pipeline
model: azure_ai/gpt-4o
description: Coordinates code writing, testing, and review
permission:
  read: allow
  task: allow
max_turns: 15
subagents:
  - config: coder.md
  - config: tester.md
  - config: reviewer.md
---

You are a development coordinator. Break tasks into:
1. **coder** — writes the implementation
2. **tester** — writes and runs tests
3. **reviewer** — reviews the final result

Delegate each step to the appropriate subagent. Synthesize their outputs into a final summary.
```

## Phase 5: Present and Checkpoint

Show the generated draft to the user. Then confirm key decisions:

> Here's the generated agent configuration. Please review:
>
> **[show full AGENTS.md content]**
>
> Before I create this, let me confirm a few things:
>
> 1. **Model**: `<model>` — is this the right model?
> 2. **Permissions**: `<summary>` — does this match what the agent needs?
> 3. **Max turns**: `<N>` — is this enough for typical tasks?
>
> Would you like to change anything, or should I create it?

If the user wants changes, update the draft and re-present. Iterate until they approve.

## Phase 6: Create Files

Create the agent directory and write the files:

```bash
mkdir -p ./<agent-name>
```

Write `AGENTS.md` (and any subagent `.md` files) into `./<agent-name>/`.

## Phase 7: Validate

Run validation to confirm the generated config is correct:

```bash
evaluate validate ./<agent-name> --format json
```

- If validation **fails**, fix the issues automatically and re-validate.
- If validation **passes**, show the result to the user.

## Phase 8: Hand Off to Evaluation

Ask the user:

> Agent created successfully at `./<agent-name>/AGENTS.md`.
>
> Would you like to evaluate and optimize this agent? This will:
> - Analyze the config for improvement suggestions
> - Benchmark against your model
> - Apply optimizations and compare before/after
>
> (This uses the evaluate-sage-agent skill)

If yes, begin the evaluate-sage-agent workflow with the newly created agent path.
If no, summarize what was created and end.
