import json
from typing import Any

from groq import Groq

from .config import settings
from .tools import collect_cluster_snapshot


class LLMConfigurationError(RuntimeError):
    """Raised when the LLM client cannot be configured."""


class LLMRequestError(RuntimeError):
    """Raised when the LLM does not return a usable response."""


class TroubleshootingAgent:
    def __init__(self) -> None:
        self.client = (
            Groq(api_key=settings.groq_api_key)
            if settings.groq_api_key
            else None
        )

    def investigate(self, question: str) -> dict[str, str]:
        if self.client is None:
            raise LLMConfigurationError("GROQ_API_KEY is not configured")

        # Collect cluster information if enabled
        cluster_context = ""
        if settings.kubernetes_enabled:
            cluster_info = self._collect_context()
            cluster_context = self._format_cluster_context(cluster_info)

        try:
            response = self.client.chat.completions.create(
                model=settings.groq_model,
                temperature=0,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a Kubernetes troubleshooting assistant. Return ONLY valid JSON "
                            "with exactly these string fields: status, root_cause, recommendation. "
                            "Keep every field concise.\n"
                            "CRITICAL RULES:\n"
                            "1. Use only the actual Kubernetes data provided in the cluster context.\n"
                            "2. Do NOT invent pod names, statuses, events, images, logs, or resources.\n"
                            "3. If the requested resource is absent, set status to 'Not found' and say so in root_cause.\n"
                            "4. For ImagePullBackOff or ErrImagePull, state that the container image cannot be pulled.\n"
                            "5. Do not include diagnostic command lists unless the user explicitly requests commands.\n"
                            "6. If Kubernetes data is unavailable, state that in status and do not infer a cause."
                        ),
                    },
                    {
                        "role": "user",
                        "content": self._build_user_message(question, cluster_context),
                    },
                ],
            )
        except Exception as exc:
            raise LLMRequestError("The LLM request failed") from exc

        answer = response.choices[0].message.content
        if not answer:
            raise LLMRequestError("The LLM returned an empty response")

        try:
            structured_answer = json.loads(answer)
        except (TypeError, json.JSONDecodeError) as exc:
            raise LLMRequestError("The LLM returned invalid JSON") from exc

        required_fields = ("status", "root_cause", "recommendation")
        if (
            not isinstance(structured_answer, dict)
            or any(
                not isinstance(structured_answer.get(field), str)
                or not structured_answer[field].strip()
                for field in required_fields
            )
        ):
            raise LLMRequestError("The LLM returned an invalid response format")

        return {field: structured_answer[field].strip() for field in required_fields}

    def _collect_context(self) -> dict[str, Any]:
        """Collect cluster information for context.
        
        Returns:
            Dictionary with cluster snapshot information.
        """
        return collect_cluster_snapshot(
            namespace=settings.kubernetes_namespace,
            use_local=settings.kubernetes_use_local_fixtures,
            kubeconfig_path=settings.kubernetes_kubeconfig_path,
        )

    def _format_cluster_context(self, cluster_info: dict[str, Any]) -> str:
        """Format cluster information into a readable context string.
        
        Args:
            cluster_info: Dictionary from collect_cluster_snapshot.
            
        Returns:
            Formatted string for inclusion in LLM prompt.
        """
        if cluster_info.get("status") == "unavailable":
            return f"\n[Kubernetes Unavailable: {cluster_info.get('error')}]"

        if cluster_info.get("status") == "error":
            return f"\n[Error collecting cluster info: {cluster_info.get('error')}]"

        namespace = cluster_info.get("namespace", "default")
        context_parts = [f"\n[ACTUAL Kubernetes Cluster Data - Namespace: {namespace}]"]

        # Add pods - be explicit about what's there
        pods = cluster_info.get("pods", [])
        if pods:
            context_parts.append(f"Pods found ({len(pods)}):")
            for pod in pods[:10]:  # Show all if less than 10
                context_parts.append(
                    f"  - NAME: {pod['name']}, STATUS: {pod.get('status')}, "
                    f"RESTARTS: {pod.get('restarts', 0)}, READY: {pod.get('ready', False)}"
                )
        else:
            context_parts.append("Pods found: NONE (no pods in this namespace)")

        # Add deployments
        deployments = cluster_info.get("deployments", [])
        if deployments:
            context_parts.append(f"Deployments found ({len(deployments)}):")
            for dep in deployments[:5]:
                ready = dep.get("ready_replicas", 0)
                total = dep.get("replicas", 0)
                context_parts.append(
                    f"  - NAME: {dep['name']}, READY: {ready}/{total} replicas"
                )
        else:
            context_parts.append("Deployments found: NONE")

        # Add recent events
        events = cluster_info.get("events", [])
        if events:
            context_parts.append(f"Recent Events found ({len(events)}):")
            for event in events[-10:]:  # Last 10 events
                context_parts.append(
                    f"  - TYPE: {event.get('type')}, REASON: {event.get('reason')}, "
                    f"POD/RESOURCE: {event.get('name')}, MESSAGE: {event.get('message')}"
                )
        else:
            context_parts.append("Events found: NONE")

        return "\n".join(context_parts)

    def _build_user_message(self, question: str, cluster_context: str) -> str:
        """Build the user message with question and cluster context.
        
        Args:
            question: The user's question.
            cluster_context: Formatted cluster information.
            
        Returns:
            Complete user message for LLM.
        """
        if cluster_context:
            return f"{cluster_context}\n\nQuestion: {question}"
        return question


agent = TroubleshootingAgent()
