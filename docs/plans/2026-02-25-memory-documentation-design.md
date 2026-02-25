# Design: Memory Management Documentation

## Date
2026-02-25

## Goal
Create a comprehensive document at `docs/memory.md` covering the memory subsystem for both Sage users (configuring/running agents with memory) and contributors (extending the system with new backends or embedding providers).

## Audience
Both users and contributors, structured with progressive depth so readers stop when they have what they need.

## Structure

1. **Opening + Quickstart** - What memory does, minimal steps to enable it
2. **Configuration Reference** - All fields, config sources, resolution order, embedding model examples
3. **How It Works** - Architecture diagrams (Mermaid), runtime lifecycle, data flow, compaction, storage schema
4. **Contributing** - New backends, new embedding providers, testing patterns, code map
5. **Troubleshooting** - Common errors and fixes
6. **Logging Reference** - Log messages by level and what they indicate

## Decisions
- Location: `docs/memory.md`
- Diagrams: Mermaid (renders on GitHub)
- Progressive depth structure (user-first)
