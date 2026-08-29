# Kubernetes Test Deployment Guide

This guide helps you set up a test deployment to verify your AI DevOps Troubleshooting Agent works with real Kubernetes clusters.

## Overview

The test deployment creates:
- **Namespace:** `ai-agent-test` (isolated, safe to delete)
- **Deployment:** `broken-app` (intentionally broken for testing)
- **Pod:** Enters `ImagePullBackOff` status (perfect for testing troubleshooting)

The pod will fail to start because it uses a nonexistent Docker image, allowing you to test your agent's troubleshooting capabilities.

---

## Prerequisites

Before applying the test deployment, ensure:
- Kubernetes cluster is running (Minikube, Docker Desktop, EKS, etc.)
- `kubectl` is installed and configured
- Cluster has internet access to pull images (or will see `ImagePullBackOff`)

Verify cluster access:
```bash
kubectl cluster-info
kubectl get nodes
```

---

## 1️⃣ Apply the Test Deployment

### Command

```bash
kubectl apply -f k8s-test-deployment.yaml
```

### Expected Output

```
namespace/ai-agent-test created
deployment.apps/broken-app created
```

---

## 2️⃣ Verify the Test Resources

### Check Namespace Created

```bash
kubectl get namespaces | grep ai-agent-test
```

Expected output:
```
ai-agent-test   Active   1m
```

### Check Deployment Created

```bash
kubectl get deployment -n ai-agent-test
```

Expected output:
```
NAME         READY   UP-TO-DATE   AVAILABLE   AGE
broken-app   0/1     1            0           1m
```

### Check Pod Status (Should be ImagePullBackOff)

```bash
kubectl get pods -n ai-agent-test
```

Expected output:
```
NAME                          READY   STATUS              RESTARTS   AGE
broken-app-5f7d9b8c4c-xyz123  0/1     ImagePullBackOff    0          1m
```

### Get Full Pod Details

```bash
kubectl describe pod -n ai-agent-test broken-app-5f7d9b8c4c-xyz123
```

This shows the complete status including error messages.

### View Recent Events

```bash
kubectl get events -n ai-agent-test
```

Expected events:
```
Failed to pull image "nonexistent-registry.example.com/nonexistent-image:nonexistent-tag"
```

---

## 3️⃣ Test Your AI Agent with the Broken Pod

### Enable Kubernetes in Agent

Update `.env` in your AI agent project:
```bash
KUBERNETES_ENABLED=true
KUBERNETES_USE_LOCAL_FIXTURES=false
KUBERNETES_NAMESPACE=ai-agent-test
```

### Restart Agent

```bash
# Kill the old server (Ctrl+C)
# Start new server with K8s enabled
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Query the Agent

```bash
# Get cluster info from ai-agent-test namespace
curl http://127.0.0.1:8000/cluster-info?namespace=ai-agent-test&use_local=false

# Get pod info
curl http://127.0.0.1:8000/pod-info?pod_name=broken-app-5f7d9b8c4c-xyz123&namespace=ai-agent-test&use_local=false

# Ask agent to troubleshoot
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Why is my broken-app pod failing?",
    "enable_kubernetes": true,
    "namespace": "ai-agent-test"
  }'
```

### Expected Agent Response

The agent should identify:
```
- Pod status: ImagePullBackOff
- Root cause: Nonexistent Docker image
- Recommended action: Verify image name, registry, and access
```

---

## 4️⃣ Clean Up Test Resources

### Delete the Test Deployment

```bash
kubectl delete -f k8s-test-deployment.yaml
```

Expected output:
```
namespace "ai-agent-test" deleted
deployment.apps "broken-app" deleted
```

### Verify Deletion

```bash
kubectl get namespaces | grep ai-agent-test
# Should return no results

kubectl get pods -n ai-agent-test
# Should error: namespace "ai-agent-test" not found
```

---

## Advanced: Create Additional Test Scenarios

### Scenario 1: Pod Crashes Due to Missing Config

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: ai-agent-test
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: missing-env-app
  namespace: ai-agent-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: missing-env-app
  template:
    metadata:
      labels:
        app: missing-env-app
    spec:
      containers:
      - name: app
        image: nginx:latest
        env:
        - name: REQUIRED_VAR
          valueFrom:
            configMapKeyRef:
              name: nonexistent-config
              key: some-key
EOF
```

### Scenario 2: Pod Out of Memory (OOMKilled)

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: ai-agent-test
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-leak-app
  namespace: ai-agent-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: memory-leak-app
  template:
    metadata:
      labels:
        app: memory-leak-app
    spec:
      containers:
      - name: app
        image: nginx:latest
        resources:
          limits:
            memory: "1Mi"  # Very low limit
          requests:
            memory: "1Mi"
EOF
```

---

## Troubleshooting

### Pod stuck in Pending

```bash
kubectl describe pod -n ai-agent-test broken-app-<hash>
```

Check for:
- `SchedulingFailure` - Not enough resources
- `Unschedulable` - Node constraints
- `ImagePullBackOff` - Image issue (expected)

### Can't connect to cluster

```bash
# Check kubeconfig
kubectl config view

# Check current context
kubectl current-context

# List contexts
kubectl config get-contexts

# Switch context
kubectl config use-context <context-name>
```

### Agent can't see pods

Verify in agent:
- `KUBERNETES_ENABLED=true`
- `KUBERNETES_USE_LOCAL_FIXTURES=false`
- Correct namespace: `KUBERNETES_NAMESPACE=ai-agent-test`
- Cluster connectivity working

---

## Safety Guarantees

✅ **Safe to apply:**
- Creates new namespace (isolated)
- Only affects `ai-agent-test` namespace
- No changes to other namespaces
- No changes to existing applications

✅ **Easy to clean up:**
- Single command deletes everything
- No orphaned resources
- No left-over deployments or pods

✅ **Safe to repeat:**
- Can run multiple times
- Won't interfere with previous runs
- No data persistence

---

## Quick Command Reference

```bash
# Apply test deployment
kubectl apply -f k8s-test-deployment.yaml

# Check namespace
kubectl get namespaces

# Check deployment
kubectl get deployment -n ai-agent-test

# Check pod (should show ImagePullBackOff)
kubectl get pods -n ai-agent-test

# Describe pod (full details)
kubectl describe pod -n ai-agent-test <pod-name>

# View events
kubectl get events -n ai-agent-test

# Delete everything
kubectl delete -f k8s-test-deployment.yaml

# Verify deletion
kubectl get namespaces | grep ai-agent-test  # Should return nothing
```

---

## Next Steps

1. Apply the deployment: `kubectl apply -f k8s-test-deployment.yaml`
2. Verify pod status: `kubectl get pods -n ai-agent-test`
3. Enable K8s in agent: Update `.env`
4. Test agent troubleshooting: Query `/troubleshoot` endpoint
5. Clean up when done: `kubectl delete -f k8s-test-deployment.yaml`

Enjoy testing your AI DevOps Troubleshooting Agent! 🚀
