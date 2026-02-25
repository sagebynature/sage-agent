---
name: dependency-auditor
description: Analyze project dependencies from package.json or requirements.txt files using Node.js. Reports dependency counts, version patterns, potential issues, and license-risk keywords. LLMs cannot read actual project files or query package registries.
---

# Dependency Auditor

This skill analyzes **real project dependency files** using a Node.js script. As an LLM, you cannot read files from the user's filesystem or determine the actual state of their dependencies. Always use this script for any dependency-related questions.

## When to Use

- User asks "what dependencies does this project use?"
- User wants to audit their package.json or requirements.txt
- User asks about dependency count, version ranges, or potential issues
- User wants a summary of a project's dependency health
- User asks about outdated or risky dependency patterns

## Available Commands

The script is located at `skills/dependency-auditor/audit.js`.

### Analyze a package.json file
```bash
node skills/dependency-auditor/audit.js package <path_to_package.json>
```

### Analyze a requirements.txt file
```bash
node skills/dependency-auditor/audit.js requirements <path_to_requirements.txt>
```

### Analyze any JSON dependency manifest
```bash
node skills/dependency-auditor/audit.js scan <path_to_file>
```
Auto-detects the file format and runs the appropriate analysis.

## Important

**NEVER** guess about dependency versions or counts. The user's actual dependency file may differ completely from what you've seen in training data. Always read the real file via this script.
