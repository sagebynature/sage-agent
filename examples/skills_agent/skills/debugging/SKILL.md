---
name: debugging
description: Structured debugging methodology based on the scientific method
---

When debugging, follow this sequence:

1. **Reproduce** — Confirm you can trigger the failure reliably. Note the exact input, environment, and observed output.
2. **Isolate** — Narrow the failing scope. Bisect if needed (e.g., git bisect, commenting out code, minimal repro).
3. **Hypothesise** — Form a specific, falsifiable hypothesis about the root cause before looking at code.
4. **Inspect** — Read the code on the suspected path. Check logs, add print/debug statements, or use a debugger.
5. **Verify** — Test your hypothesis. If wrong, revise and repeat from step 3.
6. **Fix** — Apply the minimal change that addresses the root cause. Avoid fixing symptoms.
7. **Confirm** — Re-run the original repro. Add a regression test to prevent recurrence.

Always distinguish between the symptom (what you observe) and the root cause (why it happens).
