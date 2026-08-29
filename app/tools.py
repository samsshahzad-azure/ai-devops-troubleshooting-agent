from typing import Any, Optional

from .kubernetes import KubernetesReader


# Local fixtures keep the first version useful without requiring a cluster.
LOCAL_CLUSTER: dict[str, list[dict[str, Any]]] = {
    "pods": [
        {
            "name": "checkout-api-7d8f9c6b5f-q2m4k",
            "namespace": "default",
            "status": "CrashLoopBackOff",
            "restarts": 8,
            "containers": ["checkout-api"],
            "ready": False,
        }
    ],
    "events": [
        {
            "kind": "Pod",
            "name": "checkout-api-7d8f9c6b5f-q2m4k",
            "reason": "BackOff",
            "message": "Back-off restarting failed container checkout-api",
            "type": "Warning",
        }
    ],
    "logs": {
        "current": "Error: DATABASE_URL is not set\nFailed to connect to database",
        "previous": None,
    },
}


def get_pods(use_local: bool = True) -> list[dict[str, Any]]:
    """Get pods from local cache or Kubernetes cluster.
    
    Args:
        use_local: If True, use local fixtures; if False, use real K8s.
        
    Returns:
        List of pod information dicts.
    """
    if use_local:
        return LOCAL_CLUSTER["pods"]
    
    reader = KubernetesReader()
    if not reader.is_available():
        return []
    
    snapshot = reader.collect_namespace_snapshot()
    return snapshot.get("pods", []) if snapshot.get("status") == "success" else []


def get_events(use_local: bool = True) -> list[dict[str, Any]]:
    """Get events from local cache or Kubernetes cluster.
    
    Args:
        use_local: If True, use local fixtures; if False, use real K8s.
        
    Returns:
        List of event information dicts.
    """
    if use_local:
        return LOCAL_CLUSTER["events"]
    
    reader = KubernetesReader()
    if not reader.is_available():
        return []
    
    snapshot = reader.collect_namespace_snapshot()
    return snapshot.get("events", []) if snapshot.get("status") == "success" else []


def get_pod_logs(use_local: bool = True) -> dict[str, Any]:
    """Get pod logs from local cache or Kubernetes cluster.
    
    Args:
        use_local: If True, use local fixtures; if False, use real K8s.
        
    Returns:
        Dictionary with log information.
    """
    if use_local:
        return LOCAL_CLUSTER["logs"]
    
    reader = KubernetesReader()
    if not reader.is_available():
        return {"error": "Kubernetes not available"}
    
    # Get logs from first pod
    pods = reader.collect_namespace_snapshot().get("pods", [])
    if pods and reader.is_available():
        pod = pods[0]
        info = reader.collect_pod_info(pod["name"], pod["namespace"])
        return info.get("logs", {}) if info.get("status") == "success" else {}
    
    return {}


def collect_cluster_snapshot(
    namespace: str = "default",
    use_local: bool = True,
    kubeconfig_path: Optional[str] = None,
) -> dict[str, Any]:
    """Collect a snapshot of cluster state.
    
    Args:
        namespace: Kubernetes namespace to query.
        use_local: If True, use local fixtures; if False, use real K8s.
        kubeconfig_path: Optional path to kubeconfig file.
        
    Returns:
        Dictionary with pods, events, services, and deployments.
    """
    if use_local:
        return {
            "pods": LOCAL_CLUSTER["pods"],
            "events": LOCAL_CLUSTER["events"],
            "logs": LOCAL_CLUSTER["logs"],
        }
    
    reader = KubernetesReader(kubeconfig_path=kubeconfig_path)
    if not reader.is_available():
        return {
            "status": "unavailable",
            "error": reader.connection_error or "Kubernetes not available",
        }
    
    return reader.collect_namespace_snapshot(namespace)


def collect_pod_information(
    pod_name: str,
    namespace: str = "default",
    use_local: bool = True,
    kubeconfig_path: Optional[str] = None,
) -> dict[str, Any]:
    """Collect detailed information about a specific pod.
    
    Args:
        pod_name: Name of the pod.
        namespace: Kubernetes namespace.
        use_local: If True, use local fixtures; if False, use real K8s.
        kubeconfig_path: Optional path to kubeconfig file.
        
    Returns:
        Dictionary with pod information and logs.
    """
    if use_local:
        return {
            "pod": LOCAL_CLUSTER["pods"][0] if LOCAL_CLUSTER["pods"] else {},
            "logs": LOCAL_CLUSTER["logs"],
        }
    
    reader = KubernetesReader(kubeconfig_path=kubeconfig_path)
    return reader.collect_pod_info(pod_name, namespace)


def collect_pod_logs(
    pod_name: str,
    namespace: str = "default",
    container: Optional[str] = None,
    use_local: bool = True,
    kubeconfig_path: Optional[str] = None,
) -> dict[str, Any]:
    """Collect logs for one named pod through the read-only provider."""
    if use_local:
        pod = next(
            (pod for pod in LOCAL_CLUSTER["pods"] if pod["name"] == pod_name),
            None,
        )
        return {
            "status": "success" if pod else "not_found",
            "pod_name": pod_name,
            "namespace": namespace,
            "logs": LOCAL_CLUSTER["logs"] if pod else {},
        }

    info = collect_pod_information(
        pod_name=pod_name,
        namespace=namespace,
        use_local=False,
        kubeconfig_path=kubeconfig_path,
    )
    return {
        "status": info.get("status", "error"),
        "pod_name": pod_name,
        "namespace": namespace,
        "logs": info.get("logs", {}),
        "error": info.get("error"),
    }


def collect_pod_events(
    pod_name: str,
    namespace: str = "default",
    use_local: bool = True,
    kubeconfig_path: Optional[str] = None,
) -> dict[str, Any]:
    """Collect events for one named pod through the read-only provider."""
    snapshot = collect_cluster_snapshot(
        namespace=namespace,
        use_local=use_local,
        kubeconfig_path=kubeconfig_path,
    )
    if snapshot.get("status") in {"unavailable", "error"}:
        return snapshot
    events = [event for event in snapshot.get("events", []) if event.get("name") == pod_name]
    return {"status": "success", "namespace": namespace, "pod_name": pod_name, "events": events}


def collect_deployment_information(
    deployment_name: str,
    namespace: str = "default",
    use_local: bool = True,
    kubeconfig_path: Optional[str] = None,
) -> dict[str, Any]:
    """Collect one deployment from a namespace snapshot."""
    snapshot = collect_cluster_snapshot(namespace, use_local, kubeconfig_path)
    if snapshot.get("status") in {"unavailable", "error"}:
        return snapshot
    deployment = next(
        (item for item in snapshot.get("deployments", []) if item.get("name") == deployment_name),
        None,
    )
    return {
        "status": "success" if deployment else "not_found",
        "namespace": namespace,
        "deployment": deployment,
    }


def collect_service_information(
    service_name: str,
    namespace: str = "default",
    use_local: bool = True,
    kubeconfig_path: Optional[str] = None,
) -> dict[str, Any]:
    """Collect one service from a namespace snapshot."""
    snapshot = collect_cluster_snapshot(namespace, use_local, kubeconfig_path)
    if snapshot.get("status") in {"unavailable", "error"}:
        return snapshot
    service = next(
        (item for item in snapshot.get("services", []) if item.get("name") == service_name),
        None,
    )
    return {
        "status": "success" if service else "not_found",
        "namespace": namespace,
        "service": service,
    }

