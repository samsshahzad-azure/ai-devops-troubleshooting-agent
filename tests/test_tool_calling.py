import json
from types import SimpleNamespace

import pytest

from app import agent as agent_module
from app.agent import LLMRequestError, TroubleshootingAgent
from app.tool_registry import TOOL_DEFINITIONS


def tool_call(name: str, arguments: dict[str, str], call_id: str = "call-1"):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


class SequencedCompletions:
    def __init__(self, messages):
        self.messages = messages
        self.requests = []

    def create(self, **request):
        self.requests.append(request)
        return self.messages[len(self.requests) - 1]


class SequencedGroq:
    completions = None

    def __init__(self, api_key: str):
        self.chat = SimpleNamespace(completions=self.completions)


def configure_agent(monkeypatch, completions, namespace="ai-agent-test"):
    SequencedGroq.completions = completions
    monkeypatch.setattr(agent_module, "Groq", SequencedGroq)
    monkeypatch.setattr(agent_module.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(agent_module.settings, "groq_model", "test-model")
    monkeypatch.setattr(agent_module.settings, "kubernetes_enabled", True)
    monkeypatch.setattr(agent_module.settings, "kubernetes_namespace", namespace)
    monkeypatch.setattr(agent_module.settings, "kubernetes_use_local_fixtures", False)


def final_message(status="ImagePullBackOff"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
            "status": status,
            "root_cause": "The container image cannot be pulled",
            "recommendation": "Check the image name and registry access",
        })))]
    )


def test_groq_receives_tools_and_tool_result_is_appended(monkeypatch):
    completions = SequencedCompletions([
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call(
                "get_namespace_snapshot",
                {"namespace": "ai-agent-test"},
            )],
        ))]),
        final_message(),
    ])
    configure_agent(monkeypatch, completions)
    snapshot = {
        "status": "success",
        "namespace": "ai-agent-test",
        "pods": [{"name": "broken-app-abc123", "status": "ImagePullBackOff"}],
        "deployments": [],
        "services": [],
        "events": [],
    }
    monkeypatch.setattr(agent_module, "collect_cluster_snapshot", lambda **kwargs: snapshot)

    answer = TroubleshootingAgent().investigate("Why is broken-app failing?")

    assert answer["status"] == "ImagePullBackOff"
    first_request = completions.requests[0]
    assert {tool["function"]["name"] for tool in first_request["tools"]} == {
        "get_namespace_snapshot",
        "get_pod_information",
        "get_pod_logs",
        "get_pod_events",
        "get_deployment_information",
        "get_service_information",
        "submit_diagnosis",
    }
    second_messages = completions.requests[1]["messages"]
    assert second_messages[-1]["role"] == "tool"
    assert "ImagePullBackOff" in second_messages[-1]["content"]
    assert second_messages[-1]["tool_call_id"] == "call-1"


def test_tool_call_passes_requested_namespace(monkeypatch):
    completions = SequencedCompletions([
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call("get_pod_information", {
                "pod_name": "broken-app-abc123",
                "namespace": "ai-agent-test",
            })],
        ))]),
        final_message(),
    ])
    configure_agent(monkeypatch, completions)
    calls = []
    monkeypatch.setattr(
        agent_module,
        "collect_pod_information",
        lambda **kwargs: calls.append(kwargs) or {"status": "success", "pod": {}, "logs": {}},
    )

    TroubleshootingAgent().investigate("Inspect broken-app")

    assert calls[0]["namespace"] == "ai-agent-test"
    assert calls[0]["pod_name"] == "broken-app-abc123"


def test_tool_call_rejects_unknown_tool(monkeypatch):
    configure_agent(monkeypatch, SequencedCompletions([]))
    agent = TroubleshootingAgent()

    with pytest.raises(LLMRequestError, match="invalid tool arguments"):
        agent._execute_tool_call(tool_call("delete_pod", {"namespace": "ai-agent-test"}))


