'use client'

import { useState } from 'react'
import {
  X,
  Zap,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  Sparkles,
  BarChart3,
  Loader2,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

interface BaselineAssessmentModalProps {
  isOpen: boolean
  onClose: () => void
}

const baselineQuestions = [
  {
    topic: 'Graphs',
    question: 'In a graph with V vertices and E edges represented as an adjacency list, what is the time complexity of BFS?',
    options: ['O(V * E)', 'O(V + E)', 'O(V^2)', 'O(E log V)'],
    correct: 1,
  },
  {
    topic: 'Trees',
    question: 'Which tree traversal yields elements in non-decreasing order for a Binary Search Tree (BST)?',
    options: ['Pre-order', 'In-order', 'Post-order', 'Level-order'],
    correct: 1,
  },
  {
    topic: 'Operating Systems',
    question: 'Which of the following is NOT one of the 4 Coffman conditions for deadlock?',
    options: ['Mutual Exclusion', 'Hold and Wait', 'Arbitrary Preemption', 'Circular Wait'],
    correct: 2,
  },
  {
    topic: 'Dynamic Programming',
    question: 'What is the standard optimal substructure requirement for dynamic programming to apply?',
    options: ['Greedy choice property', 'Overlapping subproblems and optimal substructure', 'Sorted input space', 'Divide and conquer without caching'],
    correct: 1,
  },
]

export function BaselineAssessmentModal({ isOpen, onClose }: BaselineAssessmentModalProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)
  const [answers, setAnswers] = useState<number[]>([])
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [isCompleted, setIsCompleted] = useState(false)

  if (!isOpen) return null

  const currentQ = baselineQuestions[currentIndex]

  const handleNext = () => {
    if (selectedOption === null) return
    const nextAnswers = [...answers, selectedOption]
    setAnswers(nextAnswers)
    setSelectedOption(null)

    if (currentIndex < baselineQuestions.length - 1) {
      setCurrentIndex((prev) => prev + 1)
    } else {
      setIsEvaluating(true)
      setTimeout(() => {
        setIsEvaluating(false)
        setIsCompleted(true)
      }, 1200)
    }
  }

  const score = answers.reduce((acc, ans, i) => {
    return ans === baselineQuestions[i].correct ? acc + 1 : acc
  }, 0)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} aria-hidden />

      <div className="relative w-full max-w-xl rounded-3xl border border-border bg-card p-6 shadow-card animate-in fade-in zoom-in-95 duration-150 sm:p-8">
        <button
          onClick={onClose}
          className="absolute right-5 top-5 flex size-8 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Close modal"
        >
          <X className="size-4" />
        </button>

        {!isCompleted && !isEvaluating && (
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex size-8 items-center justify-center rounded-lg bg-warning/15 text-warning">
                  <Zap className="size-4" />
                </span>
                <div>
                  <h2 className="font-display text-base font-semibold text-foreground">Diagnostic Baseline Assessment</h2>
                  <p className="text-[11px] text-muted-foreground">Calibrates your initial knowledge profile & roadmap</p>
                </div>
              </div>
              <Badge variant="neutral" size="sm">
                Question {currentIndex + 1} of {baselineQuestions.length}
              </Badge>
            </div>

            <div className="mt-4">
              <Progress value={((currentIndex + 1) / baselineQuestions.length) * 100} className="h-1.5" />
            </div>

            <div className="mt-6">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-primary">
                {currentQ.topic}
              </span>
              <p className="mt-1 text-sm font-medium leading-relaxed text-foreground">
                {currentQ.question}
              </p>

              <div className="mt-4 flex flex-col gap-2.5">
                {currentQ.options.map((opt, i) => {
                  const isSelected = selectedOption === i
                  return (
                    <button
                      key={i}
                      onClick={() => setSelectedOption(i)}
                      className={cn(
                        'flex items-center gap-3 rounded-2xl border p-3.5 text-left text-xs transition-all',
                        isSelected
                          ? 'border-primary bg-primary/10 text-foreground font-semibold ring-1 ring-primary/30'
                          : 'border-border bg-background/50 text-muted-foreground hover:border-primary/40 hover:bg-accent/40 hover:text-foreground'
                      )}
                    >
                      <span
                        className={cn(
                          'flex size-6 shrink-0 items-center justify-center rounded-lg border text-[11px] font-semibold',
                          isSelected ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-card'
                        )}
                      >
                        {String.fromCharCode(65 + i)}
                      </span>
                      <span>{opt}</span>
                    </button>
                  )
                })}
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  type="button"
                  disabled={selectedOption === null}
                  onClick={handleNext}
                  className="flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-40"
                >
                  {currentIndex === baselineQuestions.length - 1 ? 'Complete Assessment' : 'Next Question'}
                  <ArrowRight className="size-3.5" />
                </button>
              </div>
            </div>
          </div>
        )}

        {isEvaluating && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Loader2 className="size-10 animate-spin text-primary" />
            <h3 className="mt-4 font-display text-base font-semibold text-foreground">
              Synthesizing Diagnostic Results...
            </h3>
            <p className="mt-1 max-w-xs text-xs text-muted-foreground">
              Calculating concept mastery baselines and adapting initial learning milestones.
            </p>
          </div>
        )}

        {isCompleted && (
          <div className="text-center">
            <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-success/15 text-success">
              <CheckCircle2 className="size-7" />
            </div>
            <h3 className="mt-4 font-display text-lg font-semibold text-foreground">
              Initial Knowledge Profile Created
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              You scored {score} of {baselineQuestions.length} ({Math.round((score / baselineQuestions.length) * 100)}% accuracy).
            </p>

            <div className="mt-6 grid grid-cols-2 gap-3 text-left">
              <div className="rounded-2xl border border-border bg-background p-3.5">
                <span className="text-[11px] font-semibold text-success">Strong Foundational Grasp</span>
                <p className="mt-1 text-xs text-muted-foreground">Trees & Basic Graph traversals</p>
              </div>
              <div className="rounded-2xl border border-border bg-background p-3.5">
                <span className="text-[11px] font-semibold text-warning">Remediation Spliced</span>
                <p className="mt-1 text-xs text-muted-foreground">Dynamic Programming & Concurrency</p>
              </div>
            </div>

            <div className="mt-6 rounded-2xl border border-primary/20 bg-primary/5 p-4 text-xs text-foreground text-left">
              <p className="font-semibold text-primary">Your personalized learning path is ready.</p>
              <p className="mt-1 text-muted-foreground">
                LumoraAI has adjusted your roadmap and configured initial flashcard decks for today.
              </p>
            </div>

            <button
              onClick={onClose}
              className="mt-6 w-full rounded-xl bg-primary py-3 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
            >
              Enter Workspace & Start Learning
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
