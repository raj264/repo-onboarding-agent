from anthropic import AsyncAnthropic

from onboarding_agent.config import DEFAULT_MODEL
from onboarding_agent.mcp_client import McpToolClient
from onboarding_agent.prompts import SYSTEM_PROMPT

_MAX_TOKENS = 4096


class Agent:
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

    async def run_turn(self, messages: list[dict]) -> list[dict]:
        tools = await self._mcp_client.list_anthropic_tools()

        response = await self._anthropic_client.messages.create(
            model=self._model,
            max_tokens=_MAX_TOKENS,
            system=self._system_prompt,
            tools=tools,
            messages=messages,
        )

        while response.stop_reason == "tool_use":
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

            response = await self._anthropic_client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=self._system_prompt,
                tools=tools,
                messages=messages,
            )

        messages.append({"role": "assistant", "content": response.content})
        return messages

    @staticmethod
    def _final_text(messages: list[dict]) -> str:
        last_content = messages[-1]["content"]
        for block in last_content:
            text = block.text if hasattr(block, "text") else block.get("text")
            block_type = block.type if hasattr(block, "type") else block.get("type")
            if block_type == "text" and text:
                return text
        return ""

    async def ask(self, question: str) -> str:
        messages = [{"role": "user", "content": question}]
        messages = await self.run_turn(messages)
        return self._final_text(messages)

    async def chat_step(self, messages: list[dict], user_input: str) -> tuple[list[dict], str]:
        messages.append({"role": "user", "content": user_input})
        messages = await self.run_turn(messages)
        return messages, self._final_text(messages)
