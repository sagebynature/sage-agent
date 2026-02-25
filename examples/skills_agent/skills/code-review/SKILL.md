---
name: code-review
description: Systematic checklist for reviewing code quality and correctness
---

When reviewing code, work through these categories in order:

1. **Correctness** — Does the logic match the stated intent? Check edge cases, off-by-one errors, and null/empty inputs.
2. **Clarity** — Are names descriptive? Would a new reader understand the code without comments?
3. **Error handling** — Are errors caught at the right level? Do failures surface useful messages?
4. **Performance** — Are there obvious O(n²) loops, unnecessary allocations, or repeated computations?
5. **Security** — Any injection risks, secrets in code, or untrusted input passed to shell/SQL?
6. **Tests** — Does the change come with tests? Do existing tests still make sense?

For each issue found, state: the location, the problem, and a concrete fix or alternative.
