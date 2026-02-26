# CHANGELOG

<!-- version list -->

## v1.5.0 (2026-02-26)

### Features

- **tracing**: OpenTelemetry integration — `span()` async context manager in `sage/tracing.py`
  instruments agent runs, tool execution, LLM calls, and memory operations with parent-child spans;
  falls back to a zero-cost no-op when `opentelemetry-api` is not installed so no code changes are
  needed for untraced deployments

- **tracing**: `TracingConfig` model — configure via `tracing:` in agent frontmatter:
  `enabled`, `service_name`, `exporter` (`"none"` | `"console"` | `"otlp"`); enable with
  `pip install sage-agent[tracing]`; OTLP export requires the additional
  `opentelemetry-exporter-otlp-proto-grpc` package

- **tracing**: Span hierarchy — `agent.run` → `tool.execute` + `llm.complete` + `memory.recall` /
  `memory.store` form nested parent-child spans via OTel contextvars; exceptions are recorded on
  spans with `StatusCode.ERROR` before re-raising


## v1.4.0 (2026-02-26)

### Features

- **orchestrator**: Fix race cancellation — `run_race()` now awaits cancelled losing tasks with
  `asyncio.gather(*tasks, return_exceptions=True)` so their `finally` blocks and resource cleanup
  run before the winner's result is returned

- **orchestrator**: `Pipeline.stream()` — run all intermediate agents via `run()`, then stream the
  final agent; supports the `>>` operator and single/empty pipeline edge cases

- **memory**: Relevance filtering for memory storage — three modes: `"none"` (default, store
  everything), `"length"` (skip if exchange shorter than `min_exchange_length`, default 100 chars),
  `"llm"` (score with provider, skip below `relevance_threshold`, default 0.5); configure via
  `memory.relevance_filter` in agent frontmatter

- **agent**: Structured output via `response_model` — `await agent.run(input, response_model=MyModel)`
  injects the Pydantic JSON schema as a system message and parses the response with
  `model_validate_json()`; markdown code fences are stripped automatically; raises
  `pydantic.ValidationError` on invalid JSON


## v1.3.0 (2026-02-26)

### Features

- **config**: Configurable retry/backoff via `ModelParams` — `num_retries` and `retry_after`
  fields are forwarded to litellm, enabling automatic retry with exponential back-off on
  transient provider errors; set via `model_params:` in agent frontmatter

- **memory**: Optional sqlite-vec ANN search — `SQLiteMemory` now attempts to load the
  `sqlite-vec` extension at startup (`vector_search: auto` by default); falls back to
  O(n) numpy cosine similarity if unavailable; force numpy with `vector_search: numpy`
  or require sqlite-vec with `vector_search: sqlite_vec`; install optional dep with
  `pip install sage-agent[vec]`

- **memory**: Unified memory tools — when a `memory:` backend is configured, the semantic
  `memory_store`/`memory_recall` closures are registered in place of the JSON-file stubs;
  JSON stubs now emit `DeprecationWarning` when called without a configured backend


## v1.2.0 (2026-02-26)

### Features

- **agent**: Extract common agentic loop into `_pre_loop_setup`, `_execute_tool_calls`,
  `_post_loop_cleanup`, `_extract_final_output` — eliminates ~200 lines of duplication
  between `run()` and `stream()`

- **agent**: Parallel tool execution via `asyncio.gather(return_exceptions=True)` — independent
  tool calls in the same turn now run concurrently; order of results is preserved; opt out
  with `parallel_tool_execution: false` in agent frontmatter

- **tools**: Per-tool and registry-level timeouts — `@tool(timeout=30)` or `tool_timeout:`
  in agent frontmatter wraps execution with `asyncio.wait_for`; raises `ToolError` on
  expiry; per-tool override takes precedence over registry default


## v1.1.2 (2026-02-26)

### Features

- **security**: Prevent DNS rebinding (TOCTOU) in SSRF protection — hostname now
  resolved exactly once via `validate_and_resolve_url`; pinned IP used for actual
  connection with original hostname preserved for `Host` header and TLS SNI
  (`sage.tools._security.ResolvedURL`)

