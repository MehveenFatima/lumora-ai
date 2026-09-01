'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  RotateCcw,
  Sparkles,
  Layers,
  BookOpen,
  MessagesSquare,
  AlertTriangle,
  FileText,
  ChevronRight,
  TrendingUp,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import {
  Workspace,
  QuizQuestion,
  QuizResult,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

export default function AdaptiveQuizPage() {
  const params = useParams()
  const router = useRouter()
  const workspaceId = (params?.workspaceId as string) || 'dsa'

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [isAnswerSubmitted, setIsAnswerSubmitted] = useState(false)
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({})
  const [quizResult, setQuizResult] = useState<QuizResult | null>(null)
  const [timerSeconds, setTimerSeconds] = useState(0)

  useEffect(() => {
    async function loadQuizData() {
      const [ws, qs] = await Promise.all([
        workspaceService.getWorkspaceById(workspaceId),
        workspaceService.getQuizQuestions(workspaceId),
      ])
      setWorkspace(ws)
      setQuestions(qs)
    }
    loadQuizData()
  }, [workspaceId])

  useEffect(() => {
    let interval: NodeJS.Timeout
    if (!quizResult) {
      interval = setInterval(() => {
        setTimerSeconds((prev) => prev + 1)
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [quizResult])

  if (questions.length === 0) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8">
        <div className="text-center">
          <Zap className="mx-auto size-8 text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">Preparing adaptive quiz questions for {workspace?.name}...</p>
        </div>
      </div>
    )
  }

  const currentQ = questions[currentIndex]
  const isCorrect = selectedKey === currentQ.correctKey

  const handleSubmitAnswer = () => {
    if (!selectedKey) return
    setIsAnswerSubmitted(true)
    setUserAnswers((prev) => ({ ...prev, [currentQ.id]: selectedKey }))
  }

  const handleNextQuestion = async () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1)
      setSelectedKey(null)
      setIsAnswerSubmitted(false)
    } else {
      // Quiz Finished, calculate results
      const res = await workspaceService.submitQuiz(workspaceId, {
        ...userAnswers,
        [currentQ.id]: selectedKey!,
      })
      setQuizResult(res)
    }
  }

  const handleRestartQuiz = () => {
    setCurrentIndex(0)
    setSelectedKey(null)
    setIsAnswerSubmitted(false)
    setUserAnswers({})
    setQuizResult(null)
    setTimerSeconds(0)
  }

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // ============================================================
  // QUIZ RESULT SCREEN
  // ============================================================
  if (quizResult) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-8 md:py-12">
        <div className="rounded-3xl border border-border bg-card p-6 shadow-card md:p-10 text-center animate-in fade-in zoom-in-95 duration-200">
          <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-glow">
            <Zap className="size-7" />
          </span>

          <h1 className="mt-4 font-display text-2xl font-semibold text-foreground md:text-3xl">
            Adaptive Assessment Completed
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            {workspace?.name} — Performance Breakdown
          </p>

          {/* Key Metrics */}
          <div className="mt-6 grid grid-cols-3 gap-3">
            <div className="rounded-2xl border border-border bg-background p-4">
              <span className="text-[11px] text-muted-foreground">Score</span>
              <p className="mt-1 font-display text-2xl font-bold text-foreground">
                {quizResult.score} / {quizResult.totalQuestions}
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-background p-4">
              <span className="text-[11px] text-muted-foreground">Accuracy</span>
              <p className="mt-1 font-display text-2xl font-bold text-primary">
                {quizResult.accuracyPercentage}%
              </p>
            </div>
            <div className="rounded-2xl border border-border bg-background p-4">
              <span className="text-[11px] text-muted-foreground">Avg Response Time</span>
              <p className="mt-1 font-display text-2xl font-bold text-foreground">
                {quizResult.averageResponseTimeSeconds}s
              </p>
            </div>
          </div>

          {/* Concept Performance Matrix */}
          <div className="mt-6 text-left">
            <h3 className="font-display text-sm font-semibold text-foreground">Concept Performance</h3>
            <div className="mt-3 flex flex-col gap-2">
              {quizResult.conceptPerformance.map((c, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-xl border border-border bg-background p-3 text-xs"
                >
                  <span className="font-medium text-foreground">{c.conceptName}</span>
                  <Badge variant={c.status === 'strong' ? 'success' : 'warning'} size="sm">
                    {c.accuracyPercentage}% Mastery
                  </Badge>
                </div>
              ))}
            </div>
          </div>

          {/* Identified Gaps */}
          {quizResult.knowledgeGapsIdentified.length > 0 && (
            <div className="mt-6 rounded-2xl border border-destructive/20 bg-destructive/5 p-4 text-left">
              <div className="flex items-center gap-2 text-xs font-semibold text-destructive">
                <AlertTriangle className="size-4" />
                <span>Identified Knowledge Gaps</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                The assessment detected uncertainty in:{' '}
                <span className="font-semibold text-foreground">
                  {quizResult.knowledgeGapsIdentified.join(', ')}
                </span>
                .
              </p>
            </div>
          )}

          {/* AI Recommendation */}
          <div className="mt-4 rounded-2xl border border-primary/20 bg-primary/5 p-4 text-left text-xs">
            <div className="flex items-center gap-2 font-semibold text-primary">
              <Sparkles className="size-4" />
              <span>AI Recommendation</span>
            </div>
            <p className="mt-1 text-muted-foreground leading-relaxed">{quizResult.recommendation}</p>
          </div>

          {/* Action Buttons */}
          <div className="mt-8 flex flex-col sm:flex-row gap-3">
            <Link
              href={`/dashboard/workspace/${workspaceId}/tutor`}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary py-3 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
            >
              <MessagesSquare className="size-4" />
              <span>Review Weak Areas with Tutor</span>
            </Link>
            <Link
              href={`/dashboard/workspace/${workspaceId}`}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-border bg-card py-3 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
            >
              <span>Back to Overview</span>
            </Link>
            <button
              onClick={handleRestartQuiz}
              className="flex items-center justify-center gap-2 rounded-xl border border-border bg-card px-4 py-3 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              <RotateCcw className="size-4" />
              <span>Try Again</span>
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ============================================================
  // ACTIVE QUIZ QUESTION SCREEN
  // ============================================================
  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-6 md:py-8">
      <div className="rounded-3xl border border-border bg-card p-6 shadow-soft md:p-8">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border pb-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-xl bg-warning/15 text-warning">
              <Zap className="size-4" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-display text-sm font-semibold text-foreground">{workspace?.name}</h2>
                <Badge variant="neutral" size="sm" className="text-[10px]">
                  {currentQ.topicName}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">Adaptive Mastery Testing</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant="warning" size="md" className="capitalize text-xs font-semibold">
              {currentQ.difficulty}
            </Badge>
            <span className="flex items-center gap-1 text-xs font-medium tabular-nums text-muted-foreground">
              <Clock className="size-3.5" /> {formatTime(timerSeconds)}
            </span>
          </div>
        </div>

        {/* Adaptive Hint Banner */}
        {currentQ.adaptiveHint && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-[11px] text-primary">
            <Sparkles className="size-3.5 shrink-0" />
            <span>{currentQ.adaptiveHint}</span>
          </div>
        )}

        {/* Question Counter & Progress */}
        <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
          <span>Question {currentIndex + 1} of {questions.length}</span>
          <div className="flex gap-1">
            {questions.map((_, i) => (
              <span
                key={i}
                className={cn(
                  'h-1.5 w-4 rounded-full transition-colors',
                  i === currentIndex
                    ? 'bg-primary'
                    : i < currentIndex
                    ? 'bg-primary/50'
                    : 'bg-muted'
                )}
              />
            ))}
          </div>
        </div>

        {/* Question Text */}
        <div className="mt-6">
          <p className="text-sm font-semibold leading-relaxed text-foreground md:text-base">
            {currentQ.question}
          </p>

          {/* Options */}
          <div className="mt-5 flex flex-col gap-2.5">
            {currentQ.options.map((opt) => {
              const isSelected = selectedKey === opt.key
              const showAsCorrect = isAnswerSubmitted && opt.key === currentQ.correctKey
              const showAsWrong = isAnswerSubmitted && isSelected && !isCorrect

              return (
                <button
                  key={opt.key}
                  disabled={isAnswerSubmitted}
                  onClick={() => setSelectedKey(opt.key)}
                  className={cn(
                    'flex items-center gap-3.5 rounded-2xl border p-4 text-left text-xs md:text-sm transition-all',
                    !isAnswerSubmitted && !isSelected && 'border-border bg-background/50 hover:border-primary/40 hover:bg-accent/40',
                    !isAnswerSubmitted && isSelected && 'border-primary bg-primary/10 font-semibold ring-1 ring-primary/40',
                    showAsCorrect && 'border-success/60 bg-success/10 text-foreground font-semibold',
                    showAsWrong && 'border-destructive/60 bg-destructive/10 text-foreground',
                    isAnswerSubmitted && !showAsCorrect && !showAsWrong && 'border-border/60 opacity-60'
                  )}
                >
                  <span
                    className={cn(
                      'flex size-7 shrink-0 items-center justify-center rounded-lg border text-xs font-bold transition-colors',
                      showAsCorrect
                        ? 'border-success bg-success text-success-foreground'
                        : showAsWrong
                        ? 'border-destructive bg-destructive text-destructive-foreground'
                        : isSelected
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-card text-muted-foreground'
                    )}
                  >
                    {showAsCorrect ? <CheckCircle2 className="size-4" /> : showAsWrong ? <XCircle className="size-4" /> : opt.key}
                  </span>
                  <span className="flex-1 text-foreground">{opt.text}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Feedback & Explanation Box */}
        {isAnswerSubmitted && (
          <div
            className={cn(
              'mt-6 rounded-2xl border p-4 text-xs leading-relaxed animate-in fade-in duration-150',
              isCorrect
                ? 'border-success/30 bg-success/5 text-foreground'
                : 'border-destructive/30 bg-destructive/5 text-foreground'
            )}
          >
            <div className="flex items-center gap-2 font-semibold mb-1.5">
              {isCorrect ? (
                <>
                  <CheckCircle2 className="size-4 text-success" />
                  <span className="text-success">Correct Explanation</span>
                </>
              ) : (
                <>
                  <XCircle className="size-4 text-destructive" />
                  <span className="text-destructive">Incorrect — Concept Review</span>
                </>
              )}
            </div>
            <p className="text-muted-foreground">{currentQ.explanation}</p>

            {currentQ.sourceCitation && (
              <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-muted-foreground border-t border-border/60 pt-2">
                <FileText className="size-3 text-primary" />
                <span>Grounded in: <strong className="text-foreground">{currentQ.sourceCitation.documentName}</strong> (Page {currentQ.sourceCitation.pageOrSlide})</span>
              </div>
            )}
          </div>
        )}

        {/* Action Controls */}
        <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
          <span className="text-xs text-muted-foreground">
            Concept Tested: <strong className="text-foreground">{currentQ.conceptTested}</strong>
          </span>

          {!isAnswerSubmitted ? (
            <button
              onClick={handleSubmitAnswer}
              disabled={!selectedKey}
              className="flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-6 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              Submit Answer
            </button>
          ) : (
            <button
              onClick={handleNextQuestion}
              className="flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-6 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
            >
              <span>{currentIndex === questions.length - 1 ? 'View Final Results' : 'Next Question'}</span>
              <ArrowRight className="size-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
