# RFC-0001: In-Flight Agent Steering via Tool Response Hijacking & Explicit Context Compaction

- **Status**: Draft / Proposal
- **Author**: @wkh237
- **Target Component**: Agent Core Engine, CLI TUI, Context Lifecycle Manager
- **Related Issues**:
  - Steering: [#249](https://github.com/google-antigravity/antigravity-cli/issues/249), [#896](https://github.com/google-antigravity/antigravity-cli/issues/896)
  - Compaction: [#495](https://github.com/google-antigravity/antigravity-cli/issues/495), [#878](https://github.com/google-antigravity/antigravity-cli/issues/878), [#919](https://github.com/google-antigravity/antigravity-cli/issues/919)

---

## 1. Executive Summary

As multi-step agentic workflows grow increasingly complex, two critical pain points emerge in Antigravity CLI (`agy`):
1. **Lack of Mid-Flight Steering**: When an agent begins executing sub-optimal tool calls during a long multi-step turn, users must either wait until the entire turn finishes (wasting tokens and latency) or press `Escape` (hard-aborting execution and discarding intermediate context).
2. **Aggressive or Uncontrollable Context Compaction**: Sessions either trigger premature lossy auto-compaction around ~140k tokens (inducing model amnesia), or accumulate unbounded tool schemas and outputs until encountering gateway `HTTP 400 INVALID_ARGUMENT` trajectory errors.

This RFC proposes two architectural solutions:
- **In-Flight Steering via Tool Response Hijacking**: Inject human steering directives directly into the `tool_response` payload rather than restructuring dialogue turn roles, preserving strict API function-calling schema constraints while enabling immediate mid-chain course corrections.
- **Manual `/compact` Macro & Compaction Control**: Expose an explicit `/compact` command, provide configurable auto-compaction thresholds, and utilize artifact-based context anchoring to retain critical session invariants.

---

## 2. Proposal 1: In-Flight Steering via Tool Response Hijacking

### 2.1 The Problem
In standard Function Calling protocols (Gemini / OpenAI), a strict schema invariance must be maintained:
```
Turn N:   Model -> Function Call (call_id)
Turn N+1: Tool  -> Function Response (call_id)
```
If a human user submits an instruction mid-flight:
- Injecting a `UserMessage` immediately after `Function Call` violates the gateway protocol schema and triggers `400 Bad Request`.
- Waiting until the end of the multi-step turn prevents timely intervention when the model takes a wrong path during early steps.
- Hard-killing via `Escape` cancels all ongoing work, leaving file changes half-applied and destroying working state.

### 2.2 The Solution: Hijack Tool Response Payload
Instead of modifying message turns, the CLI / agent harness intercepts the next pending or running `tool_response`.

#### Scenario A: Tool is Currently Executing (In-Flight Cancel & Steer)
1. User types instruction into the active prompt and hits `Enter` (or triggers a dedicated steering keybinding).
2. The agent harness terminates the running child process / tool execution cleanly.
3. The tool result is synthesized and returned to the model immediately:

```json
{
  "role": "tool",
  "tool_call_id": "call_view_file_8912",
  "content": "<<<CRITICAL HUMAN INTERVENTION>>>\n[STATUS: TOOL EXECUTION ABORTED BY USER]\nUser Steering Directive: \"Stop inspecting authentication files. The issue is in the frontend router config (src/router.tsx). Please redirect your plan immediately.\"\n<<<END INTERVENTION>>>"
}
```

#### Scenario B: Tool Already Finished (Append to Completed Tool Output)
If the tool finishes before the user intervention was queued, the harness appends the steering block to the legitimate output before invoking the next LLM inference step:

```json
{
  "role": "tool",
  "tool_call_id": "call_run_command_1042",
  "content": "Test suite passed: 14 tests, 0 failures.\n\n<<<CRITICAL HUMAN INTERVENTION>>>\nUser Steering Directive: \"Great, now please do not commit yet. Refactor the helper function in utils.ts first.\"\n<<<END INTERVENTION>>>"
}
```

### 2.3 System Prompt Enforcement
To ensure the LLM respects the hijacked tool response with maximum authority, the base agent instructions include:
```markdown
## Human Steering Interception
If any `tool_response` contains a `<<<CRITICAL HUMAN INTERVENTION>>>` block:
1. Recognize that the human operator has intercepted the execution flow.
2. Prioritize the user directive within the block above all prior internal plans.
3. Acknowledge the directive in your subsequent thought step and immediately adjust your action plan.
```

### 2.4 Advantages
- **100% Protocol Compliant**: No schema changes, no unexpected `role: user` interleaving between function calls and responses.
- **Zero Cache Penalty**: Does not alter historical prefix caches, maximizing prompt cache hit rates.
- **High Attention Weight**: Positioned directly at the tail of the context window, taking advantage of LLM recency bias.

---

## 3. Proposal 2: Explicit Context Compaction & Control

### 3.1 The Problem
- **Auto-Compaction Amnesia**: As documented in #878, automated server-side compaction wipes out fine-grained file context, leading to repetitive file re-reading loops.
- **Trajectory Bloat**: Long sessions accumulate massive `run_command` outputs and schema overhead, causing gateway failures (#919).

### 3.2 The Solution: `/compact` Macro & Configurable Thresholds

1. **Explicit `/compact` Command**:
   - Provide a user-facing `/compact [focus_topic]` command.
   - When executed, the agent generates an executive summary anchored on active artifacts (`.system_generated/artifacts/`) and task lists.
   - Flushes ephemeral intermediate tool outputs (e.g. verbose linter warnings, grep dumps) while preserving:
     - Modified file diff summaries.
     - Active subagent and task registry states.
     - User constraints and active architectural guidelines.

2. **Configurable Auto-Compaction Settings**:
   Add controls to `settings.json`:
   ```json
   {
     "context": {
       "enable_auto_compaction": false,
       "compaction_threshold_percent": 85,
       "preserve_artifacts_in_summary": true
     }
   }
   ```

3. **Statusline Context Meter**:
   Expose `context_used_tokens`, `context_max_tokens`, and `context_percent` in the statusline API so users always have visibility before limits are approached.

---

## 4. Implementation Roadmap

| Phase | Milestone | Scope |
| :--- | :--- | :--- |
| **Phase 1** | Inter-tool Event Queue | Enable terminal input capture to buffer human messages between tool calls. |
| **Phase 2** | Tool Response Interception | Implement tool payload hijacking with `<<<CRITICAL HUMAN INTERVENTION>>>` wrapper. |
| **Phase 3** | `/compact` & Context API | Expose manual compaction command and add context status variables to statusline. |
| **Phase 4** | Configurable Limits | Expose auto-compaction toggle in CLI settings. |

---

## 5. Feedback & Community Discussion

Please share your thoughts on this RFC:
- Does hijacking the `tool_response` channel handle all your expected interactive steering workflows?
- What metadata should be strictly preserved during `/compact` runs?