- **security**: Add optional shell sandbox (`sandbox:` frontmatter field) with
  `NativeSandbox` (environment stripping) and `BubblewrapSandbox` (Linux
  namespace isolation via `bwrap`); per-agent closure pattern prevents
  concurrency issues between agents with different sandbox configs
  (`sage.tools._sandbox`)

- **security**: Replace blocking `urllib.request.urlopen` with async
  `httpx.AsyncClient` in `http_request` built-in tool; connections use pinned IP
  with IP-pinning transport for SSRF consistency


## v1.1.1 (2026-02-26)

### Bug Fixes

- **docs**: Update prerequisites for Azure AI API key and base in run.py
  ([`6a61b81`](https://github.com/sagebynature/sage-agent/commit/6a61b81705cecf9cbf8e1aa1d8b2f0be3cfba41e))


## v1.1.0 (2026-02-26)

### Bug Fixes

- **config**: Revert unplanned max_turns and comment formatting changes
  ([`e1987d4`](https://github.com/sagebynature/sage-agent/commit/e1987d427bcc8e123ba0b30a695609467037bde4))

- **config**: Update AZURE_AI_API_KEY and AZURE_AI_API_BASE for correct environment variable
  references
  ([`7678699`](https://github.com/sagebynature/sage-agent/commit/7678699c452efc2e1f12d6f72a8c454ca607905f))

### Chores

- **uv.lock**: Bump sage-agent version to 1.0.2
  ([`7678699`](https://github.com/sagebynature/sage-agent/commit/7678699c452efc2e1f12d6f72a8c454ca607905f))

### Documentation

- Add env var waterfall design
  ([`29ad5bf`](https://github.com/sagebynature/sage-agent/commit/29ad5bf07e52705c5a9adc754c09378aca0d3a25))

- Add env var waterfall implementation plan
  ([`4ed928a`](https://github.com/sagebynature/sage-agent/commit/4ed928ab082fe2fd2b1c1abb6660ba401b8250d0))

### Features

- **cli**: Wire resolve_and_apply_env into startup
  ([`fb90f49`](https://github.com/sagebynature/sage-agent/commit/fb90f49778ea8e2a4626a2f0db640c6f6feab50b))

- **config**: Add [env] section to config.toml and update docstring
  ([`5122f85`](https://github.com/sagebynature/sage-agent/commit/5122f85a57f7e29ee5025c0587294cfa4dd90b52))

- **config**: Add env field to MainConfig
  ([`9fd0cfe`](https://github.com/sagebynature/sage-agent/commit/9fd0cfe1f8708575b5dfc3d732c39c875534ff8a))

- **config**: Add resolve_and_apply_env for env var waterfall
  ([`ef360a3`](https://github.com/sagebynature/sage-agent/commit/ef360a3d82745a0131b158b9ad2bc6c84e52ce30))


## v1.0.2 (2026-02-26)

### Bug Fixes

- **tests**: Remove obsolete version test
  ([`d3930ea`](https://github.com/sagebynature/sage-agent/commit/d3930ea57f28a7ed18f8f867dfb122586523dde6))


## v1.0.1 (2026-02-26)

### Bug Fixes

- **mcp**: Handle CancelledError during agent cleanup
  ([`7f72368`](https://github.com/sagebynature/sage-agent/commit/7f72368d9c2b180273a85a7e2a52436bfeb5e181))

### Chores

- Stick to main version
  ([`0b3d783`](https://github.com/sagebynature/sage-agent/commit/0b3d7835cdc07a87e27ff8f70be8081cb0198a30))

- **examples**: Migrate all AGENTS.md to new permission format
  ([`8909eb0`](https://github.com/sagebynature/sage-agent/commit/8909eb07c87babc57ba7ac21d854c741e1913d0d))

### Documentation

- Update all docs to reflect permission + extensions config model
  ([`57e0d66`](https://github.com/sagebynature/sage-agent/commit/57e0d66101659d3cf5090cbd9cca3d25e60268b9))

- **readme**: Update config reference and add 41 integration tests
  ([`3cbe3c0`](https://github.com/sagebynature/sage-agent/commit/3cbe3c086f838695dd2584cc3fd9e6bda316d248))

### Refactoring

- **config**: Add Permission schema, CATEGORY_TOOLS, remove destructive flag, add bool coercion
  ([`3f9c592`](https://github.com/sagebynature/sage-agent/commit/3f9c592fe75b3086779cd7df0ea1fdd88ca47ddd))

- **config**: AgentConfig with permission + extensions fields, remove tools/permissions
  ([`53b1234`](https://github.com/sagebynature/sage-agent/commit/53b12347edca7f9c5e26c431fbe823b106296807))

- **config**: Use named dict for mcp_servers instead of list
  ([`8ea9cd7`](https://github.com/sagebynature/sage-agent/commit/8ea9cd76c03d1463eb4b58c699f491fe7ac99079))

- **permissions**: Category-aware PolicyPermissionHandler + ToolRegistry.register_from_permissions
  ([`7a8855a`](https://github.com/sagebynature/sage-agent/commit/7a8855a580265141c6e7b2356f3ff39c1b070eb6))

- **tools**: Remove git_tools, glob_find, grep_search
  ([`53c3618`](https://github.com/sagebynature/sage-agent/commit/53c36184e9a56f4acd3ef0650f5f543ec9b56fb9))


## v1.0.0 (2026-02-25)

### Documentation

- Add Sage Evaluator companion app reference to README
  ([`47b241b`](https://github.com/sagebynature/sage-agent/commit/47b241be635ac6c538c7ced5b1681ae86e96302a))


## v1.0.0-rc.7 (2026-02-25)

### Bug Fixes

- Update README formatting and enhance feature descriptions
  ([`09966d0`](https://github.com/sagebynature/sage-agent/commit/09966d0c2c78d25f6dcd3f3f163d168668697281))


## v1.0.0-rc.6 (2026-02-25)

### Bug Fixes

- Update project name from 'Apollo Agent' to 'Sage Agent' in scripts
  ([`e9ee1d3`](https://github.com/sagebynature/sage-agent/commit/e9ee1d300798588308feab6efbb7c9b6006657f2))


## v1.0.0-rc.5 (2026-02-25)

### Bug Fixes

- Separate sync from install so CI skips pre-commit hooks
  ([`2c25be3`](https://github.com/sagebynature/sage-agent/commit/2c25be3d3748da7436567bff33a98ff6eb27a470))

- Update project name from 'Sage' to 'Sage Agent' in README
  ([`ff3969c`](https://github.com/sagebynature/sage-agent/commit/ff3969c0074db2d0943e47da50c8dfcedf138c5c))

### Chores

- Remove CHANGELOG.md as it is no longer needed
  ([`42fa427`](https://github.com/sagebynature/sage-agent/commit/42fa427bb18d2ef6ca7afcabce87ccb4cc003b70))


## v1.0.0-rc.4 (2026-02-25)

### Bug Fixes

- Update CI workflow to simplify testing and bump version to 1.0.0rc3
  ([`b58bfa3`](https://github.com/sagebynature/sage-agent/commit/b58bfa3f6a60add6c8ba420a837d357c5bf461c4))

### Chores

- Fixed uv.lock
  ([`dc89dc8`](https://github.com/sagebynature/sage-agent/commit/dc89dc84bbdcc303d4245e99251aa42edd2b25e1))


## v1.0.0-rc.3 (2026-02-25)

### Bug Fixes

- Isolate HOME in config path tests to prevent host leakage
  ([`7bbe3ba`](https://github.com/sagebynature/sage-agent/commit/7bbe3ba278e0745aac1d0710cd8cfb2d735de021))

- Update package name to sage-agent and version to 1.0.0rc2
  ([`91d9484`](https://github.com/sagebynature/sage-agent/commit/91d9484024b73bdac93f6a06df074e35d3a05959))

### Documentation

- Add comprehensive agent authoring guide
  ([`fcd3aa2`](https://github.com/sagebynature/sage-agent/commit/fcd3aa2b1c20edef837af8d5f8098ef73757912c))

- Moved to .docs
  ([`ea2226d`](https://github.com/sagebynature/sage-agent/commit/ea2226dbd4dfaec4cb717f8836c56bcd6dc24be8))


## v1.0.0-rc.2 (2026-02-25)

### Bug Fixes

- Add module-name to uv build backend config
  ([`d089530`](https://github.com/sagebynature/sage-agent/commit/d0895306417ff017502ba35988413e05da99b0e2))


## v1.0.0-rc.1 (2026-02-25)

- Initial Release
