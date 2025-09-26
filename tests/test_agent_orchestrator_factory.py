import pytest

from app.services.agent_orchestrator import (
    get_agent_orchestrator,
    ClaudeCodeAgentOrchestrator,
    CodeXAgentOrchestrator,
    GeminiCLIAgentOrchestrator,
)


@pytest.mark.parametrize(
    "alias, expected",
    [
        (None, ClaudeCodeAgentOrchestrator),
        ("claude", ClaudeCodeAgentOrchestrator),
        ("codex", CodeXAgentOrchestrator),
        ("code_x", CodeXAgentOrchestrator),
        ("gemini", GeminiCLIAgentOrchestrator),
        ("gemini_cli", GeminiCLIAgentOrchestrator),
    ],
)
def test_get_agent_orchestrator(alias, expected):
    orchestrator = get_agent_orchestrator(alias)
    assert isinstance(orchestrator, expected)
