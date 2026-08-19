import { useState, type KeyboardEvent } from "react"

export default function ChatInput({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void
  disabled: boolean
}) {
  const [value, setValue] = useState("")

  const submit = () => {
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue("")
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="flex items-end gap-3 border-t border-border bg-surface p-4">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask about your roster, waiver targets, or matchups"
        rows={1}
        disabled={disabled}
        className="max-h-32 flex-1 resize-none rounded-2xl border border-border bg-surface-raised px-4 py-3 text-sm text-text placeholder:text-text-faint focus:border-accent focus:outline-none disabled:opacity-60"
      />
      <button
        onClick={submit}
        disabled={disabled || !value.trim()}
        className="pressable rounded-full bg-accent px-6 py-3 text-sm font-bold text-bg hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-40 disabled:shadow-none"
      >
        {disabled ? "Thinking" : "Send"}
      </button>
    </div>
  )
}
