# CHANGELOG

<!-- version list -->

## v1.7.0 (2026-03-08)


## v1.6.0 (2026-03-08)

### Bug Fixes

- Cap event pane height to terminal rows to prevent flickering
  ([`ec24c19`](https://github.com/sagebynature/sage-agent/commit/ec24c19e880c5378a16583849b0eb8f42518267d))

- Clean up barrel export for deleted lifecycle.ts and fix TS strict errors
  ([`7a57660`](https://github.com/sagebynature/sage-agent/commit/7a57660c0353df4a220fe012ed7df108a5fa52fe))

- Enhance input handling in App component
  ([`c35d4c9`](https://github.com/sagebynature/sage-agent/commit/c35d4c91abca13586918fb44415e8db405aea72b))

- Enhance layout of ConversationView, EventInspector, and EventTimeline components
  ([`f55ad1b`](https://github.com/sagebynature/sage-agent/commit/f55ad1b00eb0d31e66ca2a0a63121eed81e71bf2))

- Improve event pane responsiveness and layout adjustments
  ([`fa3d979`](https://github.com/sagebynature/sage-agent/commit/fa3d979730d77b84e2864a01ec6ea0ee6455ea66))

- Optimize event handling and component performance
  ([`c4397f5`](https://github.com/sagebynature/sage-agent/commit/c4397f58de141b43f9a64ef9949262b8acf97d75))

- Resolve assistant message disappearance caused by Ink Static throttle race
  ([`37cd29d`](https://github.com/sagebynature/sage-agent/commit/37cd29d1d4e72e2a9b3fcf2a6ccfac5e3ddf1076))

- Restructure event pane layout to work with Ink's Static/dynamic split
  ([`46b2ed1`](https://github.com/sagebynature/sage-agent/commit/46b2ed16b95315034fe5042b0b4a5a4e9aac3d6b))

- Typo
  ([`ec8c3a3`](https://github.com/sagebynature/sage-agent/commit/ec8c3a3ad65e2dc60cc1deb3e667af4be53d1d22))

- **config**: Raise ConfigError for non-dict frontmatter memory value
  ([`e3cf96b`](https://github.com/sagebynature/sage-agent/commit/e3cf96bd7883e119910022765e364da76fb80150))

- **f4**: Reduce run/stream to <=30 lines, wire dangerous_patterns config, async file_backend I/O
  ([`00473fc`](https://github.com/sagebynature/sage-agent/commit/00473fca361a936c618c263c75d561ba1554dd94))

- **memory**: Add timeout and response-parsing guards to OllamaEmbedding
  ([`2ae3f1c`](https://github.com/sagebynature/sage-agent/commit/2ae3f1c8d5a5ac072da380a17f3a4283bebfa6cf))

- **memory**: Broaden OllamaEmbedding error handling to cover TransportError and TypeError
  ([`7ce1e83`](https://github.com/sagebynature/sage-agent/commit/7ce1e8342a676819bf3a07f483aff5ceb61803b1))

- **memory**: Guard whitespace-only model name in create_embedding
  ([`c796b42`](https://github.com/sagebynature/sage-agent/commit/c796b42d29152bec869142857c6ab0b532eac871))

- **planning**: Replace __import__ hack with proper top-level import
  ([`741d6ef`](https://github.com/sagebynature/sage-agent/commit/741d6efeba2c43d6750dff7aee3f0939e2cdfc0f))

- **tools**: Simplify web_fetch to use direct URL instead of IP-pinned connection
  ([`f43884c`](https://github.com/sagebynature/sage-agent/commit/f43884ccde229dac80e0c3ee3551ea9fa58b6618))

- **tui**: Disable text input when permission prompt is active
  ([`f3abcad`](https://github.com/sagebynature/sage-agent/commit/f3abcade18a1d3c2609e00cf1b0b4b25a1aab6ff))

- **tui**: Fix flickering, tool completion tracking, and streaming line breaks
  ([`c5f134d`](https://github.com/sagebynature/sage-agent/commit/c5f134ded010f4304f7d837d83911407b1e0887a))

- **tui**: Fix race condition dropping tool events, add delegation support, show all tool activity
  ([`afecd8e`](https://github.com/sagebynature/sage-agent/commit/afecd8e3557f3ff5c5701bd10b5d73f6be3ab979))

- **tui**: Force-resolve running tools on stream end
  ([`75de4be`](https://github.com/sagebynature/sage-agent/commit/75de4bef14a2cd04bc0ff866e70e7dbfcbac78c9))

- **tui**: Live elapsed timer, animated spinner, cancel hints
  ([`1482c30`](https://github.com/sagebynature/sage-agent/commit/1482c30eb4db8916f054fdee95b8861fdda2af3e))

- **tui**: Restore lost features and fix critical UX issues
  ([`d9e78e9`](https://github.com/sagebynature/sage-agent/commit/d9e78e90659abb9a724e47477ed731c1449b2f35))

- **tui**: Suppress console.error in IPC client, route through event emitter
  ([`f774cef`](https://github.com/sagebynature/sage-agent/commit/f774cef8e9325800f735ae08155dcb3fb04a880c))

- **tui**: Track delegation callIds so completion marks tool as done
  ([`d7a965e`](https://github.com/sagebynature/sage-agent/commit/d7a965eaeec832e9e07229323674401e4100af52))

- **tui**: Use unique keys for tool list items to avoid React duplicate key warnings
  ([`6e64237`](https://github.com/sagebynature/sage-agent/commit/6e64237f764b8e2b24a49f4fce530e61281ec4f6))

### Chores

- Clean up config.toml by removing an empty line and update pyproject.toml to include truststore
  dependency
  ([`91adf4f`](https://github.com/sagebynature/sage-agent/commit/91adf4f5feb145f912fa4ea026ade93b69259954))

- Remove dead code — framing.py, SplitView.tsx, lifecycle.ts
  ([`a956c28`](https://github.com/sagebynature/sage-agent/commit/a956c28b16018c8c4fc3dea99a2812573bc5acdc))

- Update configuration settings.
  ([`b35d1d2`](https://github.com/sagebynature/sage-agent/commit/b35d1d2483f355c60633e9411e34f2e240a8c011))

- Updated examples
  ([`0ea7522`](https://github.com/sagebynature/sage-agent/commit/0ea752246c7e9bbe2c4a74cd35b4c9d6665788d0))

- **agent**: Trim docstrings to bring agent.py under 1400 lines
  ([`320e40c`](https://github.com/sagebynature/sage-agent/commit/320e40caf57e0b69b3400eb9056761dab7d3365e))

- **agent**: Update sage-agent version to 1.5.0
  ([`e33b77a`](https://github.com/sagebynature/sage-agent/commit/e33b77abf2d1698e43c86d65a173f5491c234644))

- **cicd**: Update commit message format in pyproject.toml
  ([`254df0d`](https://github.com/sagebynature/sage-agent/commit/254df0dce91fc6b5a08185397a2e781dc8b19b26))

- **cleanup**: Rename duplicate ResearchConfig, consolidate config models, remove dead code
  ([`bc89f81`](https://github.com/sagebynature/sage-agent/commit/bc89f81890a879b14cf8160aef65e2646881372e))

- **config**: Add OPENROUTER_API_KEY to config and update example paths
  ([`d528a72`](https://github.com/sagebynature/sage-agent/commit/d528a72a598c22166a97da6e1f963de9785d3095))

- **config**: Set default memory embedding to ollama/nomic-embed-text
  ([`c469343`](https://github.com/sagebynature/sage-agent/commit/c46934383a9bcc685f70d34a35a1c47174692d09))

- **config**: Update agent configurations and clean up memory settings
  ([`e7efbb7`](https://github.com/sagebynature/sage-agent/commit/e7efbb7bbb1a55fb9c1dcf6de2ce52b2634977f8))

### Documentation

- Add default memory config design doc
  ([`05ad304`](https://github.com/sagebynature/sage-agent/commit/05ad3048ec9775dd6c28fd2d72ce5cf14e5aa984))

- Add default memory config implementation plan
  ([`61997f1`](https://github.com/sagebynature/sage-agent/commit/61997f1cd96c80112471cbd509b1e44b64ad53be))

- Add Ollama embedding implementation plan
  ([`2901606`](https://github.com/sagebynature/sage-agent/commit/2901606b02c3ab90fe395c33ae55e889a4920266))

- Add Ollama embedding support design doc
  ([`7307856`](https://github.com/sagebynature/sage-agent/commit/730785692d123665b0356afe70cfae63913aab9c))

- Correct MemoryConfig validation description in design doc
  ([`7ade3c8`](https://github.com/sagebynature/sage-agent/commit/7ade3c83e16f106f6a6842dd26c8b05c7a954257))

- Future enhancement plans
  ([`d05f7c3`](https://github.com/sagebynature/sage-agent/commit/d05f7c38679326a252645c840071e547ee0f3398))

- Remove outdated plan and design documents.
  ([`c6df662`](https://github.com/sagebynature/sage-agent/commit/c6df6626e7635fd2d5b6f5c3ccd6c6ac3cb5eef6))

- TUI UX overhaul design — Claude Code-inspired redesign
  ([`fbfddbe`](https://github.com/sagebynature/sage-agent/commit/fbfddbe37b1ef7716682ca83832313d6925f65a8))

- Update documentation for hook/event/observability enhancements and Node.js TUI
  ([`b8f2222`](https://github.com/sagebynature/sage-agent/commit/b8f222208e35da2f2135d443b0c7d7b2327b9d3c))

- **tui**: Add bug fix design and implementation plan
  ([`696543e`](https://github.com/sagebynature/sage-agent/commit/696543ed3a7ed53164aa1ddd04f170ffc1475d70))

- **tui**: Update README to reflect current feature state
  ([`02f595f`](https://github.com/sagebynature/sage-agent/commit/02f595f92b9643cc0fb76b8c9c4dfd8279fb43d7))

### Features

- Implement canonical event system in TUI with dedicated normalizer, projector, and new event-driven
  components.
  ([`583da63`](https://github.com/sagebynature/sage-agent/commit/583da6349d30d418ad44df15f75f7501dcf0223c))

- Implement event normalization and display system, including timeline and inspector components, and
  enhance tool rendering for delegate and use_skill.
  ([`e9540b5`](https://github.com/sagebynature/sage-agent/commit/e9540b54d2e103c404d7c2b8335183fbdb002630))

- Introduce event timeline and inspector UI with verbosity and filtering options
  ([`2f6cf90`](https://github.com/sagebynature/sage-agent/commit/2f6cf908058ff7a89bf0d2322e0b0f45987cf947))

- Refactor safe_coder example structure and add global install script for the TUI.
  ([`05ca64c`](https://github.com/sagebynature/sage-agent/commit/05ca64cf89cabc2accbd0330d284b13b549a256c))

- **agent**: Propagate subagent tool/stream events to parent agent
  ([`176ae7a`](https://github.com/sagebynature/sage-agent/commit/176ae7a14b28cd08424b3461f3eb4689753e8dcf))

- **config**: Deep-merge memory config across defaults, agent overrides, and frontmatter
  ([`62be197`](https://github.com/sagebynature/sage-agent/commit/62be1973bf73fbed4b97bc9119a42f40aeadaa1a))

- **config**: Expose hardcoded constants + parallelize MCP init
  ([`9ee99ed`](https://github.com/sagebynature/sage-agent/commit/9ee99ed9c70ca45ed25193ff67262dfc2e99af98))

- **config**: Move memory field to ConfigOverrides to support [defaults.memory]
  ([`ca9c7b1`](https://github.com/sagebynature/sage-agent/commit/ca9c7b1c05072c57dd1cc37edfb7cfdfab3ee3b1))

- **memory**: Add create_embedding() factory with ollama/ prefix routing
  ([`d0f09a8`](https://github.com/sagebynature/sage-agent/commit/d0f09a8257da791a1cbe543e69549a187af0680f))

- **memory**: Add OllamaEmbedding with direct HTTP client
  ([`b92639b`](https://github.com/sagebynature/sage-agent/commit/b92639bd654cd281261e0a02659e83c941715357))

- **memory**: Wire create_embedding() in agent bootstrap, export new symbols
  ([`6b201ca`](https://github.com/sagebynature/sage-agent/commit/6b201ca519735752d141fc62cf9be2c34c3f8316))

- **protocol**: Compute real contextUsagePercent from agent usage stats
  ([`6759f0c`](https://github.com/sagebynature/sage-agent/commit/6759f0cf890eab67bca5443eea23a3e32247b90e))

- **protocol**: Switch agent/run to streaming and add run/completed notification
  ([`db81295`](https://github.com/sagebynature/sage-agent/commit/db81295e9e1e67a7d74400f4f66feb638d5d7429))

- **protocol**: Wire JsonRpcPermissionHandler in serve.py
  ([`a3b32bf`](https://github.com/sagebynature/sage-agent/commit/a3b32bfa45cf818d007dbba4f90ca1958f02cabe))

- **tui**: Add ActiveStreamView with thinking indicator and live markdown
  ([`a9cb9e0`](https://github.com/sagebynature/sage-agent/commit/a9cb9e0746329946e8871f4ce923eb1079ef88e3))

- **tui**: Add agent indicator and session name to BottomBar
  ([`f376cb7`](https://github.com/sagebynature/sage-agent/commit/f376cb791e5cb61e36df0d820da9020c1e98822f))

- **tui**: Add animated spinners for running tools and delegations
  ([`a253dbb`](https://github.com/sagebynature/sage-agent/commit/a253dbbc0b8eef0639fb551ba535ed7cddded3b7))

- **tui**: Add block renderers — UserBlock, TextBlock, ToolBlock, StaticBlock
  ([`54bcffc`](https://github.com/sagebynature/sage-agent/commit/54bcffc3c0cb548e9123a15cf127079948de605c))

- **tui**: Add blockReducer with OutputBlock/ActiveStream state model
  ([`015f667`](https://github.com/sagebynature/sage-agent/commit/015f667a8d97ae7f67c4b6aa4b363ddec807f624))

- **tui**: Add BottomBar and InputPrompt with minimal chrome
  ([`ea21dd0`](https://github.com/sagebynature/sage-agent/commit/ea21dd0ef4ecd70d8c011f3860255d7dc5d81185))

- **tui**: Add ConversationView with Static scroll + ActiveStreamView
  ([`c094ed1`](https://github.com/sagebynature/sage-agent/commit/c094ed1a4a86dfe5189b965052d6ad63f432ef9f))

- **tui**: Add executable script and update package.json
  ([`fd0a26e`](https://github.com/sagebynature/sage-agent/commit/fd0a26ea758e0be0713036829dcf60968a390b73))

- **tui**: Add OutputBlock, ActiveStream, AppStateV2 types
  ([`07768e9`](https://github.com/sagebynature/sage-agent/commit/07768e96160f04303a9d5d4fd8ae390e0b7cf08b))

- **tui**: Add RUN_COMPLETED protocol constant and payload type
  ([`fc04d51`](https://github.com/sagebynature/sage-agent/commit/fc04d51cc03519973144ff93d7bf2d6cc37fdc0c))

- **tui**: Add scroll state for active stream view
  ([`70ce7a9`](https://github.com/sagebynature/sage-agent/commit/70ce7a956e14650b4ab47ab756e0f2646e914fdf))

- **tui**: Add TypeScript TUI with Ink v6 and JSON-RPC protocol layer
  ([`6f5e15d`](https://github.com/sagebynature/sage-agent/commit/6f5e15d02dd6890cbd9fe90d8566901d28b95f44))

- **tui**: Complete BlockEventRouter with agent tracking and LLM turn methods
  ([`bf27552`](https://github.com/sagebynature/sage-agent/commit/bf27552202107cf864502e8ffef61fdd3f65bff0))

- **tui**: Extend BlockState with agents, CLEAR_BLOCKS, permission pruning
  ([`c12d5a5`](https://github.com/sagebynature/sage-agent/commit/c12d5a5ea02faa51ccc9ef54c375cac5f8132026))

- **tui**: Handle run/completed notification in EventRouter
  ([`7780d3f`](https://github.com/sagebynature/sage-agent/commit/7780d3f9c808bf16f2e6bcecdd7f3fb1cc5bb0f7))

- **tui**: Implement all 21 slash commands with honest stubs for unbuilt features
  ([`61c4237`](https://github.com/sagebynature/sage-agent/commit/61c4237342cd557998bcbfe37b93eb1ee78648f1))

- **tui**: Implement all missing command handlers in CommandExecutor
  ([`51ca1e2`](https://github.com/sagebynature/sage-agent/commit/51ca1e27ae7b3778a760ac032f129859dd93dfad))

- **tui**: Implement BACKGROUND_TASK_UPDATE and COMPACTION_STARTED reducers
  ([`5ac8332`](https://github.com/sagebynature/sage-agent/commit/5ac8332d24016a6b4016d8ed35a8b2e0f2fdf298))

- **tui**: Implement keyboard shortcuts for scroll, clear, reset, permissions
  ([`15f2053`](https://github.com/sagebynature/sage-agent/commit/15f2053105fac2e27caa38aa110c4d0cda2c96ef))

- **tui**: Render PermissionPrompt in AppShell and wire permission/respond
  ([`7b77ede`](https://github.com/sagebynature/sage-agent/commit/7b77ede77ed4724a5b5559e48f6b97eb7098f6df))

- **tui**: Render streaming text as plain text for instant display
  ([`5673925`](https://github.com/sagebynature/sage-agent/commit/5673925d89a10d757f164825f89f95069647576b))

- **tui**: Subscribe to run/completed in wiring layer
  ([`e674fad`](https://github.com/sagebynature/sage-agent/commit/e674fad799a49b1943dde419139cfd1e5c792365))

- **tui**: Wire Ctrl+C and ESC to agent/cancel request
  ([`30cf0c5`](https://github.com/sagebynature/sage-agent/commit/30cf0c5eab3ac3a248aeff2fb2cb222a2f0773eb))

- **tui**: Wire new block-based architecture into AppShell
  ([`c570bdc`](https://github.com/sagebynature/sage-agent/commit/c570bdc3a7948ea1de48411f9741e59bf7e4be92))

- **tui**: Wire SlashCommands autocomplete and command execution
  ([`f74161d`](https://github.com/sagebynature/sage-agent/commit/f74161d2d9b394c407cf25f65fbfcd2e8ad34b71))

- **tui**: Wire useResizeHandler for dynamic terminal dimensions
  ([`fe9b1b9`](https://github.com/sagebynature/sage-agent/commit/fe9b1b963ab468f4674e8e9c738d5a36708b9a02))

### Performance Improvements

- **memory**: Optimize recall paths for sqlite and file backends
  ([`9659c2f`](https://github.com/sagebynature/sage-agent/commit/9659c2f7667b5a56ca05720790beb4e0b7d6cdab))

- **tui**: Cache Marked parser instance to avoid recreation per render
  ([`9de2842`](https://github.com/sagebynature/sage-agent/commit/9de28425f13d87d51502ab0a310f4094645985c8))

- **tui**: Isolate spinner provider from stream content to reduce re-renders
  ([`0f225c3`](https://github.com/sagebynature/sage-agent/commit/0f225c3ab3fad5381abe449997bd77828b4ab891))

- **tui**: Truncate active stream to last 30 lines to prevent overflow
  ([`e687e50`](https://github.com/sagebynature/sage-agent/commit/e687e501ac02506aa24e24222095c540ddd9f544))

### Refactoring

- Remove outdated ADR-0001 on hook observability and event publishing
  ([`e155c46`](https://github.com/sagebynature/sage-agent/commit/e155c467d73c292f4adafdcd7202bb9146c03f38))

- **agent**: Extract _execute_turn from run/stream duplication
  ([`072c1c5`](https://github.com/sagebynature/sage-agent/commit/072c1c579fc3c48b6f8ef91abf7dfc2932740e0a))

- **agent**: Extract factory builders from _from_agent_config
  ([`858b08d`](https://github.com/sagebynature/sage-agent/commit/858b08d9b53f6b0a4ccbfd3f2441aefcb2be13d6))

- **agent**: Extract message builder and memory tools to reduce agent.py to <1400 LOC
  ([`6fb9442`](https://github.com/sagebynature/sage-agent/commit/6fb9442df1dfbdac06b7fd950d5e6afd92f4aa8b))

- **agent**: Extract tool registration to sage/tools/agent_tools/
  ([`e393f2d`](https://github.com/sagebynature/sage-agent/commit/e393f2da7b8d458bd251463a7157e2b63cdab058))

- **misc**: Remove deprecated tools, fix async I/O, add memory registry, extract compaction
  ([`4b85367`](https://github.com/sagebynature/sage-agent/commit/4b85367bf223c6e8df2804cbb11ca39bb47efdf3))

- **tui**: Delete all orphaned components, hooks, and utils
  ([`b5765ea`](https://github.com/sagebynature/sage-agent/commit/b5765ea8a11f4be8c127834951ed4a3fe0c4ee10))

- **tui**: Delete old AppState/EventRouter/CommandExecutor state system
  ([`3b2516c`](https://github.com/sagebynature/sage-agent/commit/3b2516c59c70df8fc079cf747c5c9d3c575d9f67))

- **tui**: Port ToolDisplay to ToolSummary, replace ToolBlock in StaticBlock
  ([`a981cbf`](https://github.com/sagebynature/sage-agent/commit/a981cbf70cec3e06338a7f616156179713e6090c))

- **tui**: Remove dead ChatMessage, AppState, AppStateV2 types
  ([`ec9867b`](https://github.com/sagebynature/sage-agent/commit/ec9867bd454e5ed4dfeb06de10fe17798fa117fd))

### Testing

- **tui**: Update tests for block-based architecture, fix TS strict errors
  ([`74ec5a4`](https://github.com/sagebynature/sage-agent/commit/74ec5a44283617725aba5ec1490c22f7902ea1c9))


## v1.5.0 (2026-03-03)

### Chores

- Remove obsolete TUI design and implementation documents
  ([`61ba674`](https://github.com/sagebynature/sage-agent/commit/61ba67457a41b915c8ad08c3ab0b2afd6f75b9af))

- Update .gitignore and remove obsolete agent documentation
  ([`79e3633`](https://github.com/sagebynature/sage-agent/commit/79e363305b5a5ecd5c274ccac38561d8ec3c22c2))

- Update type-check command and add ty for type checking
  ([`559f3ad`](https://github.com/sagebynature/sage-agent/commit/559f3adaf7bdffad976f38bb1d74b22fc6df4f57))

### Documentation

- Update README, add demo make targets, fix tool error logging
  ([`c8780cf`](https://github.com/sagebynature/sage-agent/commit/c8780cf3a2d56c85e468d19663fc66049daa30fa))

### Features

- Enhance sage-agent with notepad system and model-specific prompt overlays
  ([`4cf7c4b`](https://github.com/sagebynature/sage-agent/commit/4cf7c4b22da88f6a79cdb3d88a689503b4ea4435))

- Implement Phase 1 foundation — tool restrictions, session continuity, category routing
  ([`c95640d`](https://github.com/sagebynature/sage-agent/commit/c95640d3b58420c297113c8d9bcf23f6c09e64f7))

- Implement Phase 2 — async background execution and dynamic prompt construction
  ([`7f6435b`](https://github.com/sagebynature/sage-agent/commit/7f6435b40a7c4ba1e9b0701d104a1ff39a376523))

- Implement Phase 3 planning pipeline and fix aiosqlite teardown race
  ([`4450922`](https://github.com/sagebynature/sage-agent/commit/4450922f0caa507f126647fc44c180749183632e))


## v1.4.0 (2026-03-03)

### Bug Fixes

- **eval**: Improve path resolution for context files in EvalRunner
  ([`b15b015`](https://github.com/sagebynature/sage-agent/commit/b15b0151dc81e2e25fc874875fb74e55c538bd69))

- **provider**: Add drop_params for cross-provider streaming compatibility
  ([`ec3db46`](https://github.com/sagebynature/sage-agent/commit/ec3db463f5bc382901ebee4d416ea682230356b5))

- **tui**: Cancel in-flight title generation before starting agent call
  ([`fb66a78`](https://github.com/sagebynature/sage-agent/commit/fb66a78aec237357997ebd55d54dcae186d334ac))

- **tui**: Fix session title prompt to prevent echoing assistant response
  ([`2ba26f5`](https://github.com/sagebynature/sage-agent/commit/2ba26f534d7fdf734c43577d10d5c828eeaa9bc2))

- **tui**: Move title generation to after agent responds
  ([`8b4a29b`](https://github.com/sagebynature/sage-agent/commit/8b4a29bfc186d8376208f692f5758eac5d89da12))

- **tui**: Resolve chat scroll race condition and stuck scrollbar
  ([`c447d2d`](https://github.com/sagebynature/sage-agent/commit/c447d2d13db613f4763bfa1b8a07a7f203eaaf35))

- **tui**: Store asyncio task reference, remove hasattr guard, cancel on clear
  ([`c359a07`](https://github.com/sagebynature/sage-agent/commit/c359a07e72d141c95696ac0361268dbc4d356175))

### Chores

- Update .gitignore and modify example agent commands
  ([`dd330f2`](https://github.com/sagebynature/sage-agent/commit/dd330f24a842f9f6614cc8a3bb2a83d7ad6d6264))

### Documentation

- Add TUI separation design document
  ([`a4fb9fe`](https://github.com/sagebynature/sage-agent/commit/a4fb9fe60cc785a42b84c1f0b033de524cf76abb))

- Add TUI separation implementation plan
  ([`ac3d4c4`](https://github.com/sagebynature/sage-agent/commit/ac3d4c449fb9d889913b8b007a0a920404744c7d))

### Features

- **agent**: Add reset_session() for full session state reset
  ([`613399c`](https://github.com/sagebynature/sage-agent/commit/613399ce4c0334b2ad1cf2840f229a187349ee9d))

- **tui**: Add session state and background title generation
  ([`f0ccc09`](https://github.com/sagebynature/sage-agent/commit/f0ccc0907ffc6ccf96524c41bb7811d88340e3fb))

- **tui**: Intent-focused session title prompt, ctrl+n for new session
  ([`a2837cc`](https://github.com/sagebynature/sage-agent/commit/a2837cc83f6e38e4e34514539f5f7dedd6607ef1))

- **tui**: Redesign status panel layout and add ctrl+b toggle
  ([`b612f3c`](https://github.com/sagebynature/sage-agent/commit/b612f3ccf1188bc895782feb13294c95f04b2b86))

- **tui**: Wire session lifecycle and update tests
  ([`a405436`](https://github.com/sagebynature/sage-agent/commit/a405436e4acaa3c29d7c338a232fe3814e53d78e))

### Refactoring

- Remove TUI code from sage-agent (moved to sage-tui)
  ([`8dca334`](https://github.com/sagebynature/sage-agent/commit/8dca33466b2c01547884c0a81957a3528131ee65))


## v1.3.0 (2026-03-02)

### Features

- **changelog, plans, readme, docs**: Update changelog for v1.13.0, mark plans as done, enhance
  README and documentation
  ([`133e3b0`](https://github.com/sagebynature/sage-agent/commit/133e3b0e7f718512e6ab59537c6366f771648652))


## v1.2.0 (2026-03-02)

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

- **cli,tui**: Resolve agents_dir relative to config.toml and fix chat sandwich
  ([`66c6d4b`](https://github.com/sagebynature/sage-agent/commit/66c6d4b7579f3a28ca3360fe9803b9653008fc4d))

- **eval**: Multi-model support, tool tracking, and cancel-scope isolation
  ([`c053c2f`](https://github.com/sagebynature/sage-agent/commit/c053c2fce000218e99689529994ed7091a48e3db))

- **eval**: Propagate model override to provider in EvalRunner
  ([`63add67`](https://github.com/sagebynature/sage-agent/commit/63add67f58994bead187e705e4972368d5f1e4d1))

- **eval**: Resolve agent and context_files paths relative to suite YAML directory
  ([`cb06b18`](https://github.com/sagebynature/sage-agent/commit/cb06b185d231f6fa085f35d4b69fae7f0fa05e66))

- **eval**: Update model list in security and smoke evaluation files
  ([`83a4bd1`](https://github.com/sagebynature/sage-agent/commit/83a4bd14d2b4fc460fc8989bd01b931075510014))

- **examples/skills_demo**: Chdir to demo_dir so skill script relative paths resolve correctly
  ([`37ecd86`](https://github.com/sagebynature/sage-agent/commit/37ecd86c1eb20f61cfcb2f714286d32f85554100))

- **git**: Address code review — path traversal, snapshot refactor, case-insensitive patterns,
  shared fixtures
  ([`29c0fc5`](https://github.com/sagebynature/sage-agent/commit/29c0fc585a69fedb3d579d774238c40afd71fc54))

- **makefile**: Correct parallel_agents subagent paths in validate-examples
  ([`f27d8d1`](https://github.com/sagebynature/sage-agent/commit/f27d8d13e1e2560a780156baa05f421a26abd2e3))

- **mcp**: Handle RuntimeError during MCP disconnect for cosmetic cleanup
  ([`f9c3319`](https://github.com/sagebynature/sage-agent/commit/f9c33196bcf601cd27c45411852d16cb3d561f72))

- **memory**: Address Phase 3 final review — OperationalError fallback, config passthrough, rowid
  join, log improvements
  ([`3a53648`](https://github.com/sagebynature/sage-agent/commit/3a536482dfc0a1cd5422c2c45f73319734addb45))

- **orchestrator**: Await cancelled race tasks for proper resource cleanup
  ([`0e1a078`](https://github.com/sagebynature/sage-agent/commit/0e1a0784d6b155b62208875677320708889ec2e5))

- **permissions**: Allow unknown-category tools (MCP) through policy handler
  ([`ece8d15`](https://github.com/sagebynature/sage-agent/commit/ece8d15e0af3b9cd7bb1c64eb4ef21093f761db2))

- **phase4**: Address final review findings
  ([`b9a2ab5`](https://github.com/sagebynature/sage-agent/commit/b9a2ab55ea274a5a9a6a986ce16a51cd35ca1cf2))

- **security**: Remove python -c from dangerous patterns blocklist
  ([`a40b91d`](https://github.com/sagebynature/sage-agent/commit/a40b91d03d5395918af0e119b9b692c5c13d7b92))

- **skills**: Auto-load config.toml in from_config and expand env vars in resolve_skills_dir
  ([`a8d14a3`](https://github.com/sagebynature/sage-agent/commit/a8d14a30aa82587635248be1a4860082483f26e5))

- **tests**: Update stale test to reflect intentional MCP tool pass-through behaviour
  ([`cc1f06f`](https://github.com/sagebynature/sage-agent/commit/cc1f06f100acbe7decdbe933222ebaa404f0a14a))

- **tracing**: Address Phase 5 review suggestions
  ([`6c49a83`](https://github.com/sagebynature/sage-agent/commit/6c49a83595f557a171e3189fdf26881f44c8a3dc))

- **tui**: Correct status bar keyboard hint for ctrl+l vs ctrl+L
  ([`8cee0a3`](https://github.com/sagebynature/sage-agent/commit/8cee0a3295994a37cf77dc2f7d5652334669b3eb))

- **tui**: Eliminate log flash, fix auto-scroll, thin scrollbar
  ([`81e7d30`](https://github.com/sagebynature/sage-agent/commit/81e7d3026e592fca69c8512ca559c6586c0d7b9a))

- **tui**: Make HistoryInput._on_key async and add empty-history test
  ([`2285234`](https://github.com/sagebynature/sage-agent/commit/2285234795953a758f1ed1b610f25b9383248350))

- **tui**: Stop sage log records from reaching root StreamHandler during TUI
  ([`ffe4282`](https://github.com/sagebynature/sage-agent/commit/ffe428222d0a35c33c1cedfe4252d219b0b89193))

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

- **tui**: Resize panels to 80/20 split
  ([`2f014c5`](https://github.com/sagebynature/sage-agent/commit/2f014c522b1018d3059a085dcf01155f834e34c6))

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

- Add TUI enhancements design document
  ([`ed8004c`](https://github.com/sagebynature/sage-agent/commit/ed8004c263f5fa46761d554ba42067fe0ed2761b))

- Add TUI enhancements implementation plan
  ([`008c64b`](https://github.com/sagebynature/sage-agent/commit/008c64b06c3f607860081fe09c21bf1794d12e32))

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

- **tui**: Update module docstring to reflect new layout
  ([`fbde0fb`](https://github.com/sagebynature/sage-agent/commit/fbde0fb5d28b2b88bd8127b54a745c6ff1d71341))

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

- **cli**: Make agent-config optional for `sage tui` and `sage agent run`
  ([`b2b63e4`](https://github.com/sagebynature/sage-agent/commit/b2b63e4f4a38b9f63a358ef3563ebb7596633f03))

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

- **events**: Add typed event layer with agent.on() subscription API
  ([`d64d02b`](https://github.com/sagebynature/sage-agent/commit/d64d02bf17d588b0fc2c8bd45471e87e71feb7c9))

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

- **tui**: Add AssistantEntry with TextArea for mouse-selectable responses
  ([`cb6f94e`](https://github.com/sagebynature/sage-agent/commit/cb6f94e3eddb54a1b657f18a31da64702ebf5a0b))

- **tui**: Add HistoryInput with up/down arrow navigation
  ([`9830ab8`](https://github.com/sagebynature/sage-agent/commit/9830ab87caa01fe1bb1a25fc600e57c43530dc41))

- **tui**: Add LogPanel and TUILogHandler for togglable log output
  ([`dbe5bc7`](https://github.com/sagebynature/sage-agent/commit/dbe5bc729d49e44fa367ee8fc9d445eec6f07bf9))

- **tui**: Add StatusPanel replacing ActivityPanel
  ([`d5bf87c`](https://github.com/sagebynature/sage-agent/commit/d5bf87c60e4571fbe42eff389a2366f204808298))

- **tui**: Add ToolEntry collapsible widget for tool calls
  ([`0c96032`](https://github.com/sagebynature/sage-agent/commit/0c96032d9af47c03edd1957997e37ad0a7120789))

- **tui**: Add UserEntry and ThinkingEntry chat widgets
  ([`535b7b7`](https://github.com/sagebynature/sage-agent/commit/535b7b70b670999b7ea9dbbb21de43d95b5a99a4))

- **tui**: Enhance tool call handling and response management
  ([`97530f3`](https://github.com/sagebynature/sage-agent/commit/97530f35b1a36425e3ef898c1297dcfae54186b8))

- **tui**: Markdown rendering, collapsible skills, log panel fix
  ([`75a40b9`](https://github.com/sagebynature/sage-agent/commit/75a40b9ab82710c76b0ce5a6b40757ee0ba0d2a9))

- **tui**: Multiline input, fixed-width status panel, permission modal, and mypy fixes
  ([`71aa20f`](https://github.com/sagebynature/sage-agent/commit/71aa20fbc2c99badcdade16977eff169ef34119f))

- **tui**: Refactor ChatPanel to use typed entry widgets
  ([`1bbdfff`](https://github.com/sagebynature/sage-agent/commit/1bbdfff1bd6ae3b95f3930f120caeb1a09bd6a62))

- **tui**: Scroll-pin auto-scroll that respects user scroll position
  ([`850eb58`](https://github.com/sagebynature/sage-agent/commit/850eb587b279657aeef2d1b474bdbf6f09bfa501))

- **tui**: Wire SageTUIApp with new layout, status panel, and log toggle
  ([`4fca368`](https://github.com/sagebynature/sage-agent/commit/4fca3681d660b87ea6303183595a1e70f4f7e167))

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

- **mcp**: Enhance logging and suppress async generator errors
  ([`06314b9`](https://github.com/sagebynature/sage-agent/commit/06314b903c016c6c5fcbfdfea4c3e49c66077084))

- **policy**: Remove unnecessary comments regarding unknown categories
  ([`f9c3319`](https://github.com/sagebynature/sage-agent/commit/f9c33196bcf601cd27c45411852d16cb3d561f72))

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
