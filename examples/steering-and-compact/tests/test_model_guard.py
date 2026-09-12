#!/usr/bin/env python3
"""
Unit tests for the Model-Driven Security Guard Evaluator.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import model_security_guard

class TestModelSecurityGuard(unittest.TestCase):
    def setUp(self):
        # Clear cache before each test
        if os.path.exists(model_security_guard.CACHE_FILE):
            try:
                os.remove(model_security_guard.CACHE_FILE)
            except Exception:
                pass

    def tearDown(self):
        if os.path.exists(model_security_guard.CACHE_FILE):
            try:
                os.remove(model_security_guard.CACHE_FILE)
            except Exception:
                pass

    @patch("model_security_guard.evaluate_command_with_model")
    def test_safe_command_allows_auto_execution(self, mock_eval):
        mock_eval.return_value = {
            "safe": True,
            "reason": "Standard unit test execution in local workspace"
        }

        payload = {
            "workspacePaths": ["/Users/benhsieh/dev"],
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "npm test"}
            }
        }

        result = model_security_guard.evaluate_tool_call(payload)
        self.assertEqual(result.get("decision"), "allow")
        mock_eval.assert_called_once()

    @patch("model_security_guard.evaluate_command_with_model")
    def test_dangerous_command_prompts_user(self, mock_eval):
        mock_eval.return_value = {
            "safe": False,
            "reason": "High-risk command: Attempts to recursively wipe system root"
        }

        payload = {
            "workspacePaths": ["/Users/benhsieh/dev"],
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "rm -rf / --no-preserve-root"}
            }
        }

        result = model_security_guard.evaluate_tool_call(payload)
        self.assertEqual(result.get("decision"), "ask")
        self.assertIn("High-risk command", result.get("reason", ""))
        mock_eval.assert_called_once()

    @patch("model_security_guard.evaluate_command_with_model")
    def test_cache_prevents_repeated_llm_calls(self, mock_eval):
        mock_eval.return_value = {
            "safe": True,
            "reason": "Git diff inspection"
        }

        payload = {
            "workspacePaths": ["/Users/benhsieh/dev"],
            "toolCall": {
                "name": "run_command",
                "args": {"CommandLine": "git diff HEAD~1"}
            }
        }

        # First call hits mock LLM
        res1 = model_security_guard.evaluate_tool_call(payload)
        self.assertEqual(res1.get("decision"), "allow")
        self.assertEqual(mock_eval.call_count, 1)

        # Second identical call must hit cache, not LLM
        res2 = model_security_guard.evaluate_tool_call(payload)
        self.assertEqual(res2.get("decision"), "allow")
        self.assertEqual(mock_eval.call_count, 1)

if __name__ == "__main__":
    unittest.main()
