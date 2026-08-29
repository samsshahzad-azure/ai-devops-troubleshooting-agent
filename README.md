# AI DevOps Troubleshooting Agent

A FastAPI service that sends troubleshooting questions to a Groq-hosted LLM. Kubernetes tools are intentionally not connected yet.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
notepad .env
python -m uvicorn app.main:app --reload
```

Set `GROQ_API_KEY` in `.env` to your GroqCloud API key. The API key is read from the environment and is never stored in source code.

Open `http://127.0.0.1:8000/docs` for the interactive API. Example request:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/troubleshoot `
  -ContentType "application/json" `
  -Body '{"question":"Why is my Kubernetes pod crashing?"}'
```

The response has this shape:

```json
{
  "question": "Why is my Kubernetes pod crashing?",
  "answer": "...LLM troubleshooting response..."
}
```

Run tests with:

```powershell
python -m pytest
```

## Configuration

Required environment variable: `GROQ_API_KEY`.

Optional environment variable: `GROQ_MODEL`, which defaults to `llama-3.3-70b-versatile`.

If `GROQ_API_KEY` is missing, `/troubleshoot` returns HTTP 503. If the LLM request fails, it returns HTTP 502.
