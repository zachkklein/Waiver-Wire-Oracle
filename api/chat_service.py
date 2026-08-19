# Streaming variant of agent/chat.py's tool-calling loop, for the web chat endpoint.
# Reuses the same system prompt, tool schemas, and tool executor as the CLI agent —
# only the OpenRouter call itself (stream=True) and the event framing are different.
import json
from typing import Iterator

from openai import OpenAI

import config
from agent.chat import SYSTEM_PROMPT, TOOLS, execute_tool


def _new_client() -> OpenAI:
    return OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)


def stream_chat(history: list[dict]) -> Iterator[dict]:
    """Runs the tool-calling loop against OpenRouter, yielding event dicts as it goes:
    tool_call, tool_result, token, done, error."""
    if not config.OPENROUTER_API_KEY:
        yield {"type": "error", "message": "OPENROUTER_API_KEY must be set in .env"}
        return

    client = _new_client()
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

    try:
        while True:
            stream = client.chat.completions.create(
                model=config.OPENROUTER_MODEL,
                messages=messages,
                tools=TOOLS,
                stream=True,
            )

            content = ""
            # tool call deltas arrive chunked by index; accumulate id/name/arguments here
            pending_calls: dict[int, dict] = {}
            finish_reason = None

            for chunk in stream:
                choice = chunk.choices[0]
                delta = choice.delta
                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                if delta.content:
                    content += delta.content
                    yield {"type": "token", "content": delta.content}

                for tc in delta.tool_calls or []:
                    entry = pending_calls.setdefault(
                        tc.index, {"id": None, "name": "", "arguments": ""}
                    )
                    if tc.id:
                        entry["id"] = tc.id
                    if tc.function and tc.function.name:
                        entry["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        entry["arguments"] += tc.function.arguments

            if finish_reason != "tool_calls" or not pending_calls:
                messages.append({"role": "assistant", "content": content})
                yield {"type": "done"}
                return

            tool_calls = [pending_calls[i] for i in sorted(pending_calls)]
            messages.append(
                {
                    "role": "assistant",
                    "content": content or None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {"name": call["name"], "arguments": call["arguments"]},
                        }
                        for call in tool_calls
                    ],
                }
            )

            for call in tool_calls:
                args = json.loads(call["arguments"] or "{}")
                yield {"type": "tool_call", "name": call["name"], "args": args}
                result = execute_tool(call["name"], args)
                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": result}
                )
                yield {"type": "tool_result", "name": call["name"]}
    except Exception as exc:
        yield {"type": "error", "message": str(exc)}
