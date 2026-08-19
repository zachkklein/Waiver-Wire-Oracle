import { useEffect, useRef, useState } from "react"
import { streamChat } from "../lib/api"
import type { ChatMsg } from "../lib/types"
import { AssistantBubble, UserBubble, ToolStatusLine } from "../components/ChatMessage"
import ChatInput from "../components/ChatInput"
import { describeToolCall } from "../lib/toolLabels"

const SECTIONS = [
  { title: "Changes to Starters", copy: "Who to swap into your lineup, and for whom." },
  { title: "Waiver Wire Moves", copy: "Pickups worth a claim this week." },
  { title: "People to Keep Your Eye On", copy: "Situations that could shift by kickoff." },
]

const STARTERS = [
  "Who should I start at flex this week?",
  "Who should I pick up off waivers?",
  "Any injury news on my starters?",
]

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [streamingContent, setStreamingContent] = useState("")
  const [toolStatus, setToolStatus] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamingContent, toolStatus])

  const send = async (text: string) => {
    if (busy) return
    const next = [...messages, { role: "user" as const, content: text }]
    setMessages(next)
    setBusy(true)
    setError(null)
    setStreamingContent("")
    setToolStatus(null)

    let finalContent = ""
    try {
      for await (const event of streamChat(next)) {
        if (event.type === "token") {
          finalContent += event.content
          setStreamingContent(finalContent)
          // Once prose starts arriving, the tool trail has served its purpose.
          setToolStatus(null)
        } else if (event.type === "tool_call") {
          // Keep the last action on screen between calls — the model spends most
          // of its time generating, and blanking this hides progress.
          setToolStatus(describeToolCall(event.name, event.args))
        } else if (event.type === "error") {
          setError(event.message)
        } else if (event.type === "done") {
          if (finalContent) {
            setMessages((m) => [...m, { role: "assistant", content: finalContent }])
          }
          setStreamingContent("")
          setToolStatus(null)
        }
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-[72vh] min-h-[28rem] flex-col overflow-hidden rounded-2xl border border-border bg-bg shadow-soft md:h-[calc(100vh-9.5rem)]">
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-6">
        {messages.length === 0 && !busy ? (
          <div className="mx-auto max-w-xl py-1">
            <h2 className="font-display soft text-2xl font-semibold text-text">
              Ask the Oracle
            </h2>
            <p className="mt-1.5 text-sm text-text-muted">
              Every answer comes back in three parts.
            </p>

            <div className="mt-5 flex flex-col gap-2.5">
              {SECTIONS.map((s) => (
                <div key={s.title} className="rounded-2xl border border-border bg-surface px-4 py-3">
                  <div className="font-display soft text-base font-semibold text-accent">
                    {s.title}
                  </div>
                  <div className="mt-0.5 text-sm text-text-muted">{s.copy}</div>
                </div>
              ))}
            </div>

            <p className="mt-6 mb-2.5 text-sm font-medium text-text-muted">Start with</p>
            <div className="flex flex-col gap-2">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={busy}
                  className="rounded-2xl border border-border bg-surface px-5 py-3 text-left text-sm font-medium text-text-muted transition-all hover:-translate-y-0.5 hover:border-accent/40 hover:text-accent hover:shadow-lift disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            {messages.map((m, i) =>
              m.role === "user" ? (
                <UserBubble key={i} content={m.content} />
              ) : (
                <AssistantBubble key={i} content={m.content} />
              ),
            )}
            {busy && toolStatus && <ToolStatusLine label={toolStatus} />}
            {busy && streamingContent && <AssistantBubble content={streamingContent} />}
            {busy && !streamingContent && !toolStatus && <ToolStatusLine label="Thinking" />}
            {error && (
              <div className="rounded-2xl bg-status-bad/10 px-5 py-4 text-sm text-status-bad">
                {error}
              </div>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={send} disabled={busy} />
    </div>
  )
}
