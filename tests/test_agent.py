from types import SimpleNamespace

from app import agent as agent_module
from app.agent import TroubleshootingAgent


class FakeCompletions:
    def __init__(self) -> None:
        self.request = None

    def create(self, **request):
        self.request = request
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=(
                '{"status":"CrashLoopBackOff",'
                '"root_cause":"The container is restarting",'
                '"recommendation":"Inspect the container logs"}'
            )))]
        )


class FakeGroq:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.chat = SimpleNamespace(completions=FakeCompletions())


def test_agent_uses_groq_client_and_configured_model(monkeypatch) -> None:
    monkeypatch.setattr(agent_module, "Groq", FakeGroq)
    monkeypatch.setattr(agent_module.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(agent_module.settings, "groq_model", "test-model")
    monkeypatch.setattr(agent_module.settings, "kubernetes_enabled", False)

    troubleshooting_agent = TroubleshootingAgent()
    answer = troubleshooting_agent.investigate("Why is my pod crashing?")

    assert answer == {
        "status": "CrashLoopBackOff",
        "root_cause": "The container is restarting",
        "recommendation": "Inspect the container logs",
    }
    assert troubleshooting_agent.client.api_key == "test-key"
    request = troubleshooting_agent.client.chat.completions.request
    assert request["model"] == "test-model"
    assert request["messages"][-1] == {
        "role": "user",
        "content": "Why is my pod crashing?",
    }


def test_agent_collects_cluster_context_when_enabled(monkeypatch) -> None:
    """Test that agent collects cluster info when Kubernetes is enabled."""
    monkeypatch.setattr(agent_module, "Groq", FakeGroq)
    monkeypatch.setattr(agent_module.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(agent_module.settings, "groq_model", "test-model")
    monkeypatch.setattr(agent_module.settings, "kubernetes_enabled", True)
    monkeypatch.setattr(agent_module.settings, "kubernetes_use_local_fixtures", True)

    troubleshooting_agent = TroubleshootingAgent()
    answer = troubleshooting_agent.investigate("Why is my pod crashing?")

    assert answer["status"] == "CrashLoopBackOff"
    request = troubleshooting_agent.client.chat.completions.request
    
    # Check that the user message contains cluster context
    user_message = request["messages"][-1]
    assert user_message["role"] == "user"
    assert "ACTUAL Kubernetes Cluster Data" in user_message["content"]
    assert "checkout-api-7d8f9c6b5f-q2m4k" in user_message["content"]


def test_agent_formats_cluster_context_correctly(monkeypatch) -> None:
    """Test that cluster context is formatted properly."""
    monkeypatch.setattr(agent_module.settings, "kubernetes_enabled", True)
    monkeypatch.setattr(agent_module.settings, "kubernetes_use_local_fixtures", True)

    agent = TroubleshootingAgent()
    
    # Collect context manually
    context_dict = agent._collect_context()
    context_str = agent._format_cluster_context(context_dict)
    
    assert "[ACTUAL Kubernetes Cluster Data" in context_str
    assert "Pods" in context_str
    assert "CrashLoopBackOff" in context_str


def test_agent_uses_actual_k8s_data_not_hallucinated(monkeypatch) -> None:
    """Test that agent uses ONLY real K8s data and doesn't hallucinate.
    
    This is a critical test to ensure the agent doesn't invent pod names,
    statuses, or logs that aren't in the actual cluster context.
    """
    # Mock a real K8s cluster with specific pod data
    real_k8s_data = {
        "status": "success",
        "namespace": "test-namespace",
        "pods": [
            {
                "name": "broken-app-abc123",
                "namespace": "test-namespace",
                "status": "ImagePullBackOff",
                "restarts": 0,
                "containers": ["broken-container"],
                "ready": False,
            }
        ],
        "deployments": [],
        "services": [],
        "events": [
            {
                "kind": "Pod",
                "name": "broken-app-abc123",
                "reason": "Failed",
                "message": "Failed to pull image 'nonexistent.example.com/broken:latest'",
                "type": "Warning",
            }
        ],
    }
    
    # Mock Groq to capture the message content
    class CaptureCompletions:
        def __init__(self):
            self.captured_content = None
        
        def create(self, **request):
            self.captured_content = request["messages"][-1]["content"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content=(
                        '{"status":"ImagePullBackOff",'
                        '"root_cause":"The container image cannot be pulled",'
                        '"recommendation":"Check the image name and registry access"}'
                    )
                ))]
            )
    
    fake_completions = CaptureCompletions()
    
    class CaptureGroq:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=fake_completions)
    
    # Set up the mocks
    monkeypatch.setattr(agent_module, "Groq", CaptureGroq)
    monkeypatch.setattr(agent_module.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(agent_module.settings, "groq_model", "test-model")
    monkeypatch.setattr(agent_module.settings, "kubernetes_enabled", True)
    monkeypatch.setattr(agent_module.settings, "kubernetes_namespace", "test-namespace")
    
    # Mock the cluster collection to return real data (not local fixtures)
    monkeypatch.setattr(
        agent_module,
        "collect_cluster_snapshot",
        lambda namespace, use_local, kubeconfig_path: real_k8s_data
    )
    
    # Test the agent
    agent = TroubleshootingAgent()
    agent.investigate("Why is broken-app failing?")
    
    # Verify the agent used ONLY the real K8s data
    context_sent_to_llm = fake_completions.captured_content
    
    # MUST contain actual pod data
    assert "broken-app-abc123" in context_sent_to_llm, \
        "Agent must use actual pod name from cluster"
    assert "ImagePullBackOff" in context_sent_to_llm, \
        "Agent must use actual pod status from cluster"
    assert "test-namespace" in context_sent_to_llm, \
        "Agent must identify the correct namespace"
    
    # MUST NOT contain checkout-api (from local fixtures)
    assert "checkout-api" not in context_sent_to_llm, \
        "Agent must NOT hallucinate or use local fixture pods"
    assert "CrashLoopBackOff" not in context_sent_to_llm, \
        "Agent must NOT reference statuses from local fixtures"
    
    # Must be explicit about what was found
    assert "ACTUAL Kubernetes Cluster Data" in context_sent_to_llm, \
        "Agent must clearly indicate it's using actual cluster data"

    assert agent.investigate("Why is broken-app failing?") == {
        "status": "ImagePullBackOff",
        "root_cause": "The container image cannot be pulled",
        "recommendation": "Check the image name and registry access",
    }


def test_agent_rejects_invalid_json_response(monkeypatch) -> None:
    """Test that non-JSON model output is rejected."""
    monkeypatch.setattr(agent_module, "Groq", FakeGroq)
    monkeypatch.setattr(agent_module.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(agent_module.settings, "kubernetes_enabled", False)
    monkeypatch.setattr(
        FakeCompletions,
        "create",
        lambda self, **request: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="not JSON"))]
        ),
    )

    agent = TroubleshootingAgent()

    try:
        agent.investigate("Why is my pod failing?")
    except agent_module.LLMRequestError as exc:
        assert str(exc) == "The LLM returned invalid JSON"
    else:
        raise AssertionError("Invalid JSON must raise LLMRequestError")
