"""The Claude tool-use loop: feeds messages + the MCP tool schemas to the Anthropic API,
executes whatever tools Claude asks for via the MCP client, feeds the results back, and
repeats until Claude returns a final text answer (or a safety cap is hit).
"""

import asyncio
import logging

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic

from onboarding_agent.config import DEFAULT_MODEL
from onboarding_agent.mcp_client import McpToolClient
from onboarding_agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_MAX_TOKENS = 4096
_MAX_TOOL_ITERATIONS = 10
_MAX_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 1.0
_RETRYABLE_STATUS_CODES = {429, 529}


def _is_retryable(exc: Exception) -> bool:
    """Transient errors worth retrying: connection issues, rate limits, and
    5xx/overloaded responses. Anything else (bad request, auth, etc.) fails fast.
    """
    if isinstance(exc, APIConnectionError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in _RETRYABLE_STATUS_CODES or exc.status_code >= 500
    return False


class Agent:
    """Ties one `McpToolClient` (the tools) to one `AsyncAnthropic` client (the brain)."""

    def __init__(
        self,
        mcp_client: McpToolClient,
        anthropic_client: AsyncAnthropic,
        model: str = DEFAULT_MODEL,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self._mcp_client = mcp_client
        self._anthropic_client = anthropic_client
        self._model = model
        self._system_prompt = system_prompt

    async def _create_response(self, messages: list[dict], tools: list[dict]):
        """Calls `messages.create`, retrying transient failures with exponential
        backoff (1s, 2s, ... up to `_MAX_RETRY_ATTEMPTS` attempts total). Non-retryable
        errors (e.g. 400 bad request, auth failure) propagate immediately.
        """
        for attempt in range(_MAX_RETRY_ATTEMPTS):
            try:
                return await self._anthropic_client.messages.create(
                    model=self._model,
                    max_tokens=_MAX_TOKENS,
                    system=self._system_prompt,
                    tools=tools,
                    messages=messages,
                )
            except Exception as exc:
                if not _is_retryable(exc) or attempt == _MAX_RETRY_ATTEMPTS - 1:
                    raise
                delay = _RETRY_BASE_DELAY_SECONDS * (2**attempt)
                logger.warning("Anthropic API call failed (%s), retrying in %.0fs...", exc, delay)
                await asyncio.sleep(delay)

    async def run_turn(self, messages: list[dict]) -> list[dict]:
        """Drives the tool-use loop for one turn: calls Claude, executes any requested
        tool calls via MCP, appends the results, and calls Claude again - repeating until
        `stop_reason` is no longer `"tool_use"` (a final answer) or the iteration cap is
        hit. Mutates and returns `messages` so callers can keep accumulating history.
        """
        tools = await self._mcp_client.list_anthropic_tools()
        response = await self._create_response(messages, tools)

        iterations = 0
        while response.stop_reason == "tool_use":
            iterations += 1
            if iterations > _MAX_TOOL_ITERATIONS:
                # Guards against a model that keeps calling tools without ever
                # producing a final answer - bail out with an explicit message
                # instead of looping (and burning API calls) forever.
                messages.append({"role": "assistant", "content": response.content})
                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Stopped after {_MAX_TOOL_ITERATIONS} tool calls without "
                                    "reaching a final answer. Try a more specific question."
                                ),
                            }
                        ],
                    }
                )
                return messages

            # Execute every tool_use block in this response. A tool exception is
            # reported back to Claude as a tool_result with is_error=True rather than
            # raised, so the model can see what went wrong and adjust its approach.
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    text, is_error = await self._mcp_client.call_tool(block.name, block.input)
                except Exception as exc:
                    text, is_error = str(exc), True

                tool_result = {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": text,
                }
                if is_error:
                    tool_result["is_error"] = True
                tool_results.append(tool_result)

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            response = await self._create_response(messages, tools)

        messages.append({"role": "assistant", "content": response.content})
        return messages

    @staticmethod
    def _final_text(messages: list[dict]) -> str:
        """Extracts the first text block from the last assistant message. Handles both
        SDK content-block objects (real responses) and plain dicts (as used in tests).
        """
        last_content = messages[-1]["content"]
        for block in last_content:
            text = block.text if hasattr(block, "text") else block.get("text")
            block_type = block.type if hasattr(block, "type") else block.get("type")
            if block_type == "text" and text:
                return text
        return ""

    async def ask(self, question: str) -> str:
        """One-shot question -> final answer, with no carried conversation history."""
        messages = [{"role": "user", "content": question}]
        messages = await self.run_turn(messages)
        return self._final_text(messages)

    async def chat_step(self, messages: list[dict], user_input: str) -> tuple[list[dict], str]:
        """Appends `user_input` to existing `messages`, runs a turn, and returns the
        updated history alongside the answer so the caller can pass it back in next time.
        """
        messages.append({"role": "user", "content": user_input})
        messages = await self.run_turn(messages)
        return messages, self._final_text(messages)
