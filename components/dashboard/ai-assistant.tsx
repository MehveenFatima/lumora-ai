'use client'

import { useRef, useState } from 'react'
import { Sparkles, ArrowUp, FileText, Paperclip } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

type Message = {
  role: 'user' | 'assistant'
  text: string
  sources?: string[]
}

const initialMessages: Message[] = [
  {
    role: 'user',
    text: 'Explain deadlock and the 4 Coffman conditions from my OS notes.',
  },
  {
    role: 'assistant',
    text: 'A deadlock is a state where processes are blocked, each waiting on a resource held by another. All four Coffman conditions must hold simultaneously: mutual exclusion, hold-and-wait, no preemption, and circular wait.',
    sources: ['OS_Unit3_Notes.pdf', 'Galvin_Ch8.pdf'],
  },
]

const suggestions = ['Summarize this chapter', 'Generate 10 flashcards', 'Quiz me on Unit 3']

export function AiAssistant() {
  const [messages, setMessages] = useState<Message[]>(initialMessages)
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  function send(text: string) {
    const value = text.trim()
    if (!value) return
    setMessages((prev) => [
      ...prev,
      { role: 'user', text: value },
      {
        role: 'assistant',
        text: 'Analyzing your documents with retrieval-augmented generation… I found 3 relevant passages and drafted a grounded explanation.',
        sources: ['OS_Unit3_Notes.pdf'],
      },
    ])
    setInput('')
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
    })
  }

  return (
    <section className="flex h-full flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-soft">
      <header className="flex items-center gap-2.5 border-b border-border px-5 py-4">
        <span className="flex size-8 items-center justify-center rounded-lg bg-primary/12 text-primary">
          <Sparkles className="size-4" />
        </span>
        <div className="flex-1">
          <h3 className="font-display text-[15px] font-semibold text-foreground">AI Tutor</h3>
          <p className="text-[12px] text-muted-foreground">Grounded in your documents (RAG)</p>
        </div>
        <Badge variant="success" size="sm">
          <span className="size-1.5 rounded-full bg-success" />
          Online
        </Badge>
      </header>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {messages.map((m, i) => (
          <div key={i} className={cn('flex flex-col gap-1.5', m.role === 'user' ? 'items-end' : 'items-start')}>
            <div
              className={cn(
                'max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed',
                m.role === 'user'
                  ? 'rounded-br-md bg-primary text-primary-foreground'
                  : 'rounded-bl-md border border-border bg-muted/60 text-foreground',
              )}
            >
              {m.text}
            </div>
            {m.sources ? (
              <div className="flex flex-wrap gap-1.5">
                {m.sources.map((s) => (
                  <span
                    key={s}
                    className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-2 py-0.5 text-[11px] text-muted-foreground"
                  >
                    <FileText className="size-3 text-primary" />
                    {s}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ))}
      </div>

      <div className="border-t border-border p-3">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="rounded-full border border-border bg-card px-2.5 py-1 text-[12px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            >
              {s}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            send(input)
          }}
          className="flex items-center gap-2 rounded-xl border border-input bg-background px-2 py-1.5 transition-colors focus-within:border-ring focus-within:ring-4 focus-within:ring-ring/12"
        >
          <button type="button" className="flex size-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground" aria-label="Attach document">
            <Paperclip className="size-4" />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
                e.preventDefault()
                send(input)
              }
            }}
            placeholder="Ask anything about your documents..."
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/70 outline-none"
            aria-label="Message the AI tutor"
          />
          <button
            type="submit"
            className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
            disabled={!input.trim()}
            aria-label="Send message"
          >
            <ArrowUp className="size-4" strokeWidth={2.5} />
          </button>
        </form>
      </div>
    </section>
  )
}
