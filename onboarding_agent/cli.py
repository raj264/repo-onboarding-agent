import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

from onboarding_agent import indexer
from onboarding_agent.agent_loop import Agent
from onboarding_agent.config import DEFAULT_MODEL, get_anthropic_api_key
from onboarding_agent.mcp_client import McpToolClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="onboarding-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser("index", help="Build the RAG index for a target repo.")
    index_parser.add_argument("target_repo", type=Path)

    ask_parser = subparsers.add_parser("ask", help="Ask a one-shot question about a target repo.")
    ask_parser.add_argument("target_repo", type=Path)
    ask_parser.add_argument("question", type=str)
    _add_shared_flags(ask_parser)

    chat_parser = subparsers.add_parser("chat", help="Start an interactive chat session about a target repo.")
    chat_parser.add_argument("target_repo", type=Path)
    _add_shared_flags(chat_parser)

    return parser


def _add_shared_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--allow-pr", action="store_true", default=False)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--k", type=int, default=5)


def cmd_index(args: argparse.Namespace) -> int:
    stats = indexer.build_index(args.target_repo)
    print(f"Indexed {stats.files_indexed} markdown files ({stats.chunks_indexed} chunks).")
    return 0


async def cmd_ask(args: argparse.Namespace) -> int:
    from anthropic import AsyncAnthropic

    get_anthropic_api_key()
    async with McpToolClient(args.target_repo, allow_pr=args.allow_pr) as mcp_client:
        agent = Agent(mcp_client, AsyncAnthropic(), model=args.model)
        answer = await agent.ask(args.question)
        print(answer)
    return 0


async def cmd_chat(args: argparse.Namespace) -> int:
    from anthropic import AsyncAnthropic

    get_anthropic_api_key()
    async with McpToolClient(args.target_repo, allow_pr=args.allow_pr) as mcp_client:
        agent = Agent(mcp_client, AsyncAnthropic(), model=args.model)
        messages: list[dict] = []
        print("Repo Onboarding Agent. Type 'exit' or 'quit' to stop.")
        while True:
            try:
                user_input = input("you> ")
            except EOFError:
                break
            if user_input.strip().lower() in {"exit", "quit"}:
                break
            messages, answer = await agent.chat_step(messages, user_input)
            print(f"assistant> {answer}")
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "index":
        return cmd_index(args)
    if args.command == "ask":
        return asyncio.run(cmd_ask(args))
    if args.command == "chat":
        return asyncio.run(cmd_chat(args))

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
