'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  X,
  Plus,
  Upload,
  FileText,
  Sparkles,
  CheckCircle2,
  Calendar,
  Clock,
  Target,
  Layers,
  ArrowRight,
  Loader2,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface CreateWorkspaceModalProps {
  isOpen: boolean
  onClose: () => void
}

export function CreateWorkspaceModal({ isOpen, onClose }: CreateWorkspaceModalProps) {
  const router = useRouter()
  const [step, setStep] = useState<1 | 2>(1)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Form State
  const [name, setName] = useState('')
  const [goal, setGoal] = useState('')
  const [level, setLevel] = useState<'beginner' | 'intermediate' | 'advanced'>('intermediate')
  const [targetDate, setTargetDate] = useState('2026-07-31')
  const [dailyMinutes, setDailyMinutes] = useState(45)
  const [description, setDescription] = useState('')
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ name: string; size: string }>>([
    { name: 'Course_Syllabus_and_Notes.pdf', size: '4.2 MB' },
  ])

  if (!isOpen) return null

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0]
      setUploadedFiles((prev) => [
        ...prev,
        {
          name: file.name,
          size: `${(file.size / (1024 * 1024)).toFixed(1)} MB`,
        },
      ])
    }
  }

  const handleCreate = async () => {
    if (!name.trim()) return
    setIsSubmitting(true)

    try {
      const created = await workspaceService.createWorkspace({
        name: name.trim(),
        goal: goal.trim() || 'Mastery and exam preparation',
        level,
        targetDate,
        dailyTargetMinutes: dailyMinutes,
        description: description.trim() || 'Custom learning workspace grounded in your uploaded documents.',
        iconName: 'FolderKanban',
      })

      // Add uploaded files as demo documents
      for (const f of uploadedFiles) {
        await workspaceService.addDocument(created.id, {
          title: f.name.replace(/\.[^/.]+$/, ''),
          filename: f.name,
          type: 'pdf',
          sizeBytes: 4500000,
          pagesCount: 45,
        })
      }

      setIsSubmitting(false)
      onClose()
      router.push(`/dashboard/workspace/${created.id}`)
    } catch (err) {
      console.error(err)
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm transition-opacity"
        onClick={onClose}
        aria-hidden
      />

      {/* Modal Card */}
      <div className="relative w-full max-w-lg rounded-3xl border border-border bg-card p-6 shadow-card animate-in fade-in zoom-in-95 duration-150 sm:p-8">
        <button
          onClick={onClose}
          className="absolute right-5 top-5 flex size-8 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Close modal"
        >
          <X className="size-4" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-2.5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Sparkles className="size-5" />
          </span>
          <div>
            <h2 className="font-display text-lg font-semibold text-foreground">Create Learning Workspace</h2>
            <p className="text-xs text-muted-foreground">
              Step {step} of 2 — {step === 1 ? 'Define your goal & scope' : 'Upload resources & finalize'}
            </p>
          </div>
        </div>

        {step === 1 ? (
          <div className="mt-6 flex flex-col gap-4">
            <div>
              <label className="text-xs font-semibold text-foreground">Workspace Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Distributed Systems & Raft Consensus"
                className="mt-1.5 h-10 w-full rounded-xl border border-input bg-background px-3.5 text-xs text-foreground placeholder:text-muted-foreground/60 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                required
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-foreground">Learning Goal</label>
              <input
                type="text"
                value={goal}
                onChange={(e) => setGoal(e.target.value)}
                placeholder="e.g. System Design Interview & Midterm Exam"
                className="mt-1.5 h-10 w-full rounded-xl border border-input bg-background px-3.5 text-xs text-foreground placeholder:text-muted-foreground/60 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-foreground">Current Knowledge Level</label>
              <div className="mt-1.5 grid grid-cols-3 gap-2">
                {(['beginner', 'intermediate', 'advanced'] as const).map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => setLevel(lvl)}
                    className={cn(
                      'rounded-xl border p-2.5 text-center text-xs font-medium capitalize transition-all',
                      level === lvl
                        ? 'border-primary bg-primary/10 text-primary font-semibold'
                        : 'border-border bg-background text-muted-foreground hover:border-border hover:bg-accent/40'
                    )}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-semibold text-foreground">Daily Study Target</label>
                <div className="relative mt-1.5">
                  <input
                    type="number"
                    min={15}
                    max={360}
                    step={15}
                    value={dailyMinutes}
                    onChange={(e) => setDailyMinutes(Number(e.target.value))}
                    className="h-10 w-full rounded-xl border border-input bg-background px-3.5 text-xs text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                  />
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[11px] text-muted-foreground">
                    min / day
                  </span>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-foreground">Target Completion Date</label>
                <div className="relative mt-1.5">
                  <input
                    type="date"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                    className="h-10 w-full rounded-xl border border-input bg-background px-3 text-xs text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                  />
                </div>
              </div>
            </div>

            <button
              type="button"
              disabled={!name.trim()}
              onClick={() => setStep(2)}
              className="mt-3 flex h-11 items-center justify-center gap-2 rounded-xl bg-primary text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              Continue to Resources <ArrowRight className="size-4" />
            </button>
          </div>
        ) : (
          <div className="mt-6 flex flex-col gap-4">
            <div>
              <label className="text-xs font-semibold text-foreground">Workspace Description / Notes</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                placeholder="What topics or exam syllabus should the AI tutor focus on?"
                className="mt-1.5 w-full rounded-xl border border-input bg-background p-3 text-xs text-foreground placeholder:text-muted-foreground/60 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
              />
            </div>

            <div>
              <label className="text-xs font-semibold text-foreground">Upload Learning Resources (PDF, PPTX, DOCX)</label>
              <label className="mt-1.5 flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-background/60 p-5 text-center transition-colors hover:border-primary/50 hover:bg-accent/30">
                <input type="file" onChange={handleFileUpload} accept=".pdf,.pptx,.docx,.txt" className="hidden" />
                <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Upload className="size-4" />
                </span>
                <span className="mt-2 text-xs font-medium text-foreground">
                  Click to browse or drag & drop files
                </span>
                <span className="mt-0.5 text-[11px] text-muted-foreground">
                  Lecture slides, textbooks, question banks, or notes
                </span>
              </label>

              {uploadedFiles.length > 0 && (
                <div className="mt-2 flex flex-col gap-1.5 max-h-36 overflow-y-auto">
                  {uploadedFiles.map((file, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between rounded-xl border border-border bg-background p-2.5 text-xs"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <FileText className="size-4 text-primary shrink-0" />
                        <span className="truncate font-medium text-foreground">{file.name}</span>
                      </div>
                      <span className="text-[11px] text-muted-foreground shrink-0">{file.size}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="mt-2 flex gap-2">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="h-11 flex-1 rounded-xl border border-border bg-background text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
              >
                Back
              </button>
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleCreate}
                className="flex h-11 flex-[2] items-center justify-center gap-2 rounded-xl bg-primary text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="size-4 animate-spin" /> Initializing Workspace...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="size-4" /> Create Workspace
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
