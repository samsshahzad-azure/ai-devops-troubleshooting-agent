from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .agent import LLMConfigurationError, LLMRequestError, agent
from .config import settings
from .tools import collect_cluster_snapshot, collect_pod_information

app = FastAPI(title="AI DevOps Troubleshooting Agent", version="0.1.0")


class TroubleshootRequest(BaseModel):
    question: str
    namespace: str = "default"
    enable_kubernetes: bool = False


class ConfigResponse(BaseModel):
    kubernetes_enabled: bool
    kubernetes_namespace: str
    kubernetes_use_local_fixtures: bool
    kubernetes_available: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config")
def get_config() -> ConfigResponse:
    """Get current agent configuration."""
    return ConfigResponse(
        kubernetes_enabled=settings.kubernetes_enabled,
        kubernetes_namespace=settings.kubernetes_namespace,
        kubernetes_use_local_fixtures=settings.kubernetes_use_local_fixtures,
    )


@app.post("/troubleshoot")
def troubleshoot(request: TroubleshootRequest) -> dict:
    """Troubleshoot a Kubernetes issue.
    
    Args:
        request: TroubleshootRequest with question and optional K8s settings.
        
    Returns:
        Dictionary with question and LLM analysis answer.
    """
    # Temporarily enable Kubernetes if requested
    original_enabled = settings.kubernetes_enabled
    original_namespace = settings.kubernetes_namespace
    original_use_local = settings.kubernetes_use_local_fixtures
    
    try:
        if request.enable_kubernetes:
            settings.kubernetes_enabled = True
            settings.kubernetes_namespace = request.namespace
            settings.kubernetes_use_local_fixtures = False  # Use REAL K8s data
        
        answer = agent.investigate(request.question)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        # Restore original settings
        settings.kubernetes_enabled = original_enabled
        settings.kubernetes_namespace = original_namespace
        settings.kubernetes_use_local_fixtures = original_use_local

    return {"question": request.question, **answer}


@app.get("/cluster-info")
def get_cluster_info(namespace: str = "default", use_local: bool = True) -> dict:
    """Get cluster snapshot information.
    
    Args:
        namespace: Kubernetes namespace to query.
        use_local: Whether to use local fixtures or real K8s.
        
    Returns:
        Dictionary with cluster state snapshot.
    """
    return collect_cluster_snapshot(namespace=namespace, use_local=use_local)


@app.get("/pod-info")
def get_pod_info(
    pod_name: str, namespace: str = "default", use_local: bool = True
) -> dict:
    """Get detailed pod information.
    
    Args:
        pod_name: Name of the pod.
        namespace: Kubernetes namespace.
        use_local: Whether to use local fixtures or real K8s.
        
    Returns:
        Dictionary with pod details and logs.
    """
    return collect_pod_information(
        pod_name=pod_name,
        namespace=namespace,
        use_local=use_local,
    )
