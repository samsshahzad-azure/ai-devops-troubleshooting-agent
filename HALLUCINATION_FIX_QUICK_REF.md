# Quick Reference: Kubernetes Hallucination Fix

## What Was Fixed
The agent no longer uses local fixture pods (like `checkout-api`) when you request analysis of real Kubernetes clusters.

## The Bug
```
User: "Why is broken-app failing in ai-agent-test?"
Agent: "Pod checkout-api is in CrashLoopBackOff..." 
        ← WRONG - This is from local fixtures, not your cluster!
```

## The Fix (3 changes)
1. **Endpoint** - Disable local fixtures when K8s is enabled
2. **Prompt** - Explicitly forbid hallucinations  
3. **Format** - Clear labels showing real vs. fixture data

## How to Use

### Query Real Kubernetes
```bash
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Why is my-pod failing?",
    "enable_kubernetes": true,
    "namespace": "production"
  }'
```

**Result:** Agent queries your `production` namespace in the real cluster.

### Query Local Fixtures (Testing)
```bash
curl -X POST http://127.0.0.1:8000/troubleshoot \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Why is checkout-api failing?",
    "enable_kubernetes": false,
    "namespace": "default"
  }'
```

**Result:** Agent uses local fixture data (fast for testing).

## Verifying the Fix

### Run Tests
```bash
cd "c:\Users\samss\OneDrive\Desktop\Ai Agent"
python -m pytest tests/ -v
# Expected: 19 passed ✓
```

### Run Integration Test
```bash
python test_hallucination_fix.py
# Expected: All tests pass ✓
```

## Key Behavior Changes

| Scenario | Before Fix | After Fix |
|----------|-----------|-----------|
| `enable_kubernetes=true`, namespace=`production` | Used local fixtures ❌ | Queries real cluster ✓ |
| Pod doesn't exist in cluster | Hallucinated data ❌ | Reports "not found" ✓ |
| Pod status in fixture differs from real | Returned fixture data ❌ | Returns real status ✓ |
| User asks about `broken-app`, only `checkout-api` in fixtures | Returned `checkout-api` ❌ | Returns "not found" ✓ |

## Technical Details

### Configuration (Endpoint Setting)
```python
# app/main.py - POST /troubleshoot
if request.enable_kubernetes:
    settings.kubernetes_enabled = True
    settings.kubernetes_namespace = request.namespace
    settings.kubernetes_use_local_fixtures = False  # ← This was missing!
```

### Context Formatting (Clear Labels)
```
Before: [Cluster Information]
After:  [ACTUAL Kubernetes Cluster Data - Namespace: production]
        Pods found (3):
          - NAME: pod-1, STATUS: Running
          ...
```

### LLM Prompt (Anti-Hallucination)
```
CRITICAL RULES:
1. Only use the actual Kubernetes data provided below.
2. Do NOT invent pod names, statuses, or logs.
3. If resource not found, say: "Resource not found"
```

## What Tests Were Added

1. `test_agent_uses_actual_k8s_data_not_hallucinated()` 
   - Verifies agent uses ONLY provided data
   - Checks `checkout-api` (from fixtures) is excluded
   
2. `test_troubleshoot_disables_local_fixtures_when_kubernetes_enabled()`
   - Verifies endpoint sets `kubernetes_use_local_fixtures=False`

## Files Changed
- `app/main.py` (+3 lines)
- `app/agent.py` (+60 lines)
- `tests/test_agent.py` (+50 lines, added 1 test)
- `tests/test_api.py` (+30 lines, added 1 test)

## Support
If hallucinations persist:
1. Check `kubernetes_enabled` is `true` when expected
2. Verify `kubernetes_use_local_fixtures` is `false` when querying real K8s
3. Run: `python test_hallucination_fix.py` to diagnose
4. Check Groq API key is valid and model is set correctly