def test_tool_call_rejects_invalid_arguments(monkeypatch):
    configure_agent(monkeypatch, SequencedCompletions([]))
    agent = TroubleshootingAgent()

    with pytest.raises(LLMRequestError, match="invalid tool arguments"):
        agent._execute_tool_call(tool_call("get_namespace_snapshot", {}))


def test_tool_calls_are_bounded(monkeypatch):
    repeated_tool = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=None,
        tool_calls=[tool_call("get_namespace_snapshot", {"namespace": "ai-agent-test"})],
    ))])
    completions = SequencedCompletions([repeated_tool] * 6)
    configure_agent(monkeypatch, completions)
    monkeypatch.setattr(
        agent_module,
        "collect_cluster_snapshot",
        lambda **kwargs: {"status": "success", "namespace": "ai-agent-test", "pods": []},
    )

    with pytest.raises(LLMRequestError, match="maximum number of tool calls"):
        TroubleshootingAgent().investigate("Inspect the namespace")

    assert len(completions.requests) == agent_module.MAX_TOOL_CALLS + 1


def test_namespace_mismatch_is_rejected(monkeypatch):
    configure_agent(monkeypatch, SequencedCompletions([]))
    agent = TroubleshootingAgent()

    with pytest.raises(LLMRequestError, match="different Kubernetes namespace"):
        agent._execute_tool_call(tool_call(
            "get_namespace_snapshot", {"namespace": "default"}
        ))


def test_valid_submit_diagnosis_is_accepted(monkeypatch):
    configure_agent(monkeypatch, SequencedCompletions([]))

    result = TroubleshootingAgent()._execute_tool_call(tool_call(
        "submit_diagnosis",
        {
            "status": "ImagePullBackOff",
            "root_cause": "The container image cannot be pulled",
            "recommendation": "Check the image name and registry access",
        },
    ))

    assert result == {
        "status": "ImagePullBackOff",
        "root_cause": "The container image cannot be pulled",
        "recommendation": "Check the image name and registry access",
    }


def test_submit_diagnosis_rejects_missing_or_invalid_fields(monkeypatch):
    configure_agent(monkeypatch, SequencedCompletions([]))
    agent = TroubleshootingAgent()

    with pytest.raises(LLMRequestError, match="invalid tool arguments"):
        agent._execute_tool_call(tool_call(
            "submit_diagnosis",
            {"status": "ImagePullBackOff", "root_cause": "Missing recommendation"},
        ))

    with pytest.raises(LLMRequestError, match="invalid tool arguments"):
        agent._execute_tool_call(tool_call(
            "submit_diagnosis",
            {
                "status": "ImagePullBackOff",
                "root_cause": "The image cannot be pulled",
                "recommendation": 123,
            },
        ))


def test_submit_diagnosis_is_terminal_and_preserves_api_fields(monkeypatch):
    completions = SequencedCompletions([
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content=None,
            tool_calls=[tool_call("submit_diagnosis", {
                "status": "ImagePullBackOff",
                "root_cause": "The container image cannot be pulled",
                "recommendation": "Check the image name and registry access",
            })],
        ))]),
    ])
    configure_agent(monkeypatch, completions)

    assert TroubleshootingAgent().investigate("Why is broken-app failing?") == {
        "status": "ImagePullBackOff",
        "root_cause": "The container image cannot be pulled",
        "recommendation": "Check the image name and registry access",
    }
    assert len(completions.requests) == 1


def test_registry_contains_only_read_tools():
    names = {tool["function"]["name"] for tool in TOOL_DEFINITIONS}
    forbidden_terms = {
        "create", "update", "patch", "delete", "scale", "restart", "exec", "port_forward",
    }
    assert all(not any(term in name for term in forbidden_terms) for name in names)
    assert names == {
        "get_namespace_snapshot",
        "get_pod_information",
        "get_pod_logs",
        "get_pod_events",
        "get_deployment_information",
        "get_service_information",
        "submit_diagnosis",
    }