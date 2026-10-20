import { useState, type FormEvent } from 'react'
import { Send } from 'lucide-react'
import Button from '../common/Button'

export interface ChatMessage {
  role: 'user' | 'assistant'
  text: string
}

export default function ChatPanel({ messages, onSend, placeholder, busy }: {
  messages: ChatMessage[]
  onSend: (text: string) => void
  placeholder?: string
  busy?: boolean
}) {
  const [text, setText] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!text.trim()) return
    onSend(text.trim())
    setText('')
  }
  return (
    <div className="flex flex-col gap-3">
      <div className="flex max-h-64 flex-col gap-2 overflow-y-auto">
        {messages.map((m, i) => (
          <div key={i} className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${m.role === 'user' ? 'self-end bg-accent text-accent-ink' : 'self-start bg-panel2 text-ink'}`}>
            {m.text}
          </div>
        ))}
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder ?? 'Apna sawaal poochho…'} className="input flex-1" />
        <Button type="submit" disabled={busy}><Send className="h-4 w-4" />Send</Button>
      </form>
    </div>
  )
}
