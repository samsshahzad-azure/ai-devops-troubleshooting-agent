"""Tests for Kubernetes integration."""

import pytest

from app.kubernetes import KubernetesConnectionError, KubernetesReader


def test_kubernetes_reader_handles_unavailable_cluster() -> None:
    """Test that reader handles unavailable cluster gracefully."""
    # This should not raise an exception, but mark as unavailable
    reader = KubernetesReader(kubeconfig_path="/nonexistent/path")
    
    assert not reader.is_available()
    assert reader.connection_error is not None


def test_collect_namespace_snapshot_when_unavailable() -> None:
    """Test collecting snapshot when K8s is unavailable."""
    reader = KubernetesReader(kubeconfig_path="/nonexistent/path")
    
    snapshot = reader.collect_namespace_snapshot()
    
    assert snapshot["status"] == "unavailable"
    assert "error" in snapshot


def test_collect_pod_info_when_unavailable() -> None:
    """Test collecting pod info when K8s is unavailable."""
    reader = KubernetesReader(kubeconfig_path="/nonexistent/path")
    
    info = reader.collect_pod_info("test-pod")
    
    assert info["status"] == "unavailable"
    assert "error" in info


def test_kubernetes_reader_with_local_fixtures() -> None:
    """Test that tools use local fixtures correctly."""
    from app.tools import collect_cluster_snapshot
    
    snapshot = collect_cluster_snapshot(use_local=True)
    
    assert "pods" in snapshot
    assert len(snapshot["pods"]) > 0
    assert snapshot["pods"][0]["name"] == "checkout-api-7d8f9c6b5f-q2m4k"
    assert snapshot["pods"][0]["status"] == "CrashLoopBackOff"


def test_collect_cluster_snapshot_returns_pods_events_logs() -> None:
    """Test that cluster snapshot includes all required data."""
    from app.tools import collect_cluster_snapshot
    
    snapshot = collect_cluster_snapshot(use_local=True)
    
    assert "pods" in snapshot
    assert "events" in snapshot
    assert "logs" in snapshot


def test_collect_pod_information_uses_local_fixtures() -> None:
    """Test that pod information collection works with local fixtures."""
    from app.tools import collect_pod_information
    
    info = collect_pod_information(
        pod_name="checkout-api-7d8f9c6b5f-q2m4k",
        use_local=True,
    )
    
    assert info["pod"]["name"] == "checkout-api-7d8f9c6b5f-q2m4k"
    assert "logs" in info
