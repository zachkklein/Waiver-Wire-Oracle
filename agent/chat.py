# Agent loop with tool-calling, running on OpenRouter (OpenAI-compatible API).
import json
import os
import sys

from openai import OpenAI

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from tools import query_roster, query_stats, search_news

SYSTEM_PROMPT = """\
You are Waiver Wire Oracle, a personal fantasy football assistant for a single \
ESPN fantasy league. You help your user make roster, start/sit, and waiver-wire \
decisions by combining three data sources through tools:

- query_stats: weekly and aggregated NFL player stats (yards, TDs, targets, \
fantasy points).
- query_roster: the user's ESPN league data — their roster, league standings, \
and weekly matchups.
- search_news: semantic search over recently ingested NFL news (injuries, \
roster moves, beat-reporter buzz).

Always use these tools to look up real data rather than relying on your own \
knowledge of players or stats — your training data can be stale and this league's \
roster/scoring is specific to the user. All data reflects whenever the ingest \
scripts (espn_sync.py, stats_sync.py, news_sync.py) were last run, not necessarily \
live — mention that if it seems relevant (e.g. scores showing 0 before games start).

Be direct and concise. Never use emojis.

Structure every response as markdown with these three sections, in this order, as \
level-2 headings (##) using exactly this text:

## Changes to Starters
## Waiver Wire Moves
## People to Keep Your Eye On

Under each header, use a short bullet list. Each bullet bolds the player's name \
(and, where relevant, the player being replaced) and gives at most one or two \
sentences of reasoning (recent performance, matchup, injury news) — no more. If a \
section has nothing to report, write "None this week." under that header rather \
than omitting the header. The response is rendered as markdown in a web UI that \
supports tables, links, and code — use a markdown table instead of prose when \
comparing stat lines across multiple players, and link player/article names when \
a source URL is available from a tool result.\
"""


def _to_openai_tool(tool_schema: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool_schema["name"],
            "description": tool_schema["description"],
            "parameters": tool_schema["input_schema"],
        },
    }


TOOLS = [
    _to_openai_tool(query_stats.TOOL_SCHEMA),
    _to_openai_tool(query_roster.TOOL_SCHEMA),
    _to_openai_tool(search_news.TOOL_SCHEMA),
]

TOOL_FUNCTIONS = {
    "query_stats": query_stats.run_tool,
    "query_roster": query_roster.run_tool,
    "search_news": search_news.run_tool,
}


def execute_tool(name: str, tool_input: dict) -> str:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Error: unknown tool '{name}'"

    try:
        result = func(tool_input)
        return json.dumps(result, default=str)
    except Exception as exc:
        return f"Error running {name}: {exc}"


def run_turn(client: OpenAI, messages: list[dict]) -> list[dict]:
    while True:
        response = client.chat.completions.create(
            model=config.OPENROUTER_MODEL,
            messages=messages,
            tools=TOOLS,
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            print(message.content or "")
            return messages

        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments or "{}")
            print(f"  [{tool_call.function.name}({json.dumps(args)})]")
            result = execute_tool(tool_call.function.name, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )


def chat_loop() -> None:
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY must be set in .env")

    client = OpenAI(base_url=config.OPENROUTER_BASE_URL, api_key=config.OPENROUTER_API_KEY)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("Waiver Wire Oracle — ask about your roster, stats, or news. Type 'exit' to quit.\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        messages.append({"role": "user", "content": user_input})
        print("Oracle: ", end="", flush=True)
        messages = run_turn(client, messages)


if __name__ == "__main__":
    chat_loop()
