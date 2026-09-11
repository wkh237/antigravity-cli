#!/usr/bin/env python3
"""
Antigravity Lifecycle Hook for In-Flight Steering via Tool Response Hijacking
Implements PreToolUse and PreInvocation hooks according to the Antigravity Hook Spec.
"""

import sys
import os
import json
import glob

QUEUE_DIR = "/tmp/agy_steering"
os.makedirs(QUEUE_DIR, exist_ok=True)

def get_queue_file(conversation_id: str) -> str:
    return os.path.join(QUEUE_DIR, f"{conversation_id}.json")

def get_latest_queue_file() -> str:
    return os.path.join(QUEUE_DIR, "latest.json")

def read_pending_steering(conversation_id: str):
    """
    Check if there is a pending steering command for this conversation.
    Falls back to latest.json if conversation-specific file is not present.
    """
    for path in [get_queue_file(conversation_id), get_latest_queue_file()]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data, path
            except Exception:
                continue
    return None, None

def clear_pending_steering(conversation_id: str):
    """Remove or clear the consumed steering messages."""
    for path in [get_queue_file(conversation_id), get_latest_queue_file()]:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            sys.stderr.write(f"Failed to remove steering queue {path}: {e}\n")

def handle_pre_tool_use(payload: dict):
    conversation_id = payload.get("conversationId", "default")
    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name", "unknown")

    steering, queue_path = read_pending_steering(conversation_id)

    # Check if user requested an immediate in-flight abort
    if steering and steering.get("abort_tool", False):
        directive = steering.get("directive", "").strip()
        clear_pending_steering(conversation_id)

        reason = (
            f"<<<CRITICAL HUMAN INTERVENTION>>>\n"
            f"[STATUS: TOOL EXECUTION ABORTED BY USER]\n"
            f"Interrupted Tool: {tool_name}\n"
            f"User Steering Directive: \"{directive}\"\n"
            f"Action Required: Immediately abort current plan, acknowledge this directive, and adjust your next steps.\n"
            f"<<<END INTERVENTION>>>"
        )
        print(json.dumps({
            "decision": "deny",
            "reason": reason
        }))
        return

    # If steering is queued without aborting the current tool, allow tool to finish.
    # It will be picked up at PreInvocation or appended to PostToolUse.
    print(json.dumps({
        "decision": "allow"
    }))

def handle_pre_invocation(payload: dict):
    conversation_id = payload.get("conversationId", "default")
    steering, queue_path = read_pending_steering(conversation_id)

    if steering:
        directive = steering.get("directive", "").strip()
        clear_pending_steering(conversation_id)

        msg = (
            f"<<<CRITICAL HUMAN INTERVENTION>>>\n"
            f"User Steering Directive: \"{directive}\"\n"
            f"Action Required: Prioritize this directive above prior internal plans and revise your actions immediately.\n"
            f"<<<END INTERVENTION>>>"
        )
        print(json.dumps({
            "injectSteps": [
                {
                    "userMessage": msg
                }
            ]
        }))
        return

    print(json.dumps({}))

def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({}))
            return

        payload = json.loads(raw_input)
    except Exception as e:
        sys.stderr.write(f"Error parsing stdin in steer_hook: {e}\n")
        print(json.dumps({}))
        return

    # Update latest active conversation pointer
    conv_id = payload.get("conversationId")
    if conv_id:
        active_meta_path = os.path.join(QUEUE_DIR, "active_session.txt")
        try:
            with open(active_meta_path, "w", encoding="utf-8") as f:
                f.write(conv_id)
        except Exception:
            pass

    # Check whether this is PreToolUse or PreInvocation based on payload keys
    if "toolCall" in payload:
        handle_pre_tool_use(payload)
    elif "invocationNum" in payload:
        handle_pre_invocation(payload)
    else:
        # Default empty response
        print(json.dumps({}))

if __name__ == "__main__":
    main()
