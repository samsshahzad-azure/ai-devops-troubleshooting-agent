"""Allowlisted read-only tools available to the troubleshooting agent."""

from typing import Any

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_namespace_snapshot",
            "description": "Read pods, deployments, services, and events in one Kubernetes namespace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "namespace": {"type": "string", "description": "Kubernetes namespace."},
                },
                "required": ["namespace"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pod_information",
            "description": "Read a pod description and its current and previous logs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pod_name": {"type": "string", "description": "Pod name."},
                    "namespace": {"type": "string", "description": "Kubernetes namespace."},
                },
                "required": ["pod_name", "namespace"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pod_logs",
            "description": "Read current and previous logs for a specific pod.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pod_name": {"type": "string", "description": "Pod name."},
                    "namespace": {"type": "string", "description": "Kubernetes namespace."},
                    "container": {"type": "string", "description": "Optional container name."},
                },
                "required": ["pod_name", "namespace"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pod_events",
            "description": "Read events associated with a specific pod in a namespace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pod_name": {"type": "string", "description": "Pod name."},
                    "namespace": {"type": "string", "description": "Kubernetes namespace."},
                },
                "required": ["pod_name", "namespace"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deployment_information",
            "description": "Read deployment replica and label information in a namespace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "deployment_name": {"type": "string", "description": "Deployment name."},
                    "namespace": {"type": "string", "description": "Kubernetes namespace."},
                },
                "required": ["deployment_name", "namespace"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_service_information",
            "description": "Read service type, ports, selector, and cluster IP in a namespace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_name": {"type": "string", "description": "Service name."},
                    "namespace": {"type": "string", "description": "Kubernetes namespace."},
                },
                "required": ["service_name", "namespace"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_diagnosis",
            "description": "Submit the final concise diagnosis after reviewing verified Kubernetes data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Observed status."},
                    "root_cause": {"type": "string", "description": "Evidence-based root cause."},
                    "recommendation": {"type": "string", "description": "Concise recommended action."},
                },
                "required": ["status", "root_cause", "recommendation"],
                "additionalProperties": False,
            },
        },
    },
]

TOOL_NAMES = frozenset(tool["function"]["name"] for tool in TOOL_DEFINITIONS)


def validate_tool_arguments(tool_name: str, arguments: Any) -> dict[str, str]:
    """Validate a model tool name and its simple string arguments."""
    if tool_name not in TOOL_NAMES:
        raise ValueError(f"Unknown tool: {tool_name}")
    if not isinstance(arguments, dict):
        raise ValueError(f"Invalid arguments for tool: {tool_name}")

    schema = next(tool["function"] for tool in TOOL_DEFINITIONS if tool["function"]["name"] == tool_name)["parameters"]
    properties = schema["properties"]
    required = schema["required"]
    if set(arguments) - set(properties) or any(
        field not in arguments or not isinstance(arguments[field], str) or not arguments[field].strip()
        for field in required
    ):
        raise ValueError(f"Invalid arguments for tool: {tool_name}")
    if any(not isinstance(value, str) for value in arguments.values()):
        raise ValueError(f"Invalid arguments for tool: {tool_name}")
    return {key: value.strip() for key, value in arguments.items()}


__all__ = ["TOOL_DEFINITIONS", "TOOL_NAMES", "validate_tool_arguments"]
