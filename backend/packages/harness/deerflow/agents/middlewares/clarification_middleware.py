"""Middleware for intercepting clarification requests and presenting them to the user."""

import json
from collections.abc import Callable
from typing import Any, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.graph import END
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command


class ClarificationMiddlewareState(AgentState):
    """Compatible with the `ThreadState` schema."""

    pass


class ClarificationMiddleware(AgentMiddleware[ClarificationMiddlewareState]):
    """Intercepts clarification tool calls and interrupts execution to present questions to the user.

    When the model calls the `ask_clarification` tool, this middleware:
    1. Intercepts the tool call before execution
    2. Extracts the questions and metadata
    3. Formats a message with structured data for frontend wizard rendering
    4. Returns a Command that interrupts execution and presents the questions
    5. Waits for user response before continuing

    This enables a multi-question wizard UI where users can navigate step by step.
    """

    state_schema = ClarificationMiddlewareState

    def _normalize_option(self, option: dict[str, Any] | str, index: int) -> dict[str, Any]:
        """Normalize an option to structured format.

        Args:
            option: Raw option (string or dict)
            index: Option index for generating value

        Returns:
            Normalized option dict with label, description, value, recommended
        """
        if isinstance(option, str):
            return {
                "label": option,
                "description": None,
                "value": str(index + 1),
                "recommended": False,
            }
        elif isinstance(option, dict):
            return {
                "label": option.get("label", f"Option {index + 1}"),
                "description": option.get("description"),
                "value": option.get("value", str(index + 1)),
                "recommended": option.get("recommended", False),
            }
        else:
            return {
                "label": str(option),
                "description": None,
                "value": str(index + 1),
                "recommended": False,
            }

    def _normalize_question(self, question: dict[str, Any], index: int) -> dict[str, Any]:
        """Normalize a question to structured format.

        Args:
            question: Raw question dict
            index: Question index

        Returns:
            Normalized question dict
        """
        question_id = question.get("id", f"q_{index}")
        question_text = question.get("question", "")
        question_type = question.get("type", "single_choice")
        raw_options = question.get("options", [])
        allow_custom = question.get("allow_custom", False)

        # Normalize options
        normalized_options = []
        if isinstance(raw_options, list):
            for i, opt in enumerate(raw_options):
                normalized_options.append(self._normalize_option(opt, i))

        return {
            "id": question_id,
            "question": question_text,
            "type": question_type,
            "options": normalized_options,
            "allow_custom": allow_custom,
            "placeholder": question.get("placeholder"),
            "default_value": question.get("default_value"),
            "required": question.get("required", True),
        }

    def _format_clarification_message(self, args: dict) -> str:
        """Format the clarification arguments into a user-friendly message.

        This creates a JSON-embedded message that the frontend can parse for wizard rendering.

        Args:
            args: The tool call arguments containing clarification details

        Returns:
            Formatted message string with embedded JSON data
        """
        raw_questions = args.get("questions", [])
        title = args.get("title")
        context = args.get("context")

        # Normalize questions
        normalized_questions = []
        if isinstance(raw_questions, list):
            for i, q in enumerate(raw_questions):
                if isinstance(q, dict):
                    normalized_questions.append(self._normalize_question(q, i))

        # Build structured data for frontend
        clarification_data = {
            "title": title,
            "context": context,
            "questions": normalized_questions,
            "total_questions": len(normalized_questions),
        }

        # Embed structured data as JSON for frontend to parse
        json_data = json.dumps(clarification_data, ensure_ascii=False)

        # Create a human-readable preview for fallback
        preview_parts = []

        if title:
            preview_parts.append(f"📋 {title}")
        if context:
            preview_parts.append(context)

        if normalized_questions:
            preview_parts.append("")
            for i, q in enumerate(normalized_questions, 1):
                q_text = q.get("question", "")
                q_type = q.get("type", "single_choice")
                type_indicator = {
                    "single_choice": "🔘",
                    "multiple_choice": "☑️",
                    "text_input": "✏️",
                    "confirmation": "⚠️",
                }.get(q_type, "❓")
                preview_parts.append(f"  {i}. {type_indicator} {q_text}")

        # Combine: hidden JSON block + human-readable preview
        # Frontend will detect and parse the JSON block for rich rendering
        return f"<!--CLARIFICATION_DATA\n{json_data}\n-->\n" + "\n".join(preview_parts)

    def _handle_clarification(self, request: ToolCallRequest) -> Command:
        """Handle clarification request and return command to interrupt execution.

        Args:
            request: Tool call request

        Returns:
            Command that interrupts execution with the formatted clarification message
        """
        # Extract clarification arguments
        args = request.tool_call.get("args", {})

        print("[ClarificationMiddleware] Intercepted clarification request")
        print(f"[ClarificationMiddleware] Questions count: {len(args.get('questions', []))}")

        # Format the clarification message
        formatted_message = self._format_clarification_message(args)

        # Get the tool call ID
        tool_call_id = request.tool_call.get("id", "")

        # Create a ToolMessage with the formatted questions
        # This will be added to the message history
        tool_message = ToolMessage(
            content=formatted_message,
            tool_call_id=tool_call_id,
            name="ask_clarification",
        )

        # Return a Command that:
        # 1. Adds the formatted tool message
        # 2. Interrupts execution by going to __end__
        # Note: We don't add an extra AIMessage here - the frontend will detect
        # and display ask_clarification tool messages directly
        return Command(
            update={"messages": [tool_message]},
            goto=END,
        )

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Intercept ask_clarification tool calls and interrupt execution (sync version).

        Args:
            request: Tool call request
            handler: Original tool execution handler

        Returns:
            Command that interrupts execution with the formatted clarification message
        """
        # Check if this is an ask_clarification tool call
        if request.tool_call.get("name") != "ask_clarification":
            # Not a clarification call, execute normally
            return handler(request)

        return self._handle_clarification(request)

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """Intercept ask_clarification tool calls and interrupt execution (async version).

        Args:
            request: Tool call request
            handler: Original tool execution handler (async)

        Returns:
            Command that interrupts execution with the formatted clarification message
        """
        # Check if this is an ask_clarification tool call
        if request.tool_call.get("name") != "ask_clarification":
            # Not a clarification call, execute normally
            return await handler(request)

        return self._handle_clarification(request)
