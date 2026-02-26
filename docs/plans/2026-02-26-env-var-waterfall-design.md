# Env Var Waterfall via config.toml `[env]`

## Problem

Required env vars (e.g., `AZURE_AI_API_KEY`, `AZURE_AI_API_BASE`) are currently sourced only from `.env` files and `os.environ`. There's no way to define or override them in `config.toml`.

## Design

### Config Format

```toml
[env]
AZURE_AI_API_KEY = "${AZURE_AI_API_KEY}"
AZURE_AI_API_BASE = "https://d-ue2-aicorepltfm-aisvcs.services.ai.azure.com"
MIXED = "prefix-${SOME_VAR}-suffix"
```

Values support three forms:
- **Literal**: `"https://example.com"` — used as-is
- **Reference**: `"${VAR_NAME}"` — resolved from `os.environ`
- **Mixed**: `"prefix-${VAR}-suffix"` — literal with embedded references

### Resolution Rules

1. Parse `[env]` values as strings.
2. Expand `${VAR_NAME}` references against `os.environ` (which already contains `.env` values from `load_dotenv()`).
3. If any referenced var is not found, raise `ConfigError` listing all unresolved vars.
4. Inject resolved values into `os.environ` — config.toml values **overwrite** existing env vars.

### Execution Order

```
load_dotenv()           # .env -> os.environ
load_main_config()      # parse config.toml
resolve_and_apply_env() # expand ${...}, fail on missing, set os.environ
```

### Changes

**`main_config.py`**:
- Add `env: dict[str, str] = {}` field to `MainConfig`.
- Add `resolve_and_apply_env(config: MainConfig)` that expands `${VAR}` patterns via `re.sub` + `os.environ.get`, collects unresolved vars, raises `ConfigError` if any, then sets resolved values into `os.environ`.

**`cli/main.py`**:
- Call `resolve_and_apply_env()` after `load_main_config()`.

### Approach Chosen

**Approach A: MainConfig.env dict with early os.environ injection** — matches the existing `load_dotenv()` pattern, minimal plumbing since `os.environ` is the implicit transport layer for API keys.

Rejected alternatives:
- **Pass-through dict (no os.environ mutation)**: Too much plumbing to thread env through every consumer.
- **Pydantic field validators for `${...}` anywhere**: Scope creep beyond `[env]` section.
