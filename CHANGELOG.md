# CHANGELOG

<!-- version list -->

## v1.2.0-rc.1 (2026-03-01)

### Bug Fixes

- Address code review issues in lazy skill loading
  ([`05f3ba4`](https://github.com/sagebynature/sage-agent/commit/05f3ba425760ce0bbe153e38e99f73740068ef27))

- Resolve 15 mypy strict-mode errors across 6 files
  ([`e494593`](https://github.com/sagebynature/sage-agent/commit/e494593593a0d6346338bf2263c8a74e7fddf264))

- Typo
  ([`55a15b5`](https://github.com/sagebynature/sage-agent/commit/55a15b5d8e7117e75eaa9c3fcd4ce36440db8ea7))

- **agent**: Address Phase 2 final review findings
  ([`70c8c06`](https://github.com/sagebynature/sage-agent/commit/70c8c06e2977febc3e80ca417aad90a195572074))

- **agent**: Call resolve_and_apply_env in from_config so [env] section is applied outside CLI
  ([`b1c48e9`](https://github.com/sagebynature/sage-agent/commit/b1c48e982e3fcbda0231032353b63dedf7695b87))

- **agent**: Fail closed on ask permissions and max-turn loops
  ([`8271f52`](https://github.com/sagebynature/sage-agent/commit/8271f52c2a651c342f98031f09eccfe6e5f60dc6))

- **agent**: Use return_exceptions=True in asyncio.gather to prevent task cancellation on
  SagePermissionError
  ([`9990192`](https://github.com/sagebynature/sage-agent/commit/999019293559cd34516c8b1c7b8c0e4c40e23933))

- **eval**: Multi-model support, tool tracking, and cancel-scope isolation
  ([`c053c2f`](https://github.com/sagebynature/sage-agent/commit/c053c2fce000218e99689529994ed7091a48e3db))

- **eval**: Resolve agent and context_files paths relative to suite YAML directory
  ([`cb06b18`](https://github.com/sagebynature/sage-agent/commit/cb06b185d231f6fa085f35d4b69fae7f0fa05e66))

- **examples/skills_demo**: Chdir to demo_dir so skill script relative paths resolve correctly
  ([`37ecd86`](https://github.com/sagebynature/sage-agent/commit/37ecd86c1eb20f61cfcb2f714286d32f85554100))

- **git**: Address code review — path traversal, snapshot refactor, case-insensitive patterns,
  shared fixtures
  ([`29c0fc5`](https://github.com/sagebynature/sage-agent/commit/29c0fc585a69fedb3d579d774238c40afd71fc54))

- **makefile**: Correct parallel_agents subagent paths in validate-examples
  ([`f27d8d1`](https://github.com/sagebynature/sage-agent/commit/f27d8d13e1e2560a780156baa05f421a26abd2e3))

- **memory**: Address Phase 3 final review — OperationalError fallback, config passthrough, rowid
  join, log improvements
  ([`3a53648`](https://github.com/sagebynature/sage-agent/commit/3a536482dfc0a1cd5422c2c45f73319734addb45))

- **orchestrator**: Await cancelled race tasks for proper resource cleanup
  ([`0e1a078`](https://github.com/sagebynature/sage-agent/commit/0e1a0784d6b155b62208875677320708889ec2e5))

- **permissions**: Allow unknown-category tools (MCP) through policy handler
  ([`ece8d15`](https://github.com/sagebynature/sage-agent/commit/ece8d15e0af3b9cd7bb1c64eb4ef21093f761db2))

- **phase4**: Address final review findings
  ([`b9a2ab5`](https://github.com/sagebynature/sage-agent/commit/b9a2ab55ea274a5a9a6a986ce16a51cd35ca1cf2))

- **skills**: Auto-load config.toml in from_config and expand env vars in resolve_skills_dir
  ([`a8d14a3`](https://github.com/sagebynature/sage-agent/commit/a8d14a30aa82587635248be1a4860082483f26e5))

- **tests**: Update stale test to reflect intentional MCP tool pass-through behaviour
  ([`cc1f06f`](https://github.com/sagebynature/sage-agent/commit/cc1f06f100acbe7decdbe933222ebaa404f0a14a))

- **tracing**: Address Phase 5 review suggestions
  ([`6c49a83`](https://github.com/sagebynature/sage-agent/commit/6c49a83595f557a171e3189fdf26881f44c8a3dc))

- **types**: Resolve mypy errors from Phase 3/4 — sqlite_vec import-not-found, no-any-return
  ([`a1e29a3`](https://github.com/sagebynature/sage-agent/commit/a1e29a3795ae452985b7ccb1fc8672636fd3a299))

- **types**: Resolve mypy errors in bus, follow_through, query_classifier, tool_calls
  ([`399616a`](https://github.com/sagebynature/sage-agent/commit/399616a0856bd76e09fa915ef0cdf11e2bea09e9))

### Chores

- Downgrade version to 1.1.1 and update dependencies for OpenTelemetry integration
  ([`db0c744`](https://github.com/sagebynature/sage-agent/commit/db0c744cb01602fcf19eecff43676448f11c2d28))

- Remove outdated agent configuration redesign document
  ([`d489579`](https://github.com/sagebynature/sage-agent/commit/d489579e935ec3348bf2633682fb55363bc04a62))

- **config**: Uncomment skills_dir in config.toml for clarity on global skills directory
  ([`bd33be7`](https://github.com/sagebynature/sage-agent/commit/bd33be7fb10dff68a4eaa4f6c627d889e74f5b43))

- **config**: Update config.toml with skills_dir documentation
  ([`04bba55`](https://github.com/sagebynature/sage-agent/commit/04bba55ffd886da6cd31bf6f1c29b2ffa640f15a))

- **config**: Update model parameters and permissions in config.toml; bump sage-agent version to
  1.2.0
  ([`4453f83`](https://github.com/sagebynature/sage-agent/commit/4453f83fa96bfbe57c0a60624e952b3f41150f10))

- **eval**: Update model settings in full.eval.yaml
  ([`0b2ee66`](https://github.com/sagebynature/sage-agent/commit/0b2ee664397731838cfed2ae37323de79a2f5d3c))

### Code Style

- Remove unused type-ignore comment
  ([`d1ec450`](https://github.com/sagebynature/sage-agent/commit/d1ec4506b7f7a06418049262b5e0af223bf537ae))

- **agent**: Remove unused compacted assignment in _post_loop_cleanup
  ([`71b3664`](https://github.com/sagebynature/sage-agent/commit/71b3664f4013bfc7f2aa3576bde9f056560d8e4b))

### Documentation

- Add ci-headless and eval references, update README and architecture docs
  ([`9e9b4fc`](https://github.com/sagebynature/sage-agent/commit/9e9b4fc77c1d489b1133109feddbafb8587a6e18))

- Add Claude Code skills section for agent creation and evaluation
  ([`7b09331`](https://github.com/sagebynature/sage-agent/commit/7b09331a6d6667538b6b4e0ea4327420a2952aad))

- Add gap remediation plans from competitive analysis
  ([`77b46df`](https://github.com/sagebynature/sage-agent/commit/77b46dfcb17d73bb72fd35591dfad17c8b7014f0))

- Add git integration design document
  ([`7030be6`](https://github.com/sagebynature/sage-agent/commit/7030be6bfbb293670b1fb38b5c863abe4f09b173))

- Add git integration implementation plan
  ([`7168a93`](https://github.com/sagebynature/sage-agent/commit/7168a93324f3440ad8b2e6802dbb98394a0d4550))

- Add lazy skill loading design document
  ([`4b60e2a`](https://github.com/sagebynature/sage-agent/commit/4b60e2a904f1925b0f1578f8b9516b1f2c907955))

- Add lazy skill loading implementation plan
  ([`1587e63`](https://github.com/sagebynature/sage-agent/commit/1587e634dd1ea382ba0c242d2ad7adcae83e7d33))

- Add thorough sandboxing documentation
  ([`ed3216b`](https://github.com/sagebynature/sage-agent/commit/ed3216bddc398fe3d55864045ad1a72fedbe9e8c))

- Remove completed Plan 1 (Git Integration) and update design doc
  ([`bed5f21`](https://github.com/sagebynature/sage-agent/commit/bed5f21ad756d0eb3df5a56be6875cbe3a1c6fe0))

- Update all docs for v1.7.0 hook system and architecture additions
  ([`b36eb4b`](https://github.com/sagebynature/sage-agent/commit/b36eb4b8e7fa583bd208e9d5e884d30ef736b4f8))

- Update documentation for global skill management system
  ([`9831204`](https://github.com/sagebynature/sage-agent/commit/9831204edc2969104f78e4a8e8b93a5889a33d65))

- Update git integration plans and remove obsolete documents
  ([`293b0a7`](https://github.com/sagebynature/sage-agent/commit/293b0a72e525f0680d7d95b713ebff07dd8bfbdf))

- **config**: Update agent-only fields comment to reflect skills allowlist (remove stale skills_dir)
  ([`9c33d18`](https://github.com/sagebynature/sage-agent/commit/9c33d18540c4df4ccea1ca6b31db80acc507a5ed))

- **phase2**: Bump to v1.2.0, update CHANGELOG and agent-authoring frontmatter reference
  ([`8f9fcf9`](https://github.com/sagebynature/sage-agent/commit/8f9fcf9289fd452b1d17f2540aece3beddc1fcd4))

- **phase3**: Add v1.3.0 CHANGELOG, bump to 1.3.0, document new memory and retry fields
  ([`80adb3d`](https://github.com/sagebynature/sage-agent/commit/80adb3d66a26301e4bee0c1d2bcc5d1fa6f0102c))

- **phase3**: Update memory.md and tools.md for Phase 3 features
  ([`55360ac`](https://github.com/sagebynature/sage-agent/commit/55360acf09c02fc62431834f98d1ee97e722971a))

- **phase4**: Document response_model, Pipeline.stream(), and race cleanup
  ([`68f93ae`](https://github.com/sagebynature/sage-agent/commit/68f93ae7f3c047b5abb6acd82c080ad4353224ef))

- **phase4**: V1.4.0 CHANGELOG, bump to 1.4.0, document new features
  ([`30786e1`](https://github.com/sagebynature/sage-agent/commit/30786e141ad65fb59708e43c5e5461eccaebca35))

- **phase5**: V1.5.0 CHANGELOG, bump to 1.5.0, document tracing configuration
  ([`fea270f`](https://github.com/sagebynature/sage-agent/commit/fea270fa20e2791d2c9806f33cf1782835fe5d57))

- **security**: Update tools.md, agent-authoring.md, CHANGELOG for Phase 1
  ([`c64a23e`](https://github.com/sagebynature/sage-agent/commit/c64a23e876e62160bf738b25d366d64d64222e8d))

- **tools**: Document shell blocklist bypass via fnmatch permission patterns
  ([`b1537e2`](https://github.com/sagebynature/sage-agent/commit/b1537e261a99e5b379e4a54bf164c28032547bd6))

### Features

- Implement lazy skill loading with use_skill tool
  ([`0b7523a`](https://github.com/sagebynature/sage-agent/commit/0b7523ad7141225e022256ff5253d33b991c92b4))

- **agent**: Add approval-aware sequential execution with cancellation token (Task 20)
  ([`209b476`](https://github.com/sagebynature/sage-agent/commit/209b476dfb52eabe49261ed56aba55a6abddb193))

- **agent**: Add response_model parameter to run() for structured Pydantic output
  ([`55cee4d`](https://github.com/sagebynature/sage-agent/commit/55cee4d95fc73a9b8e07341425e256ca3e6bd40d))

- **agent**: Add subagent crash isolation with error message fallback
  ([`18feb24`](https://github.com/sagebynature/sage-agent/commit/18feb24d0911fecf294460465ab4fb9ec8c92fae))

- **agent**: Grant git permission for devtools agent
  ([`665fb38`](https://github.com/sagebynature/sage-agent/commit/665fb38e9bfb548572478738f2b7fd3eab4068aa))

- **agent**: Parallel tool execution via asyncio.gather (parallel_tool_execution config flag)
  ([`9c61351`](https://github.com/sagebynature/sage-agent/commit/9c61351e8e894fa500b28fb9de72de6e129c7a6e))

- **agent**: Wire global skill pool with per-agent allowlist filtering
  ([`ecfa8d1`](https://github.com/sagebynature/sage-agent/commit/ecfa8d1f33c41852163533c4b7f8f77a3a31cbc9))

- **agent**: Wire hook emission points into Agent run/stream/delegate/compact loops (Task 25)
  ([`95850ff`](https://github.com/sagebynature/sage-agent/commit/95850ff61a2a6a7832831fe8e6e55d6a2087ec3f))

- **agent**: Wire multi-part → emergency → deterministic compaction strategy chain (Task 26)
  ([`26ef05a`](https://github.com/sagebynature/sage-agent/commit/26ef05a6efd7a0d25f03b9f540d709b7f13d14a5))

- **agents**: Add permission fields for orchestrator agent
  ([`cfe3c0d`](https://github.com/sagebynature/sage-agent/commit/cfe3c0dc7e9382cff2aa7a41a6e09cb021ba0258))

- **cli**: Add headless/CI exec command with structured exit codes and JSONL output
  ([`b682927`](https://github.com/sagebynature/sage-agent/commit/b6829274cf203e224661ec741253fb0f47105f8b))

- **compaction**: Add character caps, bullet-point format, and source truncation
  ([`fe575e4`](https://github.com/sagebynature/sage-agent/commit/fe575e44896875b7013fa8ce487890e551d114bc))

- **config**: Add frontmatter fields for hooks, credential scrubbing, research, sessions (Task 27)
  ([`09b4cac`](https://github.com/sagebynature/sage-agent/commit/09b4caca5eedfcbc6ea532503a5d8083e59c05e0))

- **config**: Add max_depth, agent_path, primary/secondary, and AIEOS identity support
  ([`85534fa`](https://github.com/sagebynature/sage-agent/commit/85534fa0248b77e28b8a6f951a21469956a41ec3))

- **config**: Add num_retries and retry_after to ModelParams for litellm retry support
  ([`04232ea`](https://github.com/sagebynature/sage-agent/commit/04232ea6e293d452057ed0290d6c2ead4d378b40))

- **config**: Implement environment variable resolution and update config.toml
  ([`af8a14c`](https://github.com/sagebynature/sage-agent/commit/af8a14c7974616b9b1760153d10880015b7df226))

- **context**: Add static context window fallback table with pattern matching
  ([`0701fbc`](https://github.com/sagebynature/sage-agent/commit/0701fbc78dea47de326f5ce30ffc118e6578c38b))

- **coordination**: Add CancellationToken with asyncio.Event and wrap() race
  ([`c7ce29a`](https://github.com/sagebynature/sage-agent/commit/c7ce29a064f50ac4441fc205d103ea03a7cd6ca6))

- **coordination**: Add in-memory message bus with TTL, idempotency, and dead letters
  ([`44b0abc`](https://github.com/sagebynature/sage-agent/commit/44b0abc2b19b6f5785a3343139bab05506e14e85))

- **coordination**: Add SessionManager for concurrent session lifecycle management
  ([`0c00363`](https://github.com/sagebynature/sage-agent/commit/0c003636717f1b7ee0c925f4a6b3ec5c3a23b614))

- **coordination**: Add SessionState container for per-session isolated state
  ([`0ce89b8`](https://github.com/sagebynature/sage-agent/commit/0ce89b893c0b9304c67ca0f34e2c4500b4560085))

- **coordination**: Add typed message envelope models with discriminated union parsing
  ([`2139a73`](https://github.com/sagebynature/sage-agent/commit/2139a7390d3006ae04830d0ba61b1716e358b24d))

- **eval**: Add built-in evaluation CLI with 11 assertion types and SQLite history
  ([`71b02aa`](https://github.com/sagebynature/sage-agent/commit/71b02aafc12ffe0b9fbd734127923b4d162954f1))

- **eval**: Add configurable judge_model and per-token-type usage tracking
  ([`a60dcaf`](https://github.com/sagebynature/sage-agent/commit/a60dcaf44a23029ea8a80ed2e004ced7330ab152))

- **eval**: Add fixture files for devtools eval tests
  ([`1ecc4bd`](https://github.com/sagebynature/sage-agent/commit/1ecc4bdff783687db3ea78b68c571d06ecb7e311))

- **eval**: Add full regression eval suite for devtools agent
  ([`97ae702`](https://github.com/sagebynature/sage-agent/commit/97ae70238e652b72fc29b0913e7cde02bf7f9fef))

- **eval**: Add security eval suite for devtools agent
  ([`f2fde05`](https://github.com/sagebynature/sage-agent/commit/f2fde05c7e99f8b77ea0b5ca463ceb66296acce3))

- **eval**: Add smoke eval suite for devtools agent
  ([`115f692`](https://github.com/sagebynature/sage-agent/commit/115f6926d66d14f0e225cf6fd7f55707180312b9))

- **examples/skills_demo**: Create skill files and fix run_demo.py API usage
  ([`14b5d57`](https://github.com/sagebynature/sage-agent/commit/14b5d57d6127e4b96fccedcc2f6c0b5a4b26a65a))

- **git**: Add git permission category, GitConfig, and registry wiring
  ([`ee38ab5`](https://github.com/sagebynature/sage-agent/commit/ee38ab51ea956b5e59e2b15768e78061cc10c232))

- **git**: Add git-specific dangerous command patterns
  ([`3d0245a`](https://github.com/sagebynature/sage-agent/commit/3d0245ad86f00910c2f2dac4cd303f0ae170798d))

- **git**: Implement git_branch, git_worktree_create, git_worktree_remove
  ([`1cf8913`](https://github.com/sagebynature/sage-agent/commit/1cf89130650b29cea7bea5f9ae3e1b901220085e))

- **git**: Implement git_commit and git_undo with safety checks
  ([`e32fd80`](https://github.com/sagebynature/sage-agent/commit/e32fd80dbb28b91431cc41196d44c62b58005e46))

- **git**: Implement GitTools with status, diff, log tools
  ([`9a1ee4a`](https://github.com/sagebynature/sage-agent/commit/9a1ee4a4bf078d1d60d18918e80ef7e2eb416f54))

- **git**: Wire git tools into registry, add auto-snapshot to agent
  ([`ef44316`](https://github.com/sagebynature/sage-agent/commit/ef44316c15d9e1962b914259e945a1118467e6b8))

- **hooks**: Add action follow-through guardrail (Task 16)
  ([`b54916e`](https://github.com/sagebynature/sage-agent/commit/b54916e02e84d85a9371309113d110d9e5274df9))

- **hooks**: Add automatic memory loading hook for pre-LLM context enrichment
  ([`d7fae96`](https://github.com/sagebynature/sage-agent/commit/d7fae96d115c8a5ad411bf42e0aa4ba40c8b75d6))

- **hooks**: Add credential scrubbing hook with regex patterns and allowlist
  ([`fed3cf0`](https://github.com/sagebynature/sage-agent/commit/fed3cf03ffe629d1355f5a798c1857be0cda2be0))

- **hooks**: Add hook system with void/modifying dispatch, priority, and safety guardrails
  ([`9128ed2`](https://github.com/sagebynature/sage-agent/commit/9128ed2d6099a02d54f69721bddcb2d0d2a388ce))

- **hooks**: Add rule-based query classifier for model routing
  ([`d675390`](https://github.com/sagebynature/sage-agent/commit/d675390f21304fc073b49787c0d380df34a4118e))

- **memory**: Add file-based memory backend with JSON and Markdown storage modes
  ([`5274d54`](https://github.com/sagebynature/sage-agent/commit/5274d54dd4bd4b821648ffb1f911b52d6d1d1981))

- **memory**: Add memory_forget tool following existing closure pattern
  ([`aad1822`](https://github.com/sagebynature/sage-agent/commit/aad18229dfa84d152f4c793863fcb1e4d3e9676e))

- **memory**: Add multi-part compaction, emergency_drop, deterministic_trim (Tasks 17-19)
  ([`263050a`](https://github.com/sagebynature/sage-agent/commit/263050acb6cfd3c416e400d05b48bd6200ed7a94))

- **memory**: Add relevance filtering for memory storage — length, llm, and none modes
  ([`7697952`](https://github.com/sagebynature/sage-agent/commit/7697952a558871c395f9ebac621155a2b34fae64))

- **memory**: Add sqlite-vec ANN search with numpy fallback (vector_search config)
  ([`6477bc1`](https://github.com/sagebynature/sage-agent/commit/6477bc1c9434fe3837e9f901c47948e8c74f8327))

- **memory**: Enrich MemoryProtocol with get/list/forget/count/health_check
  ([`e49001b`](https://github.com/sagebynature/sage-agent/commit/e49001bc0ffd9b15b2be86b5114df7c8fa799688))

- **memory**: Unify memory tools — semantic backend overrides JSON tools when memory: configured
  ([`54751bd`](https://github.com/sagebynature/sage-agent/commit/54751bda0905971b1145e5d4655be0b680a3e995))

- **orchestrator**: Add Pipeline.stream() — intermediate agents run(), final agent streams
  ([`f8430a5`](https://github.com/sagebynature/sage-agent/commit/f8430a59459c786c12e084f4e73c76309d488abd))

- **parsing**: Add JSON repair utility for trailing commas, missing braces, code fences
  ([`fba8195`](https://github.com/sagebynature/sage-agent/commit/fba81950a917eb8bbadecf104ccfb52ab067dcdc))

- **parsing**: Add multi-format tool call parser chain (native/XML/markdown/repair)
  ([`39e1df8`](https://github.com/sagebynature/sage-agent/commit/39e1df89c6fc2f3ebb1f1efa9141aafeac767953))

- **phase5**: Merge Phase 5 — OpenTelemetry Integration (v1.5.0)
  ([`85988cf`](https://github.com/sagebynature/sage-agent/commit/85988cf4e0c00687ac2b06bc3af32ff16cb3885b))

- **research**: Add configurable pre-response research phase with trigger modes
  ([`7d9db07`](https://github.com/sagebynature/sage-agent/commit/7d9db070dbd3e26d690fda68d57cb43155458fdb))

- **sandbox**: Add multi-backend execution sandboxing with hardened command validation
  ([`819ef4d`](https://github.com/sagebynature/sage-agent/commit/819ef4d66587de9f2fbeb576bbf7816fee9eb9f0))

- **security**: Add per-agent shell_allow_patterns to bypass specific dangerous patterns
  ([`1671bdc`](https://github.com/sagebynature/sage-agent/commit/1671bdc68f90b3b7d62456c763d6ee8edaa9cfc3))

- **security**: Phase 1 — SSRF TOCTOU fix, shell sandbox, async HTTP (urllib → httpx)
  ([`9bd86d5`](https://github.com/sagebynature/sage-agent/commit/9bd86d572fc95f37797582031a3494d6d8993fee))

- **skills**: Add filter_skills_by_names helper
  ([`31a78f3`](https://github.com/sagebynature/sage-agent/commit/31a78f304a6da03a06ad173b7bc99e5ee28eb8f1))

- **skills**: Add waterfall resolver for global skills directory
  ([`3409c5b`](https://github.com/sagebynature/sage-agent/commit/3409c5ba9c6cf6fb26bd45d6cf92526d0a8aff4e))

- **tools**: Add tool timeouts via asyncio.wait_for — per-tool @tool(timeout=N) and registry
  default_timeout
  ([`8900215`](https://github.com/sagebynature/sage-agent/commit/8900215e67db62f3e308d6979b01d9bd4963df3f))

- **tools**: Add ToolDispatcher strategy pattern with native/XML/auto selection
  ([`cea791e`](https://github.com/sagebynature/sage-agent/commit/cea791e501426d5c6e9cf19dd091730d4a5f1f9d))

- **tracing**: Add OpenTelemetry integration with no-op fallback (Phase 5)
  ([`2830c48`](https://github.com/sagebynature/sage-agent/commit/2830c486870a75eeb55e983d346cb044a75201c7))

- **usage**: Track cache tokens, reasoning tokens, and cost per turn
  ([`0f63302`](https://github.com/sagebynature/sage-agent/commit/0f63302a00d7debb09a9b2de127dd93d94fb1d3f))

### Refactoring

- Remove skill-name matching heuristic from tool dispatch
  ([`6f84462`](https://github.com/sagebynature/sage-agent/commit/6f8446277b3098be604da53d1623ebd1eb5b0a86))

- **agent**: Extract _pre_loop_setup, _execute_tool_calls, _post_loop_cleanup, _extract_final_output
  ([`19c5dc5`](https://github.com/sagebynature/sage-agent/commit/19c5dc5d4a56b6299a917eb348a943c0f6e26960))

- **agent**: Extract memory tool closures into _register_memory_tools() method
  ([`5553437`](https://github.com/sagebynature/sage-agent/commit/55534375957ff13d9e95d82a42378965eb9f575e))

- **config**: Add top-level skills_dir and per-agent skills allowlist to models
  ([`9e5e7ca`](https://github.com/sagebynature/sage-agent/commit/9e5e7cab30f5f3afe3227bf040db627a8af716d6))

- **config**: Remove legacy skills_dir from AgentOverrides and AgentConfig
  ([`81eb9b3`](https://github.com/sagebynature/sage-agent/commit/81eb9b35791250bc96f5176f661fcaf717524b66))

- **config**: Rename agent_path to agents_dir for clarity
  ([`7158d47`](https://github.com/sagebynature/sage-agent/commit/7158d47c2eec6a2a82e2c948a695d74d969e7b26))

- **config**: Update merge_agent_config for skills allowlist
  ([`644c171`](https://github.com/sagebynature/sage-agent/commit/644c1714b897e86c74cc62dfbe118fbb3ff3ddd7))

- **config**: Update model references and environment variables
  ([`8a4cb27`](https://github.com/sagebynature/sage-agent/commit/8a4cb2799f11b44a9d1f5899f5dfaa904b070948))

- **security**: Use dict-form shell permission for dangerous pattern groups
  ([`299ad13`](https://github.com/sagebynature/sage-agent/commit/299ad1330ff3e863d9f904d7598ff0dd0d98cd6c))

- **security**: Use fnmatch permission patterns to bypass shell blocklist
  ([`f0afa65`](https://github.com/sagebynature/sage-agent/commit/f0afa65f22e6bc056304b8dda61e0986e2fc9f85))

### Testing

- Add assertion for catalog preamble line
  ([`d323a85`](https://github.com/sagebynature/sage-agent/commit/d323a85f3f00e8cc47a21198c6b0642d372782df))

- Add failing tests for lazy skill loading
  ([`f97ac7b`](https://github.com/sagebynature/sage-agent/commit/f97ac7bad940b619f50c76b4b73afeee1520c631))

- **git**: Add end-to-end integration tests for git tools
  ([`50f3868`](https://github.com/sagebynature/sage-agent/commit/50f38686bde2f18c52f58b5a09e4264f1d38176b))


## v1.7.0 (2026-02-27)

### Features

- **hooks**: Hook/event system — `HookRegistry` in `sage/hooks/registry.py` with two emission modes:
  `emit_void()` for parallel side-effect handlers, `emit_modifying()` for sequential chained
  transformers; `HookEvent` enum covers `PRE_LLM_CALL`, `POST_LLM_CALL`, `PRE_TOOL_EXECUTE`,
  `POST_TOOL_EXECUTE`, `ON_DELEGATION`, `ON_COMPACTION`, `PRE_MEMORY_RECALL`, `POST_MEMORY_STORE`,
  `PRE_COMPACTION`, `POST_COMPACTION`; hooks that raise are logged and swallowed so agent runs
  are never aborted by a hook failure

- **hooks/builtin**: `credential_scrubber` — `POST_TOOL_EXECUTE` void hook that redacts secrets
  from tool outputs using configurable regex patterns and an allowlist; enabled via
  `credential_scrubbing:` in agent frontmatter

- **hooks/builtin**: `query_classifier` — `PRE_LLM_CALL` modifying hook that routes queries to
  different models based on keyword/regex rules; enabled via `query_classification:` in frontmatter;
  rules specify `keywords`, `patterns`, `priority`, and `target_model`

- **hooks/builtin**: `follow_through` — `POST_LLM_CALL` modifying hook that detects LLM bail-out
  phrases (e.g. "I cannot", "I'm unable to") and sets `retry_needed: True` in hook data to trigger
  a retry; configurable `max_retries` and `retry_prompt`; enabled via `follow_through:` in frontmatter

- **hooks/builtin**: `auto_memory` — `PRE_LLM_CALL` hook that automatically injects recalled
  memories into the message list before each LLM call; enabled automatically when a memory backend
  is configured with `auto_load: true`

- **agent**: Hook emission points wired throughout the agentic loop — `PRE_LLM_CALL`/
  `POST_LLM_CALL` around each provider call, `POST_TOOL_EXECUTE` after each tool dispatch,
  `ON_DELEGATION` before each subagent handoff, `ON_COMPACTION` after history compaction;
  `hook_registry` constructor parameter; `_last_compaction_strategy` attribute tracking which
  strategy was used most recently

- **agent**: Compaction strategy chain — `_run_compaction_chain()` tries three strategies in
  order: (1) LLM-based `compact_messages` for intelligent summarization, (2) `emergency_drop`
  keeping the N most recent messages, (3) `deterministic_trim` always succeeding as a last resort;
  system message is preserved through all strategies; `ON_COMPACTION` hook data includes
  `strategy`, `before_count`, `after_count`

- **memory/compaction**: `multi_part_compact` — chunked LLM compaction for very long histories
  that exceed a single LLM context; splits into overlapping chunks, summarizes each, then
  combines summaries

- **memory/compaction**: `emergency_drop(messages, *, keep_last_n=5)` — truncates history to the
  N most recent messages while preserving any leading system message

- **memory/compaction**: `deterministic_trim(messages, *, target_count=20)` — slices history to
  at most `target_count` messages, preserving system message; always succeeds (no LLM call)

- **memory**: File backend — `FileMemory` in `sage/memory/file_backend.py`; stores memories as
  JSON lines in a flat file; supports the full `MemoryProtocol` (store, recall via numpy cosine
  similarity, compact, clear, forget); enabled via `backend: file` in agent frontmatter

- **memory**: `auto_load` / `auto_load_top_k` — new `MemoryConfig` fields to automatically recall
  the top-K memories and inject them as a system message before each LLM call; wired via the
  `auto_memory` builtin hook

- **coordination**: Message bus (`sage/coordination/bus.py`) — in-memory per-agent inboxes with
  TTL-based expiry, idempotency via seen-ID deduplication, overflow protection (drops oldest on
  full inbox), dead-letter collection for expired messages, and broadcast delivery

- **coordination**: Typed message envelopes (`sage/coordination/messages.py`) — `MessageEnvelope`
  with `id`, `sender`, `recipient`, `topic`, `payload`, `timestamp`, `ttl`; `ReplyEnvelope` for
  request/reply correlation

- **coordination**: Cancellation scopes (`sage/coordination/cancellation.py`) —
  `CancellationScope` that propagates a cancel signal across async tasks; nested child scopes
  inherit parent cancellation; `scope.cancel()` / `scope.is_cancelled` / `scope.check()` raise
  `CancelledError` on entry when already cancelled

- **coordination**: `SessionManager` (`sage/coordination/session.py`) — manage concurrent agent
  sessions with create/get/list/destroy lifecycle; `SessionState` holds agent name, metadata,
  timestamps, message count, and status; metadata is preserved across `clear()`

- **research**: Pre-response research system (`sage/research.py`) — `ResearchTrigger` enum
  (`NEVER`, `ALWAYS`, `KEYWORDS`, `LENGTH`, `QUESTION`), `should_research()` predicate,
  `run_research()` async function that runs a mini tool-calling loop to gather context before the
  main response; configured via `research:` in frontmatter (`enabled`, `max_sources`, `timeout`)

- **parsing**: Multi-format tool call parser (`sage/parsing/tool_calls.py`) — parser chain for
  OpenAI JSON, XML-tagged, markdown code-fence, and key-value tool call formats; composable via
  `ChainParser`; `ToolCallParser` protocol for custom parsers

- **parsing**: JSON repair (`sage/parsing/json_repair.py`) — heuristic fixer for common LLM JSON
  output errors (unquoted keys, trailing commas, single quotes, truncated strings); used by the
  JSON tool-call parser before falling back

- **tools**: `ToolDispatcher` (`sage/tools/dispatcher.py`) — parallel and sequential tool dispatch
  with per-tool timeout enforcement, result ordering, and error isolation per call

- **context**: `ContextFallbackTable` (`sage/context/fallback_table.py`) — static lookup table of
  model context window sizes for when litellm model info is unavailable; covers 60+ models across
  OpenAI, Anthropic, Google, Mistral, Cohere, and Meta families

- **config**: New `AgentConfig` fields for hook-driven features — all optional, all default `None`:
  `credential_scrubbing: CredentialScrubConfig`, `query_classification: QueryClassificationConfig`,
  `research: ResearchConfig`, `follow_through: FollowThroughConfig`, `session: SessionConfig`

- **agent**: Approval-aware tool execution — `_execute_tool_calls` appends tool result messages
  to the shared `messages` list and respects per-tool approval state; subagent crash isolation
  wraps `delegate()` in a try/except so a crashing subagent returns a structured error string
  instead of propagating the exception to the parent

## v1.6.0 (2026-02-27)

### Features

- **skills**: Global skill pool with per-agent allowlist — skills are now resolved from a single
  global directory shared across all agents; `skills_dir` is a top-level `config.toml` field with
  waterfall resolution (`config.toml` → `$cwd/skills` → `~/.agents/skills` → `~/.claude/skills`);
  each agent in `[agents.<name>]` can optionally specify a `skills` allowlist to restrict which
  skills from the global pool it receives; subagents always inherit the full unfiltered pool and
  apply their own allowlist independently

- **skills**: `resolve_skills_dir()` waterfall resolver in `sage/skills/loader.py` — resolves the
  global skills directory using priority order: explicit `config.toml` path → `$cwd/skills` →
  `~/.agents/skills` → `~/.claude/skills` → `None`

- **skills**: `filter_skills_by_names()` allowlist filter in `sage/skills/loader.py` — `None` returns
  all skills, `[]` returns none, `["x","y"]` returns only named skills; pool order is preserved

- **config**: `MainConfig.skills_dir` — new top-level field in TOML config for global skills directory

- **config**: `AgentOverrides.skills` — new per-agent allowlist field in `[agents.<name>]` sections

### Breaking Changes

- **config**: `skills_dir` removed from agent frontmatter (`AgentConfig`) and per-agent TOML
  overrides (`AgentOverrides`) — use top-level `skills_dir` in `config.toml` instead

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
