'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  Sparkles,
  ArrowUp,
  FileText,
  Paperclip,
  CheckCircle2,
  Copy,
  Check,
  RotateCcw,
  ThumbsUp,
  ThumbsDown,
  BookOpen,
  HelpCircle,
  Zap,
  Layers,
  ChevronRight,
  ExternalLink,
  Loader2,
  Info,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import { MarkdownText } from '@/components/workspace/markdown-text'
import {
  Workspace,
  WorkspaceDocument,
  TutorMessage,
  TutorCitation,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

export default function AiTutorPage() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([])
  const [messages, setMessages] = useState<TutorMessage[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [selectedCitation, setSelectedCitation] = useState<TutorCitation | null>(null)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const chatBottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!workspaceId) return

    async function loadTutorData() {
      const [ws, docs, historyData] = await Promise.all([
        workspaceService.getWorkspaceById(workspaceId),
        workspaceService.getDocuments(workspaceId),
        workspaceService.getTutorHistory(workspaceId),
      ])
      setWorkspace(ws)
      setDocuments(docs)
      if (historyData && historyData.messages) {
        setMessages(historyData.messages)
        if (historyData.conversationId) {
          setConversationId(historyData.conversationId)
        }
      }
    }
    loadTutorData()
  }, [workspaceId])

  // Opened from search: put the searched words in the question box, ready to send
  const askParam = useSearchParams().get('ask')
  useEffect(() => {
    if (askParam) setInput(askParam.slice(0, 300))
  }, [askParam])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const handleSendMessage = async (textToSend: string) => {
    const text = textToSend.trim()
    if (!text || isTyping) return

    setInput('')
    setIsTyping(true)

    // Add temporary user message
    const tempUserMsg: TutorMessage = {
      id: `temp_u_${Date.now()}`,
      workspaceId,
      conversationId: conversationId || undefined,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    setMessages((prev) => [...prev, tempUserMsg])

    try {
      const assistantMsg = await workspaceService.sendTutorMessage(
        workspaceId,
        text,
        conversationId || undefined
      )
      if (assistantMsg.conversationId && !conversationId) {
        setConversationId(assistantMsg.conversationId)
      }
      setMessages((prev) => [...prev.filter((m) => m.id !== tempUserMsg.id), tempUserMsg, assistantMsg])
    } catch (err) {
      console.error('Failed to send tutor message:', err)
    } finally {
      setIsTyping(false)
    }
  }

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  return (
    <div className="flex h-[calc(100dvh-4rem)] w-full overflow-hidden bg-background">
      {/* LEFT PANE: Grounded Sources Sidebar (Hidden on small screens) */}
      <aside className="hidden lg:flex w-72 shrink-0 flex-col border-r border-border bg-card/40 p-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2">
            <FileText className="size-4 text-primary" />
            <span className="text-xs font-semibold text-foreground">Workspace Sources</span>
          </div>
          <Badge variant="neutral" size="sm">
            {documents.length} Indexed
          </Badge>
        </div>

        <p className="mt-2 text-[11px] text-muted-foreground leading-relaxed">
          The AI Tutor answers exclusively based on citations retrieved from these workspace documents.
        </p>

        <div className="mt-4 flex flex-1 flex-col gap-2 overflow-y-auto pr-1">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="rounded-xl border border-border bg-background p-3 text-xs transition-colors hover:border-primary/40"
            >
              <div className="flex items-start justify-between gap-1.5">
                <span className="font-semibold text-foreground truncate max-w-[150px]">{doc.title}</span>
                <span className="text-[9px] uppercase font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                  {doc.type}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground truncate">{doc.filename}</p>
              <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground">
                <span>{doc.pagesCount} pages / slides</span>
                <span className="text-success flex items-center gap-1 font-medium">
                  <CheckCircle2 className="size-2.5" /> Ready
                </span>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-auto pt-3 border-t border-border">
          <Link
            href={`/dashboard/workspace/${workspaceId}/sources`}
            className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-border bg-card py-2 text-xs font-medium text-foreground transition-colors hover:bg-accent/40"
          >
            <span>Manage Sources Library</span>
            <ExternalLink className="size-3 text-muted-foreground" />
          </Link>
        </div>
      </aside>

      {/* CENTER PANE: Active Conversation Stream */}
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Tutor Sub-Header */}
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur md:px-6">
          <div className="flex items-center gap-2">
            <span className="flex size-6 items-center justify-center rounded-md bg-primary/10 text-primary">
              <Sparkles className="size-3.5" />
            </span>
            <span className="text-xs font-semibold text-foreground">
              AI Tutor — Grounded in {workspace?.name || 'Workspace'}
            </span>
            <Badge variant="success" size="sm" className="text-[10px]">
              Active RAG Memory
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href={`/dashboard/workspace/${workspaceId}/quiz`}
              className="hidden sm:inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              <Zap className="size-3 text-warning" /> Quiz Me
            </Link>
          </div>
        </header>

        {/* Message Thread */}
        <div className="flex-1 space-y-5 overflow-y-auto p-4 md:p-6">
          {messages.length === 0 && !isTyping && (
            <div className="flex h-full flex-col items-center justify-center py-12 text-center animate-in fade-in duration-200">
              <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-glow">
                <Sparkles className="size-7" />
              </div>
              <h3 className="mt-4 font-display text-base font-semibold text-foreground">
                AI Tutor — {workspace?.name || 'Workspace'}
              </h3>
              <p className="mt-1.5 max-w-md text-xs text-muted-foreground leading-relaxed">
                {documents.length > 0
                  ? `Ask any question grounded in your ${documents.length} indexed workspace resources. LumoraAI will retrieve relevant passages and provide citations.`
                  : `No documents uploaded to this workspace yet. Upload lecture notes or textbooks in the Sources tab, or ask a question to get started.`}
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                <button
                  onClick={() => handleSendMessage('Give me a high-level conceptual overview of the key topics in this workspace.')}
                  className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
                >
                  💡 Conceptual Overview
                </button>
                <button
                  onClick={() => handleSendMessage('What are the foundational prerequisite concepts I should review first?')}
                  className="rounded-full border border-border bg-card px-3.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
                >
                  🎯 Prerequisite Foundations
                </button>
              </div>
            </div>
          )}

          {messages.map((m) => {
            const isUser = m.role === 'user'
            return (
              <div
                key={m.id}
                className={cn('flex flex-col gap-2 max-w-3xl', isUser ? 'ml-auto items-end' : 'mr-auto items-start')}
              >
                {/* Message Bubble */}
                <div
                  className={cn(
                    'rounded-2xl p-4 text-xs md:text-[13px] leading-relaxed shadow-soft',
                    isUser
                      ? 'rounded-br-sm bg-primary text-primary-foreground font-medium'
                      : 'rounded-bl-sm border border-border bg-card text-foreground'
                  )}
                >
                  {isUser ? (
                    <div className="whitespace-pre-wrap">{m.content}</div>
                  ) : (
                    <MarkdownText content={m.content} />
                  )}
                </div>

                {/* Sources & Citations Box (For Assistant messages) */}
                {!isUser && m.citations && m.citations.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="text-[11px] font-semibold text-muted-foreground flex items-center gap-1">
                      <FileText className="size-3 text-primary" /> Sources Cited:
                    </span>
                    {m.citations.map((cit) => (
                      <button
                        key={cit.id}
                        onClick={() => setSelectedCitation(cit)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent/40 hover:text-foreground"
                      >
                        <span className="font-medium text-foreground">{cit.documentName}</span>
                        <span>• Page {cit.pageOrSlide}</span>
                      </button>
                    ))}
                  </div>
                )}

                {/* Action Toolbar on Assistant Messages */}
                {!isUser && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-1 text-[11px] text-muted-foreground">
                    <button
                      onClick={() => handleCopy(m.id, m.content)}
                      className="inline-flex items-center gap-1 rounded-lg px-2 py-1 transition-colors hover:bg-accent/50 hover:text-foreground"
                    >
                      {copiedId === m.id ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
                      <span>{copiedId === m.id ? 'Copied' : 'Copy'}</span>
                    </button>

                    <button
                      onClick={() => handleSendMessage(`Explain "${m.content.slice(0, 50)}..." in simpler terms.`)}
                      className="inline-flex items-center gap-1 rounded-lg px-2 py-1 transition-colors hover:bg-accent/50 hover:text-foreground"
                    >
                      <BookOpen className="size-3" />
                      <span>Explain Simpler</span>
                    </button>

                    <button
                      onClick={() => handleSendMessage(`Give a concrete code example demonstrating this concept.`)}
                      className="inline-flex items-center gap-1 rounded-lg px-2 py-1 transition-colors hover:bg-accent/50 hover:text-foreground"
                    >
                      <Zap className="size-3" />
                      <span>Give Example</span>
                    </button>

                    <button
                      onClick={() => handleSendMessage(`Quiz me on the key points of this explanation.`)}
                      className="inline-flex items-center gap-1 rounded-lg px-2 py-1 transition-colors hover:bg-accent/50 hover:text-foreground"
                    >
                      <HelpCircle className="size-3" />
                      <span>Quiz Me</span>
                    </button>
                  </div>
                )}

                {/* Suggested Follow-Ups */}
                {!isUser && m.suggestedFollowUps && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {m.suggestedFollowUps.map((sug, i) => (
                      <button
                        key={i}
                        onClick={() => handleSendMessage(sug)}
                        className="rounded-full border border-border bg-card/80 px-3 py-1 text-[11px] text-muted-foreground transition-all hover:border-primary/50 hover:bg-accent/40 hover:text-foreground"
                      >
                        {sug}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )
          })}

          {isTyping && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground animate-pulse">
              <Loader2 className="size-3.5 animate-spin text-primary" />
              <span>Retrieving relevant chunks & formulating grounded response...</span>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>

        {/* Input Bar */}
        <div className="border-t border-border bg-card p-3 md:p-4">
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSendMessage(input)
            }}
            className="flex items-center gap-2 rounded-2xl border border-input bg-background px-3 py-2 transition-all focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask anything about ${workspace?.name || 'your sources'}...`}
              className="flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground/60 outline-none md:text-sm"
              aria-label="Message AI tutor"
            />
            <button
              type="submit"
              disabled={!input.trim() || isTyping}
              className="flex size-8 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-40"
              aria-label="Send message"
            >
              <ArrowUp className="size-4" />
            </button>
          </form>
        </div>
      </section>

      {/* RIGHT PANE / CITATION EXCERPT DRAWER */}
      {selectedCitation && (
        <aside className="w-80 shrink-0 border-l border-border bg-card p-5 animate-in slide-in-from-right-5 duration-150 flex flex-col">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <span className="text-xs font-semibold text-foreground">Source Citation Preview</span>
            <button
              onClick={() => setSelectedCitation(null)}
              className="text-muted-foreground hover:text-foreground text-xs"
            >
              Close
            </button>
          </div>

          <div className="mt-4 flex-1 space-y-3 overflow-y-auto">
            <div className="rounded-xl border border-border bg-background p-3">
              <span className="text-[10px] font-semibold text-primary uppercase">Referenced Document</span>
              <p className="mt-1 text-xs font-bold text-foreground">{selectedCitation.documentName}</p>
              <p className="text-[11px] text-muted-foreground">Page / Slide {selectedCitation.pageOrSlide}</p>
            </div>

            <div className="rounded-xl border border-border bg-background p-3">
              <span className="text-[10px] font-semibold text-muted-foreground uppercase">Extracted Excerpt</span>
              <blockquote className="mt-1 text-xs leading-relaxed text-foreground italic">
                &ldquo;{selectedCitation.excerpt}&rdquo;
              </blockquote>
            </div>

            <div className="rounded-xl border border-border bg-background p-3 text-[11px]">
              <span className="font-semibold text-foreground">Relevance Confidence:</span>
              <div className="mt-1 flex items-center gap-2">
                <Progress value={selectedCitation.relevanceScore * 100} className="h-1.5 flex-1" />
                <span className="font-bold text-primary">{Math.round(selectedCitation.relevanceScore * 100)}%</span>
              </div>
            </div>
          </div>
        </aside>
      )}
    </div>
  )
}
