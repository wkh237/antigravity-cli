---
name: compact
description: >-
  Compress and summarize conversation history into an executive memory anchor artifact.
  Use when the user types /compact, requests context compaction, or when context length
  approaches token limits, pruning verbose tool logs while preserving crucial architectural invariants.
---

# Context Compaction Skill (`/compact`)

When this skill is activated, you must summarize and condense the current conversation trajectory into an executive memory artifact, pruning low-value intermediate tool execution outputs (e.g. verbose grep outputs, raw terminal logs) while preserving critical state invariants.

---

## Compaction Procedure

### Step 1: Scan and Synthesize Active State
Review the trajectory history and identify:
1. **Primary Goal**: The user's original objective and any updated goals.
2. **Current Status**: What has been completed and what is pending.
3. **Modified Files**: List of all files created or modified with a brief bullet point of changes.
4. **Active Constraints & Rules**: Key architectural decisions, technology choices, or user preferences established.
5. **Active Background Entities**: Any running background commands, subagents, or scheduled tasks.

### Step 2: Write Executive Memory Anchor
Create or overwrite the compacted context artifact at:
`<artifactDir>/compacted_context.md` (or `.agents/compacted_context.md` if workspace-local).

Use the following structure:
```markdown
# Compacted Conversation Context Snapshot
Timestamp: <current_timestamp>

## 1. Primary Objectives
- [x] Completed task A
- [/] In-progress task B
- [ ] Next: task C

## 2. Codebase Modifications
- `path/to/file1.ts`: Added function XYZ for handling auth.
- `path/to/file2.ts`: Fixed regression in database query.

## 3. Active Decisions & Invariants
- Constraint 1: Must remain backward-compatible with v1 schema.
- Constraint 2: Use HTTPS git protocol.

## 4. Immediate Next Step
- <Clear, single-sentence instruction of what step to execute next>
```

### Step 3: Anchor and Acknowledge
Output a concise confirmation to the user:
```markdown
✓ **Context Compacted**: Preserved core task states, file changes, and active constraints in `compacted_context.md`.
Pruned intermediate execution logs. Ready to proceed with: `<Immediate Next Step>`.
```
From this point forward, treat `compacted_context.md` as the authoritative source of truth for earlier conversation context.
