# Kubernetes Integration Guide

## Overview

The AI DevOps Troubleshooting Agent now includes **read-only Kubernetes integration** that allows it to:
- Analyze cluster state and pod information
- Provide context-aware troubleshooting advice based on live cluster data
- Support both local Minikube clusters and cloud providers (AWS EKS ready)

## Architecture

### Modules

1. **`app/kubernetes/client.py`** - Kubernetes API client wrapper
   - Read-only operations only (no create, delete, patch, or modify)
   - Handles pod information, logs, deployments, services, events
   - Gracefully handles connection failures

2. **`app/kubernetes/reader.py`** - High-level data collection
   - `KubernetesReader` class for collecting cluster snapshots
   - Pod-specific information collection
   - Error handling for unavailable clusters

3. **`app/tools.py`** - Data access layer
   - Unified interface for local fixtures and real Kubernetes
   - `collect_cluster_snapshot()` - Get namespace state
   - `collect_pod_information()` - Get pod details and logs
   - Support for both development (local fixtures) and production (real K8s)

4. **`app/agent.py`** - Enhanced troubleshooting agent
   - Collects cluster context before calling Groq LLM
   - Formats cluster information for LLM analysis
   - Backwards compatible with existing API

## API Endpoints

### Health Check
```
GET /health
```
Returns agent status.

### Troubleshoot (Enhanced)
```
POST /troubleshoot
{
  "question": "Why is my Kubernetes pod crashing?",
  "namespace": "default",
  "enable_kubernetes": false
}
```
- `question` (required): The troubleshooting question
- `namespace` (optional, default: "default"): Kubernetes namespace to analyze
- `enable_kubernetes` (optional, default: false): Enable K8s context collection

Response includes LLM analysis with Kubernetes context if enabled.

### Get Configuration
```
GET /config
```
Returns current configuration including Kubernetes settings.

### Get Cluster Information
```
GET /cluster-info?namespace=default&use_local=true
```
Returns cluster snapshot with:
- Pods and their status
- Deployments and replica status
- Services
- Recent events

### Get Pod Information
```
GET /pod-info?pod_name=my-pod&namespace=default&use_local=true
```
Returns detailed pod information:
- Pod description and status
- Container details
- Current and previous logs
- Conditions

## Configuration

Set these environment variables in `.env`:

```bash
# Existing settings
GROQ_API_KEY=your_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

# Kubernetes settings
KUBERNETES_ENABLED=false
KUBERNETES_NAMESPACE=default
KUBERNETES_KUBECONFIG_PATH=/path/to/kubeconfig  # Optional
KUBERNETES_USE_LOCAL_FIXTURES=true  # Use local data in dev
```

## Usage Examples

### Example 1: Quick troubleshooting question
```bash
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{"question": "Why is my pod crashing?"}'
```

### Example 2: With Kubernetes context
```bash
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Why is my pod crashing?",
    "enable_kubernetes": true,
    "namespace": "default"
  }'
```

### Example 3: Get cluster info
```bash
curl http://127.0.0.1:8000/cluster-info?use_local=true
```

### Example 4: Get pod logs
```bash
curl http://127.0.0.1:8000/pod-info?pod_name=my-pod&use_local=true
```

## Features

### ✅ Implemented
- [x] Read-only Kubernetes API integration
- [x] Pod information and logs collection
- [x] Pod descriptions and status
- [x] Deployment information
- [x] Service information
- [x] Event logging
- [x] Local fixtures for development/testing
- [x] Graceful handling of unavailable clusters
- [x] Cluster context in LLM prompts
- [x] Modular architecture for provider support
- [x] Comprehensive test coverage (17 tests)

### 🔒 Security
- **Read-only only** - No write, create, delete, or patch operations
- **Error handling** - Failures don't crash the agent
- **API key protection** - Groq API key in .env (not in git)

### 📦 Modular Design
- Can be extended for AWS EKS, Google GKE, Azure AKS
- Local fixtures for development without cluster access
- Configurable via environment variables

## Testing

Run all tests:
```bash
pytest tests/ -v
```

Test coverage:
- Agent context collection
- Kubernetes client read operations
- API endpoints
- Error handling and edge cases
- Local fixture data access

All 17 tests pass ✅

## Future Enhancements

1. **AWS EKS Support** - Add IAM authentication
2. **Google GKE Support** - Add GCP credentials
3. **Azure AKS Support** - Add Azure credentials
4. **Metrics Integration** - Collect resource usage
5. **Custom Resource Support** - Read CRDs
6. **RBAC Awareness** - Check pod permissions

## Read-Only Operations Only

The agent implements **read-only access only**. Prohibited operations:
- ❌ Creating resources (pods, deployments, etc.)
- ❌ Deleting resources
- ❌ Patching/modifying resources
- ❌ Scaling deployments
- ❌ Restarting pods
- ❌ Port forwarding
- ❌ Executing commands in pods

This design ensures the agent can safely analyze clusters without making changes.

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│         FastAPI Application                     │
├─────────────────────────────────────────────────┤
│  POST /troubleshoot (Enhanced)                  │
│  GET /config                                    │
│  GET /cluster-info                              │
│  GET /pod-info                                  │
└─────────────────┬───────────────────────────────┘
                  │
          ┌───────▼──────────┐
          │   agent.py       │
          │  (Investigation) │
          └───────┬──────────┘
                  │
        ┌─────────▼──────────────┐
        │    tools.py            │
        │  (Data Access Layer)   │
        └─────────┬──────────────┘
                  │
     ┌────────────┴────────────┐
     │                         │
  LOCAL FIXTURES        KUBERNETES
  (Development)         (Production)
     │                         │
     ▼                         ▼
  app/tools.py       app/kubernetes/
                     - client.py
                     - reader.py
```

## Troubleshooting

### "Kubernetes not available"
- Ensure kubeconfig exists at configured path
- Or ensure in-cluster config is available (if running in pod)
- Check KUBERNETES_USE_LOCAL_FIXTURES=true for development

### "Pod logs not available"
- Pod must exist in specified namespace
- Container must have logs (some failed pods have no logs)
- Check pod status with `/cluster-info` endpoint first

### "Connection refused"
- Ensure Kubernetes cluster is running
- Verify kubeconfig points to running cluster
- Check firewall/network access to cluster API
