export function describeToolCall(name: string, args: Record<string, unknown>): string {
  switch (name) {
    case "query_stats":
      return args.player_name ? `Looking up stats for ${args.player_name}…` : "Pulling player stats…"
    case "query_roster":
      if (args.view === "matchup") return "Checking the matchup…"
      if (args.view === "teams") return "Checking league standings…"
      return "Checking your roster…"
    case "search_news":
      return args.query ? `Searching news for "${args.query}"…` : "Searching recent news…"
    default:
      return `Running ${name}…`
  }
}
