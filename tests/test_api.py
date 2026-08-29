from fastapi.testclient import TestClient

from app.agent import LLMConfigurationError, LLMRequestError
from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_troubleshoot_returns_llm_answer(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.agent.investigate",
        lambda question: {
            "status": "Running",
            "root_cause": "No failure detected",
            "recommendation": "No action is required",
        },
    )
    response = client.post(
        "/troubleshoot",
        json={"question": "Why is my Kubernetes pod crashing?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "question": "Why is my Kubernetes pod crashing?",
        "status": "Running",
        "root_cause": "No failure detected",
        "recommendation": "No action is required",
    }


def test_troubleshoot_returns_503_when_key_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.agent.investigate",
        lambda question: (_ for _ in ()).throw(
            LLMConfigurationError("GROQ_API_KEY is not configured")
        ),
    )

    response = client.post("/troubleshoot", json={"question": "Why is my pod crashing?"})

    assert response.status_code == 503
    assert response.json() == {"detail": "GROQ_API_KEY is not configured"}


def test_troubleshoot_returns_502_when_llm_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.agent.investigate",
        lambda question: (_ for _ in ()).throw(LLMRequestError("The LLM request failed")),
    )

    response = client.post("/troubleshoot", json={"question": "Why is my pod crashing?"})

    assert response.status_code == 502
    assert response.json() == {"detail": "The LLM request failed"}


def test_get_config_endpoint() -> None:
    """Test the /config endpoint returns configuration."""
    response = client.get("/config")

    assert response.status_code == 200
    config = response.json()
    assert "kubernetes_enabled" in config
    assert "kubernetes_namespace" in config
    assert "kubernetes_use_local_fixtures" in config


def test_cluster_info_endpoint_with_local_fixtures() -> None:
    """Test the /cluster-info endpoint with local fixtures."""
    response = client.get("/cluster-info?use_local=true")

    assert response.status_code == 200
    cluster_info = response.json()
    assert "pods" in cluster_info
    assert "events" in cluster_info
    assert len(cluster_info["pods"]) > 0


def test_pod_info_endpoint_with_local_fixtures() -> None:
    """Test the /pod-info endpoint with local fixtures."""
    response = client.get(
        "/pod-info?pod_name=checkout-api-7d8f9c6b5f-q2m4k&use_local=true"
    )

    assert response.status_code == 200
    pod_info = response.json()
    assert "pod" in pod_info
    assert "logs" in pod_info


def test_troubleshoot_with_kubernetes_enabled(monkeypatch) -> None:
    """Test troubleshoot endpoint with Kubernetes integration enabled."""
    monkeypatch.setattr(
        "app.main.agent.investigate",
        lambda question: {
            "status": "CrashLoopBackOff",
            "root_cause": "The container is restarting",
            "recommendation": "Inspect the container logs",
        },
    )
    response = client.post(
        "/troubleshoot",
        json={
            "question": "Why is my pod crashing?",
            "enable_kubernetes": False,  # Use local fixtures
            "namespace": "default",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["question"] == "Why is my pod crashing?"
    assert result["status"] == "CrashLoopBackOff"
    assert result["root_cause"] == "The container is restarting"
    assert result["recommendation"] == "Inspect the container logs"


def test_troubleshoot_disables_local_fixtures_when_kubernetes_enabled(monkeypatch) -> None:
    """Test that enable_kubernetes=True disables local fixtures.
    
    This critical test ensures that when the user requests real K8s data,
    the endpoint actually uses it instead of falling back to local fixtures.
    """
    import app.main as main_module
    
    # Track what settings are used during investigation
    settings_used = {}
    
    def capture_investigate(question):
        """Mock investigate that captures the settings used."""
        settings_used["kubernetes_enabled"] = main_module.settings.kubernetes_enabled
        settings_used["kubernetes_use_local_fixtures"] = main_module.settings.kubernetes_use_local_fixtures
        settings_used["kubernetes_namespace"] = main_module.settings.kubernetes_namespace
        return {
            "status": "ImagePullBackOff",
            "root_cause": "The container image cannot be pulled",
            "recommendation": "Check the image name",
        }
    
    monkeypatch.setattr("app.main.agent.investigate", capture_investigate)
    
    # Make request with enable_kubernetes=True
    response = client.post(
        "/troubleshoot",
        json={
            "question": "What's happening in ai-agent-test namespace?",
            "enable_kubernetes": True,
            "namespace": "ai-agent-test",
        },
    )
    
    assert response.status_code == 200
    
    # Verify that the settings were correctly set to use REAL K8s
    assert settings_used["kubernetes_enabled"] is True, \
        "kubernetes_enabled must be True when enable_kubernetes=True"
    assert settings_used["kubernetes_use_local_fixtures"] is False, \
        "kubernetes_use_local_fixtures must be False to use real K8s data"
    assert settings_used["kubernetes_namespace"] == "ai-agent-test", \
        "Namespace must be set correctly"
