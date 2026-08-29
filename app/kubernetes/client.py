"""Kubernetes client wrapper for read-only operations."""

from typing import Optional

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException


class KubernetesConnectionError(RuntimeError):
    """Raised when Kubernetes client cannot be initialized."""


class KubernetesClient:
    """Wrapper for read-only Kubernetes API operations."""

    def __init__(self, kubeconfig_path: Optional[str] = None) -> None:
        """Initialize Kubernetes client.
        
        Args:
            kubeconfig_path: Path to kubeconfig file. If None, uses default locations.
        
        Raises:
            KubernetesConnectionError: If unable to connect to cluster.
        """
        try:
            if kubeconfig_path:
                config.load_kube_config(config_file=kubeconfig_path)
            else:
                # Try in-cluster config first, then fall back to kubeconfig
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()
            
            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.is_connected = True
        except Exception as exc:
            self.is_connected = False
            raise KubernetesConnectionError(
                f"Failed to connect to Kubernetes cluster: {exc}"
            ) from exc

    def list_pods(
        self, namespace: str = "default", label_selector: Optional[str] = None
    ) -> list[dict]:
        """Get pods in a namespace.
        
        Args:
            namespace: Kubernetes namespace.
            label_selector: Optional label selector filter.
            
        Returns:
            List of pod information dicts.
        """
        try:
            pods = self.v1.list_namespaced_pod(
                namespace, label_selector=label_selector
            )
            return [
                {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": pod.status.phase,
                    "restarts": sum(
                        c.restart_count or 0 for c in pod.status.container_statuses or []
                    ),
                    "containers": [c.name for c in pod.spec.containers],
                    "ready": pod.status.conditions[-1].status == "True"
                    if pod.status.conditions
                    else False,
                }
                for pod in pods.items
            ]
        except ApiException as exc:
            raise RuntimeError(f"Failed to list pods: {exc}") from exc

    def get_pod_logs(
        self, pod_name: str, namespace: str = "default", container: Optional[str] = None
    ) -> str:
        """Get logs from a pod.
        
        Args:
            pod_name: Name of the pod.
            namespace: Kubernetes namespace.
            container: Optional specific container name.
            
        Returns:
            Pod logs as string.
        """
        try:
            return self.v1.read_namespaced_pod_log(
                pod_name, namespace, container=container, tail_lines=100
            )
        except ApiException as exc:
            raise RuntimeError(f"Failed to get pod logs: {exc}") from exc

    def get_pod_description(self, pod_name: str, namespace: str = "default") -> dict:
        """Get detailed pod information.
        
        Args:
            pod_name: Name of the pod.
            namespace: Kubernetes namespace.
            
        Returns:
            Detailed pod information dict.
        """
        try:
            pod = self.v1.read_namespaced_pod(pod_name, namespace)
            conditions = {}
            if pod.status.conditions:
                conditions = {
                    c.type: {"status": c.status, "reason": c.reason, "message": c.message}
                    for c in pod.status.conditions
                }
            
            container_statuses = []
            if pod.status.container_statuses:
                container_statuses = [
                    {
                        "name": c.name,
                        "ready": c.ready,
                        "restart_count": c.restart_count or 0,
                        "last_state": str(c.last_state) if c.last_state else None,
                        "state": str(c.state) if c.state else None,
                    }
                    for c in pod.status.container_statuses
                ]
            
            return {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
                "conditions": conditions,
                "container_statuses": container_statuses,
                "node_name": pod.spec.node_name,
                "labels": pod.metadata.labels or {},
                "annotations": pod.metadata.annotations or {},
            }
        except ApiException as exc:
            raise RuntimeError(f"Failed to get pod description: {exc}") from exc

    def list_events(
        self, namespace: str = "default", field_selector: Optional[str] = None
    ) -> list[dict]:
        """Get events in a namespace.
        
        Args:
            namespace: Kubernetes namespace.
            field_selector: Optional field selector filter.
            
        Returns:
            List of event information dicts.
        """
        try:
            events = self.v1.list_namespaced_event(
                namespace, field_selector=field_selector
            )
            return [
                {
                    "kind": event.involved_object.kind,
                    "name": event.involved_object.name,
                    "reason": event.reason,
                    "message": event.message,
                    "type": event.type,
                    "timestamp": event.last_timestamp.isoformat()
                    if event.last_timestamp
                    else None,
                }
                for event in events.items
            ]
        except ApiException as exc:
            raise RuntimeError(f"Failed to list events: {exc}") from exc

    def list_deployments(
        self, namespace: str = "default", label_selector: Optional[str] = None
    ) -> list[dict]:
        """Get deployments in a namespace.
        
        Args:
            namespace: Kubernetes namespace.
            label_selector: Optional label selector filter.
            
        Returns:
            List of deployment information dicts.
        """
        try:
            deployments = self.apps_v1.list_namespaced_deployment(
                namespace, label_selector=label_selector
            )
            return [
                {
                    "name": dep.metadata.name,
                    "namespace": dep.metadata.namespace,
                    "replicas": dep.spec.replicas or 0,
                    "ready_replicas": dep.status.ready_replicas or 0,
                    "updated_replicas": dep.status.updated_replicas or 0,
                    "labels": dep.metadata.labels or {},
                }
                for dep in deployments.items
            ]
        except ApiException as exc:
            raise RuntimeError(f"Failed to list deployments: {exc}") from exc

    def list_services(
        self, namespace: str = "default", label_selector: Optional[str] = None
    ) -> list[dict]:
        """Get services in a namespace.
        
        Args:
            namespace: Kubernetes namespace.
            label_selector: Optional label selector filter.
            
        Returns:
            List of service information dicts.
        """
        try:
            services = self.v1.list_namespaced_service(
                namespace, label_selector=label_selector
            )
            return [
                {
                    "name": svc.metadata.name,
                    "namespace": svc.metadata.namespace,
                    "type": svc.spec.type,
                    "cluster_ip": svc.spec.cluster_ip,
                    "ports": [
                        {"port": p.port, "target_port": p.target_port, "protocol": p.protocol}
                        for p in svc.spec.ports or []
                    ],
                    "selector": svc.spec.selector or {},
                }
                for svc in services.items
            ]
        except ApiException as exc:
            raise RuntimeError(f"Failed to list services: {exc}") from exc
