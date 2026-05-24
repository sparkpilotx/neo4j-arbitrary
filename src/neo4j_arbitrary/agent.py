"""Agent detection utilities."""

import os

_AGENT_VARS: list[tuple[str, str]] = [
    ("CLAUDE_CODE_IS_COWORK", "cowork"),
    ("CLAUDEDECODE", "claude-code"),
    ("CLAUDE_CODE", "claude-code"),
    ("CODEX_SANDBOX", "codex"),
    ("CODEX_CI", "codex"),
    ("CODEX_THREAD_ID", "codex"),
    ("CLINE_ACTIVE", "cline"),
    ("CURSOR_TRACE_ID", "cursor"),
    ("GEMINI_CLI", "gemini"),
    ("COPILOT_MODEL", "github-copilot"),
    ("GOOSE_TERMINAL", "goose"),
    ("REPL_ID", "replit"),
    ("PI_CODING_AGENT", "pi"),
    ("TRAE_AI_SHELL_ID", "trae"),
    ("OPENCLAW_SHELL", "openclaw"),
    ("OPENCODE_CLIENT", "opencode"),
    ("ROO_ACTIVE", "roo-code"),
    ("AUGMENT_AGENT", "augment-cli"),
    ("ANTIGRAVITY_AGENT", "antigravity"),
]

_KNOWN_AGENTS: frozenset[str] = frozenset(name for _, name in _AGENT_VARS)


def detect_agent() -> str | None:
    for var, name in _AGENT_VARS:
        if os.environ.get(var):
            return name
    for var in ("AI_AGENT", "AGENT"):
        if val := os.environ.get(var):
            return val if val in _KNOWN_AGENTS else "unknown"
    return None


def is_agent() -> bool:
    return detect_agent() is not None
