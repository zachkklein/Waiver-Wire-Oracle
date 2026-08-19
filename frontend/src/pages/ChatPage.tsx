import { useEffect, useRef, useState } from "react"
import { streamChat } from "../lib/api"
import type { ChatMsg } from "../lib/types"
import { AssistantBubble, UserBubble, ToolStatusLine } from "../components/ChatMessage"
import ChatInput from "../components/ChatInput"
import { describeToolCall } from "../lib/toolLabels"

const WELCOME = `Ask me about start/sit decisions, waiver pickups, or what's happening around your league. Every answer covers changes to starters, waiver wire moves, and players to watch.`

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
        } else if (event.type === "tool_call") {
          setToolStatus(describeToolCall(event.name, event.args))
        } else if (event.type === "tool_result") {
          setToolStatus(null)
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
    <div className="flex h-[calc(100vh-7rem)] flex-col rounded-xl border border-border bg-surface">
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="mx-auto max-w-lg pt-10 text-center text-sm text-text-muted">{WELCOME}</div>
        )}
        <div className="flex flex-col gap-4">
          {messages.map((m, i) =>
            m.role === "user" ? (
              <UserBubble key={i} content={m.content} />
            ) : (
              <AssistantBubble key={i} content={m.content} />
            ),
          )}
          {busy && toolStatus && <ToolStatusLine label={toolStatus} />}
          {busy && streamingContent && <AssistantBubble content={streamingContent} />}
          {error && <div className="text-sm text-status-bad">{error}</div>}
        </div>
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={send} disabled={busy} />
    </div>
  )
}
