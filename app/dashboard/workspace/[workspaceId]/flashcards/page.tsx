'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  Layers,
  Sparkles,
  RotateCcw,
  CheckCircle2,
  HelpCircle,
  Clock,
  ArrowRight,
  ArrowLeft,
  BookOpen,
  FileText,
  Zap,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import {
  Workspace,
  FlashcardDeck,
  Flashcard,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

export default function FlashcardsPage() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [decks, setDecks] = useState<FlashcardDeck[]>([])
  const [selectedDeckId, setSelectedDeckId] = useState<string | null>(null)
  const [cardIndex, setCardIndex] = useState(0)
  const [isRevealed, setIsRevealed] = useState(false)
  const [reviewedCount, setReviewedCount] = useState(0)
  const [deckCompleted, setDeckCompleted] = useState(false)

  useEffect(() => {
    if (!workspaceId) return

    async function loadFlashcards() {
      const [ws, dks] = await Promise.all([
        workspaceService.getWorkspaceById(workspaceId),
        workspaceService.getFlashcardDecks(workspaceId),
      ])
      setWorkspace(ws)
      setDecks(dks)
      if (dks.length > 0) {
        setSelectedDeckId(dks[0].id)
      }
    }
    loadFlashcards()
  }, [workspaceId])

  const currentDeck = decks.find((d) => d.id === selectedDeckId) || decks[0]
  const currentCards = currentDeck?.cards || []
  const currentCard = currentCards[cardIndex]

  const handleRate = (rating: 'again' | 'hard' | 'good' | 'easy') => {
    if (currentCard && currentDeck) {
      workspaceService
        .reviewFlashcard(workspaceId, currentDeck.id, currentCard.id, rating)
        .catch((err) => console.warn('Could not save flashcard review:', err))
    }
    setIsRevealed(false)
    setReviewedCount((prev) => prev + 1)

    if (cardIndex < currentCards.length - 1) {
      setCardIndex((prev) => prev + 1)
    } else {
      setDeckCompleted(true)
    }
  }

  const handleRestartDeck = () => {
    setCardIndex(0)
    setIsRevealed(false)
    setReviewedCount(0)
    setDeckCompleted(false)
  }

  if (!currentDeck || currentCards.length === 0) {
    return (
      <div className="mx-auto w-full max-w-2xl px-4 py-16 text-center">
        <div className="rounded-3xl border border-dashed border-border bg-card/50 p-10">
          <Layers className="mx-auto size-10 text-muted-foreground/60" />
          <h2 className="mt-4 font-display text-lg font-semibold text-foreground">
            No Flashcard Decks Available Yet
          </h2>
          <p className="mt-2 text-xs text-muted-foreground leading-relaxed max-w-md mx-auto">
            Upload course notes or slides in the Sources tab to generate spaced repetition decks for {workspace?.name || 'this workspace'}.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              href={`/dashboard/workspace/${workspaceId}/sources`}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-glow"
            >
              <span>Manage Learning Sources</span>
              <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6 md:px-6 md:py-8">
      {/* Header & Deck Selector */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              Spaced Repetition
            </span>
            <span className="text-muted-foreground">•</span>
            <span className="text-xs text-muted-foreground">{workspace?.name}</span>
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold text-foreground">
            Flashcard Review
          </h1>
        </div>

        {/* Deck Switcher Tabs */}
        <div className="flex flex-wrap gap-2">
          {decks.map((deck) => (
            <button
              key={deck.id}
              onClick={() => {
                setSelectedDeckId(deck.id)
                setCardIndex(0)
                setIsRevealed(false)
                setDeckCompleted(false)
              }}
              className={cn(
                'rounded-xl border px-3.5 py-1.5 text-xs font-semibold transition-all',
                deck.id === currentDeck.id
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:text-foreground'
              )}
            >
              {deck.title} ({deck.dueTodayCount} due)
            </button>
          ))}
        </div>
      </div>

      {/* Main Flashcard Stage */}
      {!deckCompleted ? (
        <div className="mt-8 flex flex-col items-center">
          {/* Deck Progress Bar */}
          <div className="w-full max-w-2xl mb-4 flex items-center justify-between text-xs text-muted-foreground">
            <span>
              Card <strong className="text-foreground">{cardIndex + 1}</strong> of{' '}
              <strong className="text-foreground">{currentCards.length}</strong>
            </span>
            <Badge variant="neutral" size="sm">
              {currentDeck.topicName}
            </Badge>
          </div>

          <div className="w-full max-w-2xl">
            <Progress value={((cardIndex + 1) / currentCards.length) * 100} className="h-1.5 mb-6" />
          </div>

          {/* Interactive Card */}
          <div
            onClick={() => !isRevealed && setIsRevealed(true)}
            className={cn(
              'w-full max-w-2xl min-h-[320px] md:min-h-[380px] rounded-3xl border border-border bg-card p-6 md:p-8 shadow-card flex flex-col justify-between cursor-pointer transition-all duration-200 hover:border-primary/40',
              isRevealed && 'ring-1 ring-primary/30'
            )}
          >
            {/* Top Card Bar */}
            <div className="flex items-center justify-between text-xs text-muted-foreground border-b border-border/70 pb-3">
              <span className="font-semibold uppercase tracking-wider text-primary text-[10px]">
                {isRevealed ? 'Answer & Core Invariants' : 'Question Prompt'}
              </span>
              <span className="flex items-center gap-1 text-[11px]">
                <Clock className="size-3" /> Interval: {currentCard.intervalDays}d
              </span>
            </div>

            {/* Question / Answer Content */}
            <div className="my-auto py-4">
              {!isRevealed ? (
                <div>
                  <h3 className="font-display text-base font-semibold leading-relaxed text-foreground md:text-lg">
                    {currentCard.question}
                  </h3>
                  <p className="mt-4 text-xs text-muted-foreground">
                    Click anywhere or press [Reveal] to see the solution.
                  </p>
                </div>
              ) : (
                <div className="animate-in fade-in duration-200">
                  <p className="text-xs md:text-sm font-medium leading-relaxed text-foreground">
                    {currentCard.answer}
                  </p>

                  {currentCard.keyPoints && (
                    <div className="mt-4 rounded-xl border border-border bg-background p-3.5 text-xs">
                      <span className="font-semibold text-primary text-[11px]">Key Takeaways:</span>
                      <ul className="mt-1 space-y-1 list-disc pl-4 text-muted-foreground text-[11px]">
                        {currentCard.keyPoints.map((pt, i) => (
                          <li key={i}>{pt}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {currentCard.sourceCitation && (
                    <div className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                      <FileText className="size-3 text-primary" />
                      <span>Source: {currentCard.sourceCitation}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Bottom Card Helper */}
            <div className="border-t border-border/70 pt-3 flex items-center justify-between text-[11px] text-muted-foreground">
              <span>Difficulty: <strong className="capitalize text-foreground">{currentCard.difficulty}</strong></span>
              {!isRevealed ? (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                    setIsRevealed(true)
                  }}
                  className="rounded-lg bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow-glow"
                >
                  Reveal Answer
                </button>
              ) : (
                <span className="text-primary font-medium">Rate recall difficulty below</span>
              )}
            </div>
          </div>

          {/* Spaced Repetition Rating Buttons (Only shown when revealed) */}
          {isRevealed && (
            <div className="mt-6 w-full max-w-2xl grid grid-cols-4 gap-2.5 animate-in fade-in duration-150">
              <button
                onClick={() => handleRate('again')}
                className="flex flex-col items-center justify-center rounded-2xl border border-destructive/30 bg-destructive/10 p-3 text-destructive transition-colors hover:bg-destructive/20"
              >
                <span className="text-xs font-bold">Again</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">&lt; 1 day</span>
              </button>

              <button
                onClick={() => handleRate('hard')}
                className="flex flex-col items-center justify-center rounded-2xl border border-warning/30 bg-warning/10 p-3 text-warning transition-colors hover:bg-warning/20"
              >
                <span className="text-xs font-bold">Hard</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">2 days</span>
              </button>

              <button
                onClick={() => handleRate('good')}
                className="flex flex-col items-center justify-center rounded-2xl border border-primary/30 bg-primary/10 p-3 text-primary transition-colors hover:bg-primary/20"
              >
                <span className="text-xs font-bold">Good</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">4 days</span>
              </button>

              <button
                onClick={() => handleRate('easy')}
                className="flex flex-col items-center justify-center rounded-2xl border border-success/30 bg-success/10 p-3 text-success transition-colors hover:bg-success/20"
              >
                <span className="text-xs font-bold">Easy</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">7 days</span>
              </button>
            </div>
          )}
        </div>
      ) : (
        /* Deck Completed Screen */
        <div className="mx-auto mt-10 w-full max-w-lg rounded-3xl border border-border bg-card p-8 shadow-card text-center animate-in fade-in zoom-in-95 duration-200">
          <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-success/15 text-success">
            <CheckCircle2 className="size-7" />
          </span>

          <h2 className="mt-4 font-display text-xl font-semibold text-foreground">
            Deck Review Complete!
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            You reviewed all {currentCards.length} cards in {currentDeck.title}.
          </p>

          <div className="mt-6 rounded-2xl border border-border bg-background p-4 text-left text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-foreground">Estimated Deck Retention:</span>
              <span className="font-bold text-primary tabular-nums">94%</span>
            </div>
            <p className="mt-1.5 text-muted-foreground text-[11px]">
              Spaced repetition intervals have been recalculated. Next review scheduled in 4 days.
            </p>
          </div>

          <div className="mt-6 flex flex-col gap-2.5">
            <button
              onClick={handleRestartDeck}
              className="flex items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
            >
              <RotateCcw className="size-3.5" />
              <span>Review Deck Again</span>
            </button>
            <Link
              href={`/dashboard/workspace/${workspaceId}`}
              className="flex items-center justify-center gap-2 rounded-xl border border-border bg-card py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
            >
              <span>Back to Overview</span>
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
