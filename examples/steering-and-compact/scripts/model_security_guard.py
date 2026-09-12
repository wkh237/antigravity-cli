#!/usr/bin/env python3
"""
Model-Driven Auto-Approval Security Guard for Antigravity CLI.
Evaluates commands using a fast, lightweight evaluator model (Gemini Flash / Claude Haiku / GPT-4o-mini / Ollama)
to dynamically decide whether to auto-allow or prompt the user for confirmation.
No static regex whitelists required.
"""

import sys
import os
import json
import urllib.request
import urllib.error
import hashlib
import subprocess

CACHE_FILE = "/tmp/agy_steering/model_guard_cache.json"

EVAL_PROMPT_TEMPLATE = """You are an automated security evaluator for a software developer's terminal commands.
Workspace: {workspace}
Tool: {tool_name}
Command: {command}

Analyze the command and determine whether it is safe to execute automatically without manual confirmation.
Criteria:
- Safe (true): Standard development activities, building, testing, linting, inspecting files, harmless git operations, package installations within workspace, cleaning workspace build artifacts.
- Unsafe / Risky (false): Deleting source code outside build dirs, modifying root/system files, accessing ssh/cloud secrets (~/.ssh, ~/.aws, environment variables with secrets), data exfiltration, dropping production databases, force pushing to remote git branches.

Respond strictly with a JSON object in this format (no markdown, no extra text):
{{"safe": true, "reason": "concise explanation of safety or risk"}}"""


def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def call_gemini_api(prompt: str, api_key: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.0
        }
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        text = res["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)


def call_openai_api(prompt: str, api_key: str) -> dict:
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.0
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        text = res["choices"][0]["message"]["content"]
        return json.loads(text)


def call_anthropic_api(prompt: str, api_key: str) -> dict:
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 150,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}]
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        text = res["content"][0]["text"]
        # extract json block
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])


def call_ollama(prompt: str, host: str) -> dict:
    url = f"{host.rstrip('/')}/api/generate"
    payload = {
        "model": "qwen2.5-coder:1.5b",
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return json.loads(res["response"])


def call_agy_print_fallback(prompt: str) -> dict:
    """Fallback using native agy --print with low tier model"""
    proc = subprocess.run(
        ["agy", "--model", "Gemini 3.8 Flash (Low)", f"--print={prompt}"],
        capture_output=True,
        text=True,
        timeout=15
    )
    text = proc.stdout.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])
    raise ValueError(f"Failed to parse JSON from agy --print: {text}")


def evaluate_command_with_model(command: str, tool_name: str, workspace: str) -> dict:
    prompt = EVAL_PROMPT_TEMPLATE.format(
        workspace=workspace,
        tool_name=tool_name,
        command=command
    )

    # 1. Check Gemini API key
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        try:
            return call_gemini_api(prompt, gemini_key)
        except Exception as e:
            sys.stderr.write(f"Gemini API review error: {e}\n")

    # 2. Check Anthropic API key
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            return call_anthropic_api(prompt, anthropic_key)
        except Exception as e:
            sys.stderr.write(f"Anthropic API review error: {e}\n")

    # 3. Check OpenAI API key
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            return call_openai_api(prompt, openai_key)
        except Exception as e:
            sys.stderr.write(f"OpenAI API review error: {e}\n")

    # 4. Check Local Ollama (only if explicitly enabled or host specified)
    if os.environ.get("OLLAMA_HOST") or os.environ.get("USE_OLLAMA"):
        ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        try:
            return call_ollama(prompt, ollama_host)
        except Exception:
            pass

    # If no fast model API key is configured, return safe to avoid blocking terminal
    return {"safe": True, "reason": "No evaluator API key set (GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY). Auto-allowing."}


def evaluate_tool_call(payload: dict) -> dict:
    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name", "unknown")
    args = tool_call.get("args", {})
    workspace = (payload.get("workspacePaths") or ["."])[0]

    command = args.get("CommandLine") or args.get("command") or str(args)

    # Cache lookup by command hash
    cache_key = hashlib.sha256(f"{workspace}:{tool_name}:{command}".encode("utf-8")).hexdigest()
    cache = load_cache()
    if cache_key in cache:
        cached_res = cache[cache_key]
        if cached_res.get("safe", False):
            return {"decision": "allow"}
        else:
            return {
                "decision": "ask",
                "reason": f"[AI Model Review (Cached)] {cached_res.get('reason', 'Potentially destructive command')}"
            }

    # Query reviewer model
    eval_result = evaluate_command_with_model(command, tool_name, workspace)

    # Save to cache
    cache[cache_key] = eval_result
    save_cache(cache)

    if eval_result.get("safe", False):
        return {"decision": "allow"}
    else:
        reason = eval_result.get("reason", "Potentially destructive or high-risk command")
        return {
            "decision": "ask",
            "reason": f"[AI Model Review] {reason}"
        }


def main():
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"decision": "allow"}))
            return
        payload = json.loads(raw_input)
    except Exception as e:
        sys.stderr.write(f"Error parsing stdin: {e}\n")
        print(json.dumps({"decision": "allow"}))
        return

    result = evaluate_tool_call(payload)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
