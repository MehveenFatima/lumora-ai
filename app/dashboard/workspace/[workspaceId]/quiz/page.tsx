'use client'

import { useState, useEffect, useRef } from 'react'
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
  Loader2,
  Award,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import { tutorApiClient } from '@/lib/api/tutor-api-client'
import { Workspace } from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

interface PublicQuestionOption {
  key?: string
  option_id?: string
  text: string
}

interface SourceCitation {
  document_id?: string
  document_name: string
  page_or_slide: number
  excerpt?: string
}

interface PublicQuizQuestion {
  id: string
  session_id?: string
  quiz_session_id?: string
  workspace_id: string
  question_text: string
  options: PublicQuestionOption[]
  difficulty?: number
  difficulty_level?: number
  concept?: string
  concept_tag?: string
  topic?: string
  topic_id?: string
  question_order?: number
  question_index?: number
  document_name?: string
  page_number?: number
  source_citations?: SourceCitation[]
  explanation_hint?: string
}

interface AttemptResult {
  is_correct: boolean
  correct_option: string
  explanation: string
  earned_score?: number
  previous_difficulty?: number
  new_difficulty?: number
  adaptation_reason?: string
  document_name?: string
  page_number?: number
  source_excerpt?: string
  source_citations?: SourceCitation[]
  is_quiz_completed: boolean
  next_question?: PublicQuizQuestion | null
}

interface ConceptPerformance {
  concept_name: string
  attempts: number
  correct: number
  accuracy_percentage: number
  mastery_status: 'mastered' | 'proficient' | 'review_needed'
}

interface QuizSummary {
  session_id: string
  workspace_id: string
  total_questions: number
  correct_answers: number
  score: number
  accuracy_percentage: number
  average_response_time_seconds: number
  final_difficulty_level: number
  concept_breakdown: ConceptPerformance[]
  knowledge_gaps: string[]
  strengths: string[]
  recommendations: string[]
}

const DIFFICULTY_LABELS: Record<number, { name: string; variant: 'neutral' | 'success' | 'warning' | 'destructive' }> = {
  1: { name: 'Level 1: Foundational', variant: 'neutral' },
  2: { name: 'Level 2: Intermediate', variant: 'warning' },
  3: { name: 'Level 3: Advanced', variant: 'warning' },
  4: { name: 'Level 4: Mastery', variant: 'success' },
  5: { name: 'Level 5: Expert', variant: 'destructive' },
}

