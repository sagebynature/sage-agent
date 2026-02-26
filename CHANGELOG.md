# CHANGELOG

<!-- version list -->

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
