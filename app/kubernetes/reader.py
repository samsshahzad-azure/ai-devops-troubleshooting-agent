"""Kubernetes data reader - collects cluster information for analysis."""

from typing import Any, Optional

from .client import KubernetesClient, KubernetesConnectionError


class KubernetesReader:
    """Reads Kubernetes cluster data for troubleshooting analysis."""

    def __init__(self, kubeconfig_path: Optional[str] = None) -> None:
        """Initialize the Kubernetes reader.
        
        Args:
            kubeconfig_path: Optional path to kubeconfig file.
        """
        self.client: Optional[KubernetesClient] = None
        self.connection_error: Optional[str] = None
        
        try:
            self.client = KubernetesClient(kubeconfig_path=kubeconfig_path)
        except KubernetesConnectionError as exc:
            self.connection_error = str(exc)

    def is_available(self) -> bool:
        """Check if Kubernetes cluster is available."""
        return self.client is not None and self.client.is_connected

    def collect_pod_info(
        self, pod_name: str, namespace: str = "default"
    ) -> dict[str, Any]:
        """Collect detailed information about a specific pod.
        
        Args:
            pod_name: Name of the pod.
            namespace: Kubernetes namespace.
            
        Returns:
            Dictionary with pod description and recent logs.
        """
        if not self.is_available():
            return {
                "status": "unavailable",
                "error": self.connection_error or "Kubernetes not available",
            }
        
        try:
            pod_desc = self.client.get_pod_description(pod_name, namespace)
            logs = self._get_pod_logs(pod_name, namespace)
            
            return {
                "status": "success",
                "pod": pod_desc,
                "logs": logs,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }

    def collect_namespace_snapshot(
        self, namespace: str = "default", pod_filter: Optional[str] = None
    ) -> dict[str, Any]:
        """Collect a snapshot of the namespace state.
        
        Args:
            namespace: Kubernetes namespace.
            pod_filter: Optional label selector to filter pods.
            
        Returns:
            Dictionary with pods, deployments, services, and recent events.
        """
        if not self.is_available():
            return {
                "status": "unavailable",
                "error": self.connection_error or "Kubernetes not available",
            }
        
        try:
            pods = self.client.list_pods(namespace, label_selector=pod_filter)
            deployments = self.client.list_deployments(namespace, label_selector=pod_filter)
            services = self.client.list_services(namespace, label_selector=pod_filter)
            events = self.client.list_events(namespace)
            
            return {
                "status": "success",
                "namespace": namespace,
                "pods": pods,
                "deployments": deployments,
                "services": services,
                "events": events[-20:],  # Last 20 events
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }

    def _get_pod_logs(
        self, pod_name: str, namespace: str = "default", container: Optional[str] = None
    ) -> dict[str, str]:
        """Get logs from a pod's containers.
        
        Args:
            pod_name: Name of the pod.
            namespace: Kubernetes namespace.
            container: Optional specific container.
            
        Returns:
            Dictionary with current and previous logs.
        """
        logs = {}
        
        try:
            # Get current logs
            current_logs = self.client.get_pod_logs(
                pod_name, namespace, container=container
            )
            logs["current"] = current_logs
        except Exception as exc:
            logs["current"] = f"Error reading current logs: {exc}"
        
        try:
            # Get previous logs if available
            previous_logs = self.client.get_pod_logs(
                pod_name, namespace, container=container
            )
            logs["previous"] = previous_logs
        except Exception:
            # Previous logs may not exist for first crash
            logs["previous"] = None
        
        return logs
