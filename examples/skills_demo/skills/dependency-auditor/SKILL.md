---
name: dependency-auditor
description: "Audit project dependencies from package.json or requirements.txt — counts packages, classifies version specifiers, and flags unpinned or risky dependencies"
version: "1.0.0"
---

## Usage
Run `node skills/dependency-auditor/audit.js <file>` via the shell tool.

Supported file types:
- `package.json` — analyzes npm dependencies (prod + dev), classifies version specifiers
- `requirements.txt` — analyzes Python packages, flags unpinned (no `==`) entries

Version specifier classifications (npm):
- **exact** — no prefix, e.g. `4.17.23`
- **caret** — `^` prefix, e.g. `^4.18.2` (compatible patch/minor updates)
- **tilde** — `~` prefix, e.g. `~1.13.5` (compatible patch updates only)
- **gt/range** — `>`, `>=`, `<`, `<=`, or `-` range
- **wildcard** — `*` or empty (unpinned, highest risk)

## Examples
```bash
node skills/dependency-auditor/audit.js sample_data/package.json
node skills/dependency-auditor/audit.js sample_data/requirements.txt
```