export default function AdaptiveQuizPage() {
  const params = useParams()
  const router = useRouter()
  const workspaceId = params?.workspaceId as string

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentQuestion, setCurrentQuestion] = useState<PublicQuizQuestion | null>(null)
  const [questionOrder, setQuestionOrder] = useState<number>(1)
  const [totalTargetQuestions, setTotalTargetQuestions] = useState<number>(5)
  const [currentDifficulty, setCurrentDifficulty] = useState<number>(2)

  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false)
  const [isAnswerSubmitted, setIsAnswerSubmitted] = useState<boolean>(false)
  const [attemptResult, setAttemptResult] = useState<AttemptResult | null>(null)
  const [quizSummary, setQuizSummary] = useState<QuizSummary | null>(null)

  const [isLoading, setIsLoading] = useState<boolean>(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [timerSeconds, setTimerSeconds] = useState<number>(0)

  const questionStartTimeRef = useRef<number>(performance.now())

  // Initialize workspace & quiz session
  const startQuizSession = async () => {
    if (!workspaceId) return
    setIsLoading(true)
    setErrorMessage(null)
    setQuizSummary(null)
    setAttemptResult(null)
    setIsAnswerSubmitted(false)
    setSelectedOption(null)
    setTimerSeconds(0)

    try {
      const ws = await workspaceService.getWorkspaceById(workspaceId)
      setWorkspace(ws)

      const sessionData = await tutorApiClient.createQuizSession(workspaceId, {
        targetQuestionCount: 5,
        initialDifficulty: 2,
      })

      setSessionId(sessionData.id)
      setCurrentDifficulty(sessionData.current_difficulty || 2)
      setTotalTargetQuestions(sessionData.target_question_count || 5)

      if (sessionData.current_question) {
        setCurrentQuestion(sessionData.current_question)
        setQuestionOrder(sessionData.current_question.question_order || 1)
        questionStartTimeRef.current = performance.now()
      } else {
        setErrorMessage('No questions could be generated. Please ensure your workspace has indexed documents.')
      }
    } catch (err: any) {
      console.error('Failed to initialize quiz session:', err)
      setErrorMessage(err.message || 'Unable to create adaptive quiz session. Please verify workspace sources are indexed.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    startQuizSession()
  }, [workspaceId])

  // Timer per question
  useEffect(() => {
    let interval: NodeJS.Timeout
    if (!quizSummary && !isAnswerSubmitted && !isLoading) {
      interval = setInterval(() => {
        setTimerSeconds((prev) => prev + 1)
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [quizSummary, isAnswerSubmitted, isLoading])

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60)
    const s = secs % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // Handle Answer Submission with High-Precision Timing
  const handleSubmitAnswer = async () => {
    if (!sessionId || !currentQuestion || !selectedOption || isSubmitting) return

    const responseTimeMs = Math.max(500, Math.round(performance.now() - questionStartTimeRef.current))
    setIsSubmitting(true)

    try {
      const result: AttemptResult = await tutorApiClient.submitQuizAttempt(
        workspaceId,
        sessionId,
        currentQuestion.id,
        {
          selectedOption,
          responseTimeMs,
        }
      )

      setAttemptResult(result)
      setIsAnswerSubmitted(true)
      setCurrentDifficulty(result.new_difficulty ?? currentDifficulty)
    } catch (err: any) {
      console.error('Failed to submit quiz attempt:', err)
      alert(err.message || 'Failed to submit answer. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Advance to Next Question or Complete Quiz
  const handleNextQuestion = async () => {
    if (!sessionId || !attemptResult) return

    if (attemptResult.is_quiz_completed || !attemptResult.next_question) {
      // Complete Session
      setIsLoading(true)
      try {
        const summary: QuizSummary = await tutorApiClient.completeQuizSession(workspaceId, sessionId)
        setQuizSummary(summary)
      } catch (err: any) {
        console.error('Failed to complete quiz session:', err)
        alert(err.message || 'Failed to generate quiz summary.')
      } finally {
        setIsLoading(false)
      }
    } else {
      // Next Adaptive Question
      setCurrentQuestion(attemptResult.next_question)
      setQuestionOrder(attemptResult.next_question.question_order || (questionOrder + 1))
      setCurrentDifficulty(attemptResult.next_question.difficulty_level || currentDifficulty)
      setSelectedOption(null)
      setIsAnswerSubmitted(false)
      setAttemptResult(null)
      setTimerSeconds(0)
      questionStartTimeRef.current = performance.now()
    }
  }

  // ============================================================
  // LOADING STATE
  // ============================================================
  if (isLoading && !quizSummary) {
    return (
      <div className="mx-auto w-full max-w-2xl px-4 py-24 text-center">
        <div className="flex flex-col items-center justify-center gap-4 rounded-3xl border border-border bg-card/60 p-12 shadow-soft">
          <Loader2 className="size-10 animate-spin text-primary" />
          <h2 className="font-display text-lg font-semibold text-foreground">
            Synthesizing Adaptive Diagnostics...
          </h2>
          <p className="max-w-md text-xs text-muted-foreground leading-relaxed">
            Retrieving grounded excerpts from your workspace documents to construct personalized diagnostic questions.
          </p>
        </div>
      </div>
    )
  }

  // ============================================================
  // EMPTY / ERROR STATE
  // ============================================================
  if (errorMessage || !currentQuestion) {
    return (
      <div className="mx-auto w-full max-w-2xl px-4 py-16 text-center">
        <div className="rounded-3xl border border-dashed border-border bg-card/50 p-10">
          <Zap className="mx-auto size-10 text-muted-foreground/60" />
          <h2 className="mt-4 font-display text-lg font-semibold text-foreground">
            No Quiz Questions Available
          </h2>
          <p className="mt-2 text-xs text-muted-foreground leading-relaxed max-w-md mx-auto">
            {errorMessage || `Upload lecture slides, textbooks, or notes in the Sources tab to automatically generate adaptive diagnostic quizzes for ${workspace?.name || 'this workspace'}.`}
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              href={`/dashboard/workspace/${workspaceId}/sources`}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-glow"
            >
              <span>Manage Learning Sources</span>
              <ArrowRight className="size-3.5" />
            </Link>
            <button
              onClick={startQuizSession}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-4 py-2.5 text-xs font-medium text-foreground hover:bg-accent/40"
            >
              <RotateCcw className="size-3.5" />
              <span>Retry</span>
            </button>
          </div>
        </div>
      </div>
    )
  }

  // ============================================================
  // QUIZ SUMMARY SCREEN
  // ============================================================
  if (quizSummary) {
    const weakConcepts = quizSummary.knowledge_gaps || []
    const tutorPrompt = weakConcepts.length > 0
      ? `I completed an adaptive quiz and need help understanding: ${weakConcepts.join(', ')}. Can you explain the core principles with examples?`
      : 'Can you give me an advanced conceptual challenge based on our workspace sources?'

    return (
      <div className="mx-auto w-full max-w-3xl px-4 py-8 md:py-12">
        <div className="rounded-3xl border border-border bg-card p-6 shadow-card md:p-10 text-center animate-in fade-in zoom-in-95 duration-200">
          <span className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-glow">
            <Award className="size-7" />
          </span>

          <h1 className="mt-4 font-display text-2xl font-semibold text-foreground md:text-3xl">
            Adaptive Assessment Completed
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            {workspace?.name || 'Workspace'} — Multi-Signal Performance Breakdown
          </p>

          {/* Key Metrics */}
          <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="rounded-2xl border border-border bg-background p-4">
              <span className="text-[11px] text-muted-foreground">Score</span>
              <p className="mt-1 font-display text-2xl font-bold text-foreground">
                {quizSummary.score}
              </p>
              <span className="text-[10px] text-muted-foreground">
                {(quizSummary as any).correct_count ?? (quizSummary as any).correct_answers ?? 0} of {quizSummary.total_questions} correct
              </span>
            </div>
            <div className="rounded-2xl border border-border bg-background p-4">
              <span className="text-[11px] text-muted-foreground">Accuracy</span>
              <p className="mt-1 font-display text-2xl font-bold text-primary">
                {quizSummary.accuracy_percentage}%
              </p>
              <span className="text-[10px] text-muted-foreground">Precision Rate</span>
            </div>
            <div className="rounded-2xl border border-border bg-background p-4">
              <span className="text-[11px] text-muted-foreground">Avg Response Time</span>
              <p className="mt-1 font-display text-2xl font-bold text-foreground">
                {quizSummary.average_response_time_seconds}s
              </p>
              <span className="text-[10px] text-muted-foreground">Speed Calibration</span>
            </div>
            <div className="rounded-2xl border border-border bg-background p-4">
              <span className="text-[11px] text-muted-foreground">Final Difficulty</span>
              <p className="mt-1 font-display text-2xl font-bold text-warning">
                L{(quizSummary as any).final_difficulty_level || 2}
              </p>
              <span className="text-[10px] text-muted-foreground">
                {DIFFICULTY_LABELS[(quizSummary as any).final_difficulty_level || 2]?.name.split(':')[1] || 'Calibrated'}
              </span>
            </div>
          </div>

          {/* Concept Performance Matrix */}
          {((quizSummary as any).concept_performance || (quizSummary as any).concept_breakdown || []).length > 0 && (
            <div className="mt-6 text-left">
              <h3 className="font-display text-sm font-semibold text-foreground">Concept Mastery Matrix</h3>
              <div className="mt-3 flex flex-col gap-2">
                {((quizSummary as any).concept_performance || (quizSummary as any).concept_breakdown || []).map((c: any, i: number) => {
                  const cName = c.concept || c.concept_name
                  const cAcc = c.accuracy_percentage
                  const cStatus = c.mastery_status || (c.status === 'strong' ? 'mastered' : 'review_needed')
                  return (
                    <div
                      key={i}
                      className="flex items-center justify-between rounded-xl border border-border bg-background p-3 text-xs"
                    >
                      <div>
                        <span className="font-medium text-foreground">{cName}</span>
                        <p className="text-[10px] text-muted-foreground">
                          {c.correct}/{c.total_questions || c.attempts || 1} correct ({cAcc}%)
                        </p>
                      </div>
                      <Badge
                        variant={cStatus === 'mastered' ? 'success' : cStatus === 'proficient' ? 'warning' : 'destructive'}
                        size="sm"
                      >
                        {cStatus === 'mastered' ? 'Mastered' : cStatus === 'proficient' ? 'Proficient' : 'Needs Review'}
                      </Badge>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Identified Gaps */}
          {weakConcepts.length > 0 && (
            <div className="mt-6 rounded-2xl border border-destructive/20 bg-destructive/5 p-4 text-left">
              <div className="flex items-center gap-2 text-xs font-semibold text-destructive">
                <AlertTriangle className="size-4" />
                <span>Identified Knowledge Gaps</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                The adaptive engine detected hesitation or incorrect responses on:{' '}
                <span className="font-semibold text-foreground">
                  {weakConcepts.join(', ')}
                </span>
                .
              </p>
            </div>
          )}

          {/* AI Recommendations */}
          {((quizSummary as any).recommendation || (quizSummary as any).recommendations) && (
            <div className="mt-4 rounded-2xl border border-primary/20 bg-primary/5 p-4 text-left text-xs">
              <div className="flex items-center gap-2 font-semibold text-primary">
                <Sparkles className="size-4" />
                <span>AI Tutor Recommendations</span>
              </div>
              <p className="mt-2 text-muted-foreground leading-relaxed">
                {(quizSummary as any).recommendation ||
                  (Array.isArray((quizSummary as any).recommendations)
                    ? (quizSummary as any).recommendations.join(' ')
                    : 'Review identified topics with AI Tutor.')}
              </p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="mt-8 flex flex-col sm:flex-row gap-3">
            <Link
              href={`/dashboard/workspace/${workspaceId}/tutor?prompt=${encodeURIComponent(tutorPrompt)}`}
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
              onClick={startQuizSession}
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

  const currentConcept = currentQuestion.concept || currentQuestion.concept_tag || 'Core Principle'
  const currentDiff = currentQuestion.difficulty || currentQuestion.difficulty_level || currentDifficulty
  const diffMeta = DIFFICULTY_LABELS[currentDiff] || {
    name: `Level ${currentDiff}`,
    variant: 'neutral',
  }

  const citations = attemptResult?.document_name
    ? [{
        document_name: attemptResult.document_name,
        page_or_slide: attemptResult.page_number || 1,
        excerpt: attemptResult.source_excerpt,
      }]
    : (attemptResult?.source_citations || [])

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
                <h2 className="font-display text-sm font-semibold text-foreground">{workspace?.name || 'Workspace'}</h2>
                <Badge variant="neutral" size="sm" className="text-[10px]">
                  {currentConcept}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">Production Adaptive Diagnostic Engine</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant={diffMeta.variant} size="md" className="capitalize text-xs font-semibold">
              {diffMeta.name}
            </Badge>
            <span className="flex items-center gap-1 text-xs font-medium tabular-nums text-muted-foreground">
              <Clock className="size-3.5" /> {formatTime(timerSeconds)}
            </span>
          </div>
        </div>

        {/* Question Counter & Progress */}
        <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
          <span>Question {questionOrder} of {totalTargetQuestions}</span>
          <div className="flex gap-1">
            {Array.from({ length: totalTargetQuestions }).map((_, i) => (
              <span
                key={i}
                className={cn(
                  'h-1.5 w-5 rounded-full transition-colors',
                  i + 1 === questionOrder
                    ? 'bg-primary'
                    : i + 1 < questionOrder
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
            {currentQuestion.question_text}
          </p>

          {/* Options */}
          <div className="mt-5 flex flex-col gap-2.5">
            {currentQuestion.options.map((opt: any) => {
              const optKey = opt.key || opt.option_id
              const isSelected = selectedOption === optKey
              const isCorrectOpt = isAnswerSubmitted && attemptResult && optKey === attemptResult.correct_option
              const isWrongSelected = isAnswerSubmitted && isSelected && !attemptResult?.is_correct

              return (
                <button
                  key={optKey}
                  disabled={isAnswerSubmitted || isSubmitting}
                  onClick={() => setSelectedOption(optKey)}
                  className={cn(
                    'flex items-center gap-3.5 rounded-2xl border p-4 text-left text-xs md:text-sm transition-all',
                    !isAnswerSubmitted && !isSelected && 'border-border bg-background/50 hover:border-primary/40 hover:bg-accent/40',
                    !isAnswerSubmitted && isSelected && 'border-primary bg-primary/10 font-semibold ring-1 ring-primary/40',
                    isCorrectOpt && 'border-success/60 bg-success/10 text-foreground font-semibold',
                    isWrongSelected && 'border-destructive/60 bg-destructive/10 text-foreground',
                    isAnswerSubmitted && !isCorrectOpt && !isWrongSelected && 'border-border/60 opacity-60'
                  )}
                >
                  <span
                    className={cn(
                      'flex size-7 shrink-0 items-center justify-center rounded-lg border text-xs font-bold transition-colors',
                      isCorrectOpt
                        ? 'border-success bg-success text-success-foreground'
                        : isWrongSelected
                        ? 'border-destructive bg-destructive text-destructive-foreground'
                        : isSelected
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border bg-card text-muted-foreground'
                    )}
                  >
                    {isCorrectOpt ? <CheckCircle2 className="size-4" /> : isWrongSelected ? <XCircle className="size-4" /> : optKey}
                  </span>
                  <span className="flex-1 text-foreground">{opt.text}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* Feedback & Explanation Box (After Submission) */}
        {isAnswerSubmitted && attemptResult && (
          <div
            className={cn(
              'mt-6 rounded-2xl border p-4 text-xs leading-relaxed animate-in fade-in duration-150',
              attemptResult.is_correct
                ? 'border-success/30 bg-success/5 text-foreground'
                : 'border-destructive/30 bg-destructive/5 text-foreground'
            )}
          >
            <div className="flex items-center justify-between gap-2 font-semibold mb-1.5">
              <div className="flex items-center gap-2">
                {attemptResult.is_correct ? (
                  <>
                    <CheckCircle2 className="size-4 text-success" />
                    <span className="text-success">Correct (+{attemptResult.earned_score} pts)</span>
                  </>
                ) : (
                  <>
                    <XCircle className="size-4 text-destructive" />
                    <span className="text-destructive">Incorrect — Concept Calibration</span>
                  </>
                )}
              </div>

              {attemptResult.adaptation_reason && (
                <span className="text-[10px] text-muted-foreground font-normal bg-background/80 px-2 py-0.5 rounded-md border border-border/50">
                  {attemptResult.adaptation_reason}
                </span>
              )}
            </div>

            <p className="text-muted-foreground mt-1">{attemptResult.explanation}</p>

            {/* Document Grounding Citation */}
            {citations.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground border-t border-border/60 pt-2.5">
                <FileText className="size-3.5 text-primary shrink-0" />
                <span>
                  Grounded in:{' '}
                  <strong className="text-foreground">{citations[0].document_name}</strong>
                  {' '}(Page {citations[0].page_or_slide})
                </span>
                {citations[0].excerpt && (
                  <p className="w-full text-[10px] text-muted-foreground/80 italic pl-5 line-clamp-2">
                    &ldquo;{citations[0].excerpt}&rdquo;
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        {/* Action Controls */}
        <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
          <span className="text-xs text-muted-foreground">
            Concept: <strong className="text-foreground">{currentConcept}</strong>
          </span>

          {!isAnswerSubmitted ? (
            <button
              onClick={handleSubmitAnswer}
              disabled={!selectedOption || isSubmitting}
              className="flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-6 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="size-3.5 animate-spin" />
                  <span>Evaluating...</span>
                </>
              ) : (
                <span>Submit Answer</span>
              )}
            </button>
          ) : (
            <button
              onClick={handleNextQuestion}
              className="flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-6 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
            >
              <span>
                {attemptResult?.is_quiz_completed || questionOrder >= totalTargetQuestions
                  ? 'View Final Results'
                  : 'Next Question'}
              </span>
              <ArrowRight className="size-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
