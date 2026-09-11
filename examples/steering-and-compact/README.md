# In-Flight Steering & Context Compaction for Antigravity

This directory contains a complete, working reference implementation of:
1. **In-Flight Steering via Tool Response Hijacking** (using Antigravity Lifecycle Hooks).
2. **Context Compaction Skill (`/compact`)** (using the Antigravity Skills system).

---

## 1. Architecture Overview

### Steering Mechanism (`hooks.json` + `steer_hook.py`)
Instead of violating Gemini/OpenAI API schema rules by inserting rogue messages, we use Antigravity's native `PreToolUse` and `PreInvocation` hooks:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant CLI as agy-steer
    participant Hook as steer_hook.py
    participant Agent as Antigravity Agent
    participant LLM as Gemini Model

    Agent->>Hook: PreToolUse (tool: replace_file_content)
    Note over User,CLI: User types: agy-steer --abort "Stop and fix router.tsx"
    CLI->>Hook: Write to /tmp/agy_steering queue
    Hook-->>Agent: decision: "deny", reason: "<<<CRITICAL HUMAN INTERVENTION>>>..."
    Note over Agent: Tool is aborted cleanly without breaking API schema
    Agent->>LLM: Tool Result containing Human Intervention Directive
    LLM->>Agent: Pivots plan immediately based on user directive
```

### Context Compaction (`skills/compact/SKILL.md`)
When invoked via `/compact`, the agent:
1. Synthesizes objectives, file changes, and active constraints.
2. Writes an executive snapshot into `compacted_context.md`.
3. Prunes low-value intermediate logs to recover context space while preventing amnesia.

---

## 2. Directory Structure

```text
examples/steering-and-compact/
├── hooks.json                     # Antigravity hook definition for PreToolUse & PreInvocation
├── scripts/
│   └── steer_hook.py              # Hook runner that checks the steering queue and aborts/injects
├── bin/
│   └── agy-steer                  # Command-line utility to send steering directives
├── skills/
│   └── compact/
│       └── SKILL.md               # /compact skill definition and compaction workflow
├── tests/
│   └── test_steering_hook.py      # Automated unit tests
└── README.md
```

---

## 3. How to Use in Your Workspace

### Step 1: Enable Hooks and Skills in your Project
To enable this in your current workspace, link or copy the configuration into your project's `.agents` directory:

```bash
mkdir -p .agents/scripts .agents/skills/compact
cp examples/steering-and-compact/hooks.json .agents/hooks.json
cp examples/steering-and-compact/scripts/steer_hook.py .agents/scripts/steer_hook.py
chmod +x .agents/scripts/steer_hook.py
cp examples/steering-and-compact/skills/compact/SKILL.md .agents/skills/compact/SKILL.md
```

### Step 2: In-Flight Steering
While Antigravity is running in one terminal, open another terminal (or split pane) and run:

```bash
# Send a steering instruction (applied before next step)
./bin/agy-steer "Please switch your focus to router.tsx"

# Immediately abort the currently running tool and force pivot
./bin/agy-steer --abort "Stop modifying auth.ts, look at user.ts instead"

# Check active session and pending queue
./bin/agy-steer --status
```

### Step 3: Trigger Context Compaction
In your Antigravity chat session, type:
```text
/compact
```
The agent activates the compaction skill, creating a structured context artifact and discarding ephemeral logs.

---

## 4. Running the Tests

```bash
python3 examples/steering-and-compact/tests/test_steering_hook.py
```
