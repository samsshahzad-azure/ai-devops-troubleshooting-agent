import json
from types import SimpleNamespace
from typing import Any

from groq import Groq

from .config import settings
from .tool_registry import TOOL_DEFINITIONS, validate_tool_arguments
from .tools import (
    collect_cluster_snapshot,
    collect_deployment_information,
    collect_pod_events,
    collect_pod_information,
    collect_pod_logs,
    collect_service_information,
)


class LLMConfigurationError(RuntimeError):
    """Raised when the LLM client cannot be configured."""


class LLMRequestError(RuntimeError):
    """Raised when the LLM does not return a usable response."""


MAX_TOOL_CALLS = 5


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

        final_response_instruction = (
            "by calling submit_diagnosis after reviewing Kubernetes data."
            if settings.kubernetes_enabled
            else "as the final assistant message."
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a Kubernetes troubleshooting assistant. Return ONLY valid JSON "
                    "with exactly these string fields: status, root_cause, recommendation, "
                    f"{final_response_instruction} "
                    "Keep every field concise.\n"
                    "CRITICAL RULES:\n"
                    "1. Use only the actual Kubernetes data provided in the cluster context or tool results.\n"
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
        ]
        tool_calls_used = 0
        while True:
            request: dict[str, Any] = {
                "model": settings.groq_model,
                "temperature": 0,
                "messages": messages,
            }
            if settings.kubernetes_enabled:
                request["tools"] = TOOL_DEFINITIONS
                request["tool_choice"] = "auto"

            try:
                response = self.client.chat.completions.create(**request)
            except Exception as exc:
                raise LLMRequestError("The LLM request failed") from exc

            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None) or []
            if not tool_calls:
                answer = message.content
                break
            if tool_calls_used + len(tool_calls) > MAX_TOOL_CALLS:
                raise LLMRequestError("The LLM exceeded the maximum number of tool calls")

            messages.append(self._assistant_tool_message(message))
            for tool_call in tool_calls:
                result = self._execute_tool_call(tool_call)
                if tool_call.function.name == "submit_diagnosis":
                    return result
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )
                tool_calls_used += 1

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

    def _assistant_tool_message(self, message: Any) -> dict[str, Any]:
        """Convert an SDK assistant message into a conversation message."""
        return {
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in message.tool_calls
            ],
        }

    def _execute_tool_call(self, tool_call: Any) -> dict[str, Any]:
        """Validate and execute one fixed, read-only tool."""
        tool_name = getattr(tool_call.function, "name", None)
        try:
            raw_arguments = json.loads(tool_call.function.arguments)
            arguments = validate_tool_arguments(tool_name, raw_arguments)
        except (AttributeError, TypeError, json.JSONDecodeError, ValueError) as exc:
            raise LLMRequestError("The LLM returned invalid tool arguments") from exc

        if tool_name == "submit_diagnosis":
            return arguments

        if "namespace" in arguments and arguments["namespace"] != settings.kubernetes_namespace:
            raise LLMRequestError("The LLM requested a different Kubernetes namespace")

        tool_functions = {
            "get_namespace_snapshot": collect_cluster_snapshot,
            "get_pod_information": collect_pod_information,
            "get_pod_logs": collect_pod_logs,
            "get_pod_events": collect_pod_events,
            "get_deployment_information": collect_deployment_information,
            "get_service_information": collect_service_information,
        }
        try:
            if tool_name == "get_namespace_snapshot":
                return tool_functions[tool_name](
                    namespace=arguments["namespace"],
                    use_local=settings.kubernetes_use_local_fixtures,
                    kubeconfig_path=settings.kubernetes_kubeconfig_path,
                )
            if tool_name == "get_pod_information":
                return tool_functions[tool_name](
                    pod_name=arguments["pod_name"],
                    namespace=arguments["namespace"],
                    use_local=settings.kubernetes_use_local_fixtures,
                    kubeconfig_path=settings.kubernetes_kubeconfig_path,
                )
            if tool_name == "get_pod_logs":
                return tool_functions[tool_name](
                    pod_name=arguments["pod_name"],
                    namespace=arguments["namespace"],
                    container=arguments.get("container"),
                    use_local=settings.kubernetes_use_local_fixtures,
                    kubeconfig_path=settings.kubernetes_kubeconfig_path,
                )
            if tool_name == "get_pod_events":
                return tool_functions[tool_name](
                    pod_name=arguments["pod_name"],
                    namespace=arguments["namespace"],
                    use_local=settings.kubernetes_use_local_fixtures,
                    kubeconfig_path=settings.kubernetes_kubeconfig_path,
                )
            return tool_functions[tool_name](
                namespace=arguments["namespace"],
                **{
                    "deployment_name": arguments["deployment_name"]
                    if tool_name == "get_deployment_information"
                    else arguments["service_name"]
                },
                use_local=settings.kubernetes_use_local_fixtures,
                kubeconfig_path=settings.kubernetes_kubeconfig_path,
            )
        except Exception as exc:
            raise LLMRequestError("The Kubernetes tool failed") from exc

    def _collect_context(self) -> dict[str, Any]:
        """Collect cluster information for context.
        
        Returns:
            Dictionary with cluster snapshot information.
        """
        return self._execute_tool_call(
            SimpleNamespace(
                function=SimpleNamespace(
                    name="get_namespace_snapshot",
                    arguments=json.dumps({"namespace": settings.kubernetes_namespace}),
                )
            )
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
