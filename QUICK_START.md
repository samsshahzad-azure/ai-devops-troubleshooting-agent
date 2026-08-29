# Kubernetes Integration Quick Start

## 1. Verify Installation

```bash
# Run tests
pytest tests/ -v

# All 17 tests should pass ✅
```

## 2. Test Local Fixtures (No K8s Required)

```bash
# Start the server
& 'c:/Users/samss/OneDrive/Desktop/Ai Agent/.venv/Scripts/python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# In another terminal, test the endpoints:

# Check config
curl http://127.0.0.1:8000/config

# Get cluster info (local fixtures)
curl http://127.0.0.1:8000/cluster-info?use_local=true

# Get pod info (local fixtures)
curl http://127.0.0.1:8000/pod-info?pod_name=checkout-api-7d8f9c6b5f-q2m4k&use_local=true

# Troubleshoot with question
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{"question": "Why is my pod crashing?"}'
```

## 3. Enable Real Kubernetes (Optional)

### Step 3a: Start Minikube
```bash
# Start Minikube
minikube start

# Verify it's running
kubectl cluster-info
```

### Step 3b: Configure Agent
Update `.env`:
```bash
KUBERNETES_ENABLED=true
KUBERNETES_USE_LOCAL_FIXTURES=false
KUBERNETES_NAMESPACE=default
```

### Step 3c: Restart Server
```bash
# Kill old server (Ctrl+C)
# Start new server with K8s enabled
& 'c:/Users/samss/OneDrive/Desktop/Ai Agent/.venv/Scripts/python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Step 3d: Deploy Test Pod
```bash
# Create a test pod
kubectl run test-pod --image=nginx

# Test the agent
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the status of my pods?",
    "enable_kubernetes": true,
    "namespace": "default"
  }'
```

## 4. API Reference

### GET /health
```bash
curl http://127.0.0.1:8000/health
# Response: {"status": "ok"}
```

### GET /config
```bash
curl http://127.0.0.1:8000/config
# Returns current Kubernetes configuration
```

### GET /cluster-info
```bash
# With local fixtures
curl http://127.0.0.1:8000/cluster-info?use_local=true

# With real K8s
curl http://127.0.0.1:8000/cluster-info?use_local=false&namespace=default

# Response includes:
# - pods
# - deployments
# - services
# - events
```

### GET /pod-info
```bash
# Get info about specific pod
curl http://127.0.0.1:8000/pod-info?pod_name=my-pod&use_local=true

# Response includes:
# - pod details
# - pod status
# - current logs
# - previous logs (if available)
```

### POST /troubleshoot
```bash
# Without K8s context
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{"question": "Why is my pod crashing?"}'

# With K8s context
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Why is my pod crashing?",
    "enable_kubernetes": true,
    "namespace": "default"
  }'

# Response:
# {
#   "question": "...",
#   "answer": "LLM analysis with cluster context"
# }
```

## 5. Development Workflow

### With Local Fixtures Only
- No Kubernetes needed
- Set `KUBERNETES_USE_LOCAL_FIXTURES=true`
- Perfect for CI/CD pipelines
- Fast testing

### With Real Cluster
- Set `KUBERNETES_USE_LOCAL_FIXTURES=false`
- Set `KUBERNETES_KUBECONFIG_PATH` if needed
- Agent reads real cluster state
- LLM gets actual data

### Switching Modes
Edit `.env` to switch between modes without code changes.

## 6. Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test File
```bash
# Test agent functionality
pytest tests/test_agent.py -v

# Test API endpoints
pytest tests/test_api.py -v

# Test Kubernetes integration
pytest tests/test_kubernetes.py -v
```

### Run Single Test
```bash
pytest tests/test_agent.py::test_agent_collects_cluster_context_when_enabled -v
```

## 7. Troubleshooting

### "Kubernetes not available"
- Check `.env` settings
- Verify kubeconfig path if specified
- Use `KUBERNETES_USE_LOCAL_FIXTURES=true` for development
- Check K8s cluster is running if using real cluster

### "Pod not found"
- Verify pod exists: `kubectl get pods`
- Check namespace: `kubectl get pods -n <namespace>`
- Use `/cluster-info` to list available pods first

### "Connection refused"
- K8s cluster not running
- Kubeconfig incorrect
- Network access blocked
- Fallback to local fixtures with `KUBERNETES_USE_LOCAL_FIXTURES=true`

## 8. Next Steps

1. **Test with Local Fixtures** (no dependencies)
   ```bash
   pytest tests/ -v
   curl http://127.0.0.1:8000/cluster-info?use_local=true
   ```

2. **Start Real Cluster** (Minikube)
   ```bash
   minikube start
   kubectl cluster-info
   ```

3. **Enable Kubernetes Integration**
   - Update `.env`
   - Restart server
   - Test endpoints

4. **Deploy to Production**
   - For AWS EKS: Implement IAM auth
   - For GKE: Add GCP credentials
   - For AKS: Add Azure credentials

## 9. Example Session

```bash
# Terminal 1: Start server
$ cd 'c:\Users\samss\OneDrive\Desktop\Ai Agent'
$ & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload

# Terminal 2: Test endpoints
$ curl http://127.0.0.1:8000/health
{"status":"ok"}

$ curl http://127.0.0.1:8000/config
{"kubernetes_enabled":false,...}

$ curl http://127.0.0.1:8000/cluster-info?use_local=true
{"pods":[...],"events":[...],...}

$ curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{"question":"Why is my pod crashing?"}'
{"question":"...","answer":"..."}
```

---

For more details, see [KUBERNETES_INTEGRATION.md](KUBERNETES_INTEGRATION.md)
