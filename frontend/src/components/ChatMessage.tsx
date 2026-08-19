import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { Components } from "react-markdown"

const KNOWN_HEADERS = ["Changes to Starters", "Waiver Wire Moves", "People to Keep Your Eye On"]

// Smaller models drift from the requested markdown: they drop the "##" on the three
// section headers, and sometimes emit literal "•" characters (occasionally several run
// together on one line) instead of "-" list items. Repair both before rendering.
function normalizeMarkdown(content: string): string {
  return content
    .split("\n")
    .map((line) => {
      const trimmed = line.trim().replace(/^#+\s*/, "")
      if (KNOWN_HEADERS.includes(trimmed)) return `## ${trimmed}`

      if (line.includes("•")) {
        return line
          .split("•")
          .map((part) => part.trim())
          .filter(Boolean)
          .map((part) => `- ${part}`)
          .join("\n")
      }
      return line
    })
    .join("\n")
}

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mt-6 mb-2.5 font-display soft text-lg font-semibold text-text first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-6 mb-3 font-display soft text-base font-semibold text-accent first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-4 mb-1.5 text-sm font-semibold text-text first:mt-0">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="mb-3 text-sm leading-relaxed text-text-muted last:mb-0">{children}</p>
  ),
  ul: ({ children }) => <ul className="mb-3 space-y-2.5 last:mb-0">{children}</ul>,
  ol: ({ children }) => (
    <ol className="mb-3 ml-5 list-decimal space-y-2.5 text-sm text-text-muted last:mb-0">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="relative pl-5 text-sm leading-relaxed text-text-muted before:absolute before:left-0 before:top-[0.62em] before:h-1.5 before:w-1.5 before:rounded-full before:bg-accent/70">
      {children}
    </li>
  ),
  strong: ({ children }) => <strong className="font-semibold text-text">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="font-medium text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-5 border-border" />,
  blockquote: ({ children }) => (
    <blockquote className="mb-3 rounded-r-xl border-l-2 border-accent/50 bg-surface-raised/60 py-2 pl-4 pr-3 text-sm text-text-muted last:mb-0">
      {children}
    </blockquote>
  ),
  code: ({ children, className }) => {
    if (/language-/.test(className ?? "")) {
      return <code className={`text-[13px] ${className ?? ""}`}>{children}</code>
    }
    return (
      <code className="rounded-md bg-surface-raised px-1.5 py-0.5 text-[13px] text-accent">
        {children}
      </code>
    )
  },
  pre: ({ children }) => (
    <pre className="mb-3 overflow-x-auto rounded-xl bg-surface-raised p-4 font-mono last:mb-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="mb-3 overflow-x-auto rounded-xl border border-border last:mb-0">
      <table className="w-full text-left">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-surface-raised">{children}</thead>,
  th: ({ children }) => (
    <th className="px-4 py-2.5 text-xs font-semibold text-text-muted">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border-t border-border px-4 py-2.5 text-[13px] tabular-nums text-text">
      {children}
    </td>
  ),
}

export function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="max-w-2xl rounded-2xl rounded-tl-md border border-border bg-surface px-5 py-4 shadow-soft">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {normalizeMarkdown(content)}
      </ReactMarkdown>
    </div>
  )
}

export function UserBubble({ content }: { content: string }) {
  return (
    <div className="ml-auto max-w-lg rounded-2xl rounded-tr-md bg-accent/15 px-4 py-3 text-sm font-medium text-text">
      {content}
    </div>
  )
}

export function ToolStatusLine({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2.5 pl-1 text-xs text-text-faint">
      <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
      {label}
    </div>
  )
}
