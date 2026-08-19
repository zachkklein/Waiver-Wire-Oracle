import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import type { Components } from "react-markdown"

const KNOWN_HEADERS = ["Changes to Starters", "Waiver Wire Moves", "People to Keep Your Eye On"]

// The model is instructed to emit these as "## Heading" but smaller models sometimes
// drop the markdown prefix — normalize plain-text header lines so they still render as headings.
function normalizeHeaders(content: string): string {
  return content
    .split("\n")
    .map((line) => {
      const trimmed = line.trim().replace(/^#+\s*/, "")
      return KNOWN_HEADERS.includes(trimmed) ? `## ${trimmed}` : line
    })
    .join("\n")
}

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mt-5 mb-2 font-display text-lg font-bold text-text first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-5 mb-2 border-b border-border pb-1.5 font-display text-sm font-bold uppercase tracking-wide text-accent first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-3 mb-1 text-sm font-semibold text-text first:mt-0">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="mb-2.5 text-sm leading-relaxed text-text last:mb-0">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-2.5 ml-4 list-disc space-y-1.5 text-sm text-text last:mb-0">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2.5 ml-4 list-decimal space-y-1.5 text-sm text-text last:mb-0">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed pl-0.5">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold text-text">{children}</strong>,
  em: ({ children }) => <em className="italic text-text-muted">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-accent"
    >
      {children}
    </a>
  ),
  hr: () => <hr className="my-3 border-border" />,
  blockquote: ({ children }) => (
    <blockquote className="mb-2.5 border-l-2 border-accent/40 pl-3 text-sm text-text-muted last:mb-0">
      {children}
    </blockquote>
  ),
  code: ({ children, className }) => {
    const isBlock = /language-/.test(className ?? "")
    if (isBlock) {
      return <code className={`font-mono text-xs ${className ?? ""}`}>{children}</code>
    }
    return (
      <code className="rounded bg-surface-raised px-1 py-0.5 font-mono text-[13px] text-accent">
        {children}
      </code>
    )
  },
  pre: ({ children }) => (
    <pre className="mb-2.5 overflow-x-auto rounded-lg border border-border bg-surface-raised p-3 last:mb-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="mb-2.5 overflow-x-auto rounded-lg border border-border last:mb-0">
      <table className="w-full text-left text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-surface-raised">{children}</thead>,
  th: ({ children }) => (
    <th className="border-b border-border px-3 py-2 font-medium uppercase tracking-wide text-text-faint">
      {children}
    </th>
  ),
  td: ({ children }) => <td className="border-b border-border px-3 py-2 text-text last:border-b-0">{children}</td>,
  tr: ({ children }) => <tr className="last:[&>td]:border-b-0">{children}</tr>,
}

export function AssistantBubble({ content }: { content: string }) {
  return (
    <div className="max-w-2xl rounded-xl rounded-tl-sm border border-border bg-surface px-4 py-3.5">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {normalizeHeaders(content)}
      </ReactMarkdown>
    </div>
  )
}

export function UserBubble({ content }: { content: string }) {
  return (
    <div className="ml-auto max-w-lg rounded-xl rounded-tr-sm bg-accent-dim px-4 py-2.5 text-sm text-text">
      {content}
    </div>
  )
}

export function ToolStatusLine({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-text-faint">
      <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent" />
      {label}
    </div>
  )
}
