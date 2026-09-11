#!/usr/bin/env python3
"""
Unit tests for the Antigravity In-Flight Steering Hook and CLI.
"""

import os
import sys
import json
import subprocess
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_SCRIPT = os.path.join(BASE_DIR, "scripts", "steer_hook.py")
CLI_SCRIPT = os.path.join(BASE_DIR, "bin", "agy-steer")
QUEUE_DIR = "/tmp/agy_steering"

class TestSteeringHook(unittest.TestCase):
    def setUp(self):
        # Clean test queues
        os.makedirs(QUEUE_DIR, exist_ok=True)
        for f in os.listdir(QUEUE_DIR):
            os.remove(os.path.join(QUEUE_DIR, f))

    def tearDown(self):
        for f in os.listdir(QUEUE_DIR):
            try:
                os.remove(os.path.join(QUEUE_DIR, f))
            except Exception:
                pass

    def run_hook(self, payload: dict) -> dict:
        proc = subprocess.run(
            [sys.executable, HOOK_SCRIPT],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            check=True
        )
        return json.loads(proc.stdout.strip())

    def test_pre_tool_use_normal(self):
        payload = {
            "conversationId": "test-session-1",
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "ls -la"}
            },
            "stepIdx": 1
        }
        res = self.run_hook(payload)
        self.assertEqual(res.get("decision"), "allow")

    def test_pre_tool_use_with_abort_steering(self):
        # 1. Send an abort steering directive via agy-steer
        subprocess.run(
            [sys.executable, CLI_SCRIPT, "--abort", "--conversation-id", "test-session-2", "Cancel and check router.tsx"],
            check=True,
            capture_output=True
        )

        # 2. Trigger PreToolUse
        payload = {
            "conversationId": "test-session-2",
            "toolCall": {
                "name": "replace_file_content",
                "args": {"TargetFile": "src/auth.ts"}
            },
            "stepIdx": 2
        }
        res = self.run_hook(payload)
        self.assertEqual(res.get("decision"), "deny")
        self.assertIn("<<<CRITICAL HUMAN INTERVENTION>>>", res.get("reason", ""))
        self.assertIn("Cancel and check router.tsx", res.get("reason", ""))

        # 3. Queue should now be cleared
        res_after = self.run_hook(payload)
        self.assertEqual(res_after.get("decision"), "allow")

    def test_pre_invocation_injection(self):
        # 1. Queue a normal steering directive (no abort)
        subprocess.run(
            [sys.executable, CLI_SCRIPT, "--conversation-id", "test-session-3", "Remember to add unit tests"],
            check=True,
            capture_output=True
        )

        # 2. Trigger PreInvocation
        payload = {
            "conversationId": "test-session-3",
            "invocationNum": 1,
            "initialNumSteps": 5
        }
        res = self.run_hook(payload)
        self.assertIn("injectSteps", res)
        self.assertEqual(len(res["injectSteps"]), 1)
        self.assertIn("Remember to add unit tests", res["injectSteps"][0]["userMessage"])

if __name__ == "__main__":
    unittest.main()
