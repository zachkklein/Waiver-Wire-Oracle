# CLI entrypoint.
import argparse

import config
from agent import chat
from ingest import espn_sync, news_sync, stats_sync


def _sync_espn(args: argparse.Namespace) -> None:
    # The CLI is single-user by definition, so the league comes from local settings.
    # The hosted worker calls espn_sync.run(ctx) with a league from the database instead.
    league, self_team_id = espn_sync.run(config.load_league_ctx())
    total_players = sum(len(t.roster) for t in league.teams)
    print(f"Synced {len(league.teams)} teams, {total_players} rostered players, "
          f"matchups for week {league.current_week}.")
    if self_team_id is None:
        print("Could not match ESPN_SWID to a team in this league; self-team flag not set.")


def _sync_stats(args: argparse.Namespace) -> None:
    count = stats_sync.run(args.years or None)
    print(f"Synced {count} player-week stat lines.")


def _sync_news(args: argparse.Namespace) -> None:
    count = news_sync.run(args.feeds or None)
    print(f"Synced {count} news chunks.")


SYNC_TARGETS = {"espn": _sync_espn, "stats": _sync_stats, "news": _sync_news}


def cmd_sync(args: argparse.Namespace) -> None:
    targets = args.targets or list(SYNC_TARGETS)
    invalid = [t for t in targets if t not in SYNC_TARGETS]
    if invalid:
        raise SystemExit(
            f"Invalid sync target(s): {', '.join(invalid)}. "
            f"Choose from: {', '.join(SYNC_TARGETS)}."
        )

    failed = []
    for target in targets:
        print(f"== Syncing {target} ==")
        try:
            SYNC_TARGETS[target](args)
        except Exception as exc:
            print(f"FAILED: {exc}")
            failed.append(target)

    if failed:
        raise SystemExit(f"\n{len(failed)}/{len(targets)} sync target(s) failed: {', '.join(failed)}")


def cmd_chat(args: argparse.Namespace) -> None:
    chat.chat_loop()


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=args.port, reload=args.reload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="waiver-wire-oracle", description="Waiver Wire Oracle CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Sync data from ESPN, nflverse, and RSS feeds")
    sync_parser.add_argument(
        "targets",
        nargs="*",
        help="Which sources to sync: espn, stats, news (default: all three)",
    )
    sync_parser.add_argument(
        "--years", nargs="*", type=int, help="Season years for stats sync (default: ESPN_SEASON)"
    )
    sync_parser.add_argument(
        "--feeds", nargs="*", help="RSS feed URLs for news sync (default: RSS_FEED_URLS)"
    )
    sync_parser.set_defaults(func=cmd_sync)

    chat_parser = subparsers.add_parser("chat", help="Start the chat agent")
    chat_parser.set_defaults(func=cmd_chat)

    serve_parser = subparsers.add_parser("serve", help="Run the web app (API + frontend)")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true", help="Auto-reload on code changes")
    serve_parser.set_defaults(func=cmd_serve)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
