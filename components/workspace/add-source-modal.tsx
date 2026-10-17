'use client'

import { useState, useRef, useEffect } from 'react'
import {
  X,
  Upload,
  FileText,
  FileCode,
  File,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Trash2,
  Sparkles,
} from 'lucide-react'
import { WorkspaceDocument, DocumentType } from '@/lib/types/domain'
import { workspaceService } from '@/lib/services/workspace-service'
import { tutorApiClient } from '@/lib/api/tutor-api-client'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface AddSourceModalProps {
  isOpen: boolean
  workspaceId: string
  workspaceName?: string
  onClose: () => void
  onSourceAdded: (newDoc: WorkspaceDocument) => void
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB
const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.pptx', '.txt']

type ProcessingStage = 'idle' | 'uploading' | 'processing' | 'extracting' | 'indexing' | 'ready'

export function AddSourceModal({
  isOpen,
  workspaceId,
  workspaceName,
  onClose,
  onSourceAdded,
}: AddSourceModalProps) {
  const [file, setFile] = useState<File | null>(null)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [stage, setStage] = useState<ProcessingStage>('idle')
  const [progressPercent, setProgressPercent] = useState(0)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const cancelledRef = useRef(false)
  const [backgroundDoc, setBackgroundDoc] = useState<WorkspaceDocument | null>(null)

  // Stop following a background upload when the modal unmounts
  useEffect(() => () => {
    cancelledRef.current = true
  }, [])

  useEffect(() => {
    if (isOpen) {
      setFile(null)
      setValidationError(null)
      setIsDragging(false)
      setStage('idle')
      setProgressPercent(0)
      setBackgroundDoc(null)
      cancelledRef.current = false
    }
  }, [isOpen])

  // Handle ESC key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && isOpen && stage === 'idle') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, stage, onClose])

  if (!isOpen) return null

  const validateAndSetFile = (selectedFile: File) => {
    setValidationError(null)

    // Check extension
    const name = selectedFile.name.toLowerCase()
    if (name.endsWith('.doc') || name.endsWith('.ppt')) {
      setValidationError(
        `This is an older Office format. Open it and use Save As to save it as ${name.endsWith('.doc') ? '.docx' : '.pptx'} (or export as PDF), then upload again.`,
      )
      return
    }
    const isSupported = SUPPORTED_EXTENSIONS.some((ext) => name.endsWith(ext))
    if (!isSupported) {
      setValidationError('Unsupported file type. Please upload PDF, DOCX, PPTX or TXT.')
      setFile(null)
      return
    }

    // Check size
    if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
      setValidationError('File exceeds the 10 MB limit.')
      setFile(null)
      return
    }

    setFile(selectedFile)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0])
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndSetFile(e.dataTransfer.files[0])
    }
  }

  const handleRemoveFile = () => {
    setFile(null)
    setValidationError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const getFileType = (filename: string): 'pdf' | 'pptx' | 'docx' => {
    const lower = filename.toLowerCase()
    if (lower.endsWith('.pptx')) return 'pptx'
    if (lower.endsWith('.docx')) return 'docx'
    return 'pdf'
  }

  const handleStartUpload = async () => {
    if (!file) return

    const fType = getFileType(file.name)
    const title = file.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' ')
    const estimatedPages = Math.max(1, Math.round(file.size / (150 * 1024)))
    cancelledRef.current = false

    // While the request is open the server parses, chunks and embeds; show that honestly
    const stageTimer = setTimeout(() => {
      if (!cancelledRef.current) {
        setStage('processing')
        setProgressPercent(40)
      }
    }, 1200)

    try {
      setStage('uploading')
      setProgressPercent(15)

      const newDoc = await workspaceService.addDocument(workspaceId, {
        title,
        filename: file.name,
        type: fType,
        sizeBytes: file.size,
        pagesCount: estimatedPages,
        rawFile: file,
      })
      clearTimeout(stageTimer)

      if (newDoc.status === 'ready') {
        finish(newDoc)
        return
      }

      // Large file: the server keeps processing in the background; follow its real status
      setBackgroundDoc(newDoc)
      await followProcessing(newDoc)
    } catch (err: any) {
      clearTimeout(stageTimer)
      console.error('Failed to add document source:', err)
      setValidationError(err.message || 'Failed to upload document.')
      setStage('idle')
      setProgressPercent(0)
    }
  }

  const finish = (doc: WorkspaceDocument) => {
    setStage('ready')
    setProgressPercent(100)
    setTimeout(() => {
      onSourceAdded(doc)
      onClose()
    }, 600)
  }

  const STAGE_PROGRESS: Record<string, number> = { uploading: 20, processing: 40, extracting: 60, indexing: 85 }

  const followProcessing = async (doc: WorkspaceDocument) => {
    while (!cancelledRef.current) {
      await new Promise((r) => setTimeout(r, 2000))
      if (cancelledRef.current) return
      const latest = await tutorApiClient.getDocument(doc.id)
      if (!latest) continue
      if (latest.status === 'ready') {
        finish(latest)
        return
      }
      if (latest.status === 'failed') {
        setBackgroundDoc(null)
        setValidationError(latest.errorMessage || 'This file could not be processed.')
        setStage('idle')
        setProgressPercent(0)
        return
      }
      setStage(latest.status as ProcessingStage)
      setProgressPercent(STAGE_PROGRESS[latest.status] ?? 50)
    }
  }

  const continueInBackground = () => {
    cancelledRef.current = true
    if (backgroundDoc) onSourceAdded(backgroundDoc)
    onClose()
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`
    }
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const getStageLabel = () => {
    switch (stage) {
      case 'uploading':
        return 'Uploading resource...'
      case 'processing':
        return 'Processing document structure...'
      case 'extracting':
        return 'Extracting content & semantic chunks...'
      case 'indexing':
        return 'Building vector index for AI Tutor...'
      case 'ready':
        return 'Ready! Added to workspace.'
      default:
        return ''
    }
  }

  const isProcessing = stage !== 'idle'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm transition-opacity"
        onClick={() => !isProcessing && onClose()}
        aria-hidden
      />

      {/* Modal Card */}
      <div className="relative w-full max-w-lg rounded-3xl border border-border bg-card p-6 shadow-card animate-in fade-in zoom-in-95 duration-150 sm:p-8">
        <button
          onClick={onClose}
          disabled={isProcessing}
          className="absolute right-5 top-5 flex size-8 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground transition-colors hover:text-foreground disabled:opacity-40"
          aria-label="Close modal"
        >
          <X className="size-4" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Upload className="size-5" />
          </span>
          <div>
            <h2 className="font-display text-lg font-semibold text-foreground">Add Learning Source</h2>
            <p className="text-xs text-muted-foreground">
              Upload learning material to build this workspace&apos;s knowledge base.
            </p>
          </div>
        </div>

        {/* Workspace Scope Indicator */}
        {workspaceName && (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-border bg-background/60 px-3 py-1.5 text-xs text-muted-foreground">
            <span>Workspace Scope:</span>
            <span className="font-semibold text-foreground">{workspaceName}</span>
          </div>
        )}

        {!isProcessing ? (
          <div className="mt-5 space-y-4">
            {/* Drag & Drop Upload Zone */}
            {!file ? (
              <div>
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className={cn(
                    'flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center cursor-pointer transition-all',
                    isDragging
                      ? 'border-primary bg-primary/10'
                      : 'border-border bg-background/50 hover:border-primary/50 hover:bg-accent/30'
                  )}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    onChange={handleFileChange}
                    accept=".pdf,.docx,.pptx,.txt"
                    className="hidden"
                  />
                  <span className="flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-soft">
                    <Upload className="size-6" />
                  </span>
                  <p className="mt-3 text-xs font-semibold text-foreground">
                    Drag and drop your file here
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    or <span className="font-semibold text-primary hover:underline">Choose File</span> from your device
                  </p>

                  <div className="mt-4 flex flex-wrap items-center justify-center gap-1.5 text-[10px] text-muted-foreground">
                    <Badge variant="neutral" size="sm">PDF</Badge>
                    <Badge variant="neutral" size="sm">DOCX</Badge>
                    <Badge variant="neutral" size="sm">PPTX</Badge>
                    <Badge variant="neutral" size="sm">TXT</Badge>
                    <span>• Maximum file size: 10 MB</span>
                  </div>
                </div>

                {validationError && (
                  <div className="mt-3 flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive animate-in fade-in">
                    <AlertCircle className="size-4 shrink-0" />
                    <span>{validationError}</span>
                  </div>
                )}
              </div>
            ) : (
              /* Selected File Preview Card */
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-2xl border border-primary/30 bg-primary/5 p-4 text-xs">
                  <div className="flex items-center gap-3 truncate">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                      <FileText className="size-5" />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-foreground">{file.name}</p>
                      <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                        <span className="uppercase font-bold text-primary">
                          {file.name.split('.').pop()}
                        </span>
                        <span>•</span>
                        <span>{formatFileSize(file.size)}</span>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleRemoveFile}
                    className="flex size-8 shrink-0 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground transition-colors hover:border-destructive/40 hover:text-destructive"
                    aria-label="Remove selected file"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>

                <div className="rounded-xl border border-border bg-background p-3 text-[11px] text-muted-foreground">
                  <p className="flex items-center gap-1.5 font-medium text-foreground">
                    <Sparkles className="size-3.5 text-primary" /> RAG Ingestion Pipeline:
                  </p>
                  <p className="mt-1">
                    Document will be parsed, split into semantic chunks, and embedded for contextual citation by the AI Tutor.
                  </p>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="mt-6 flex items-center justify-end gap-2.5 border-t border-border/80 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="h-10 rounded-xl border border-border bg-background px-4 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!file}
                onClick={handleStartUpload}
                className="flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                <Upload className="size-3.5" />
                <span>Add Source</span>
              </button>
            </div>
          </div>
        ) : (
          /* PROCESSING STATE SIMULATION */
          <div className="mt-6 space-y-5 py-4 text-center animate-in fade-in duration-150">
            <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-glow">
              {stage === 'ready' ? (
                <CheckCircle2 className="size-7 text-success" />
              ) : (
                <Loader2 className="size-7 animate-spin text-primary" />
              )}
            </div>

            <div>
              <h3 className="font-display text-base font-semibold text-foreground">
                {stage === 'ready' ? 'Document Indexed Successfully!' : getStageLabel()}
              </h3>
              <p className="mt-1 text-xs text-muted-foreground">{file?.name}</p>
              {backgroundDoc && stage !== 'ready' ? (
                <p className="mx-auto mt-2 max-w-sm text-[11px] text-muted-foreground">
                  This is a larger file, so it&apos;s being processed in the background. You can keep working; we&apos;ll
                  notify you when it&apos;s ready.
                </p>
              ) : null}
            </div>

            <div className="mx-auto max-w-sm">
              <Progress value={progressPercent} className="h-2" />
              <div className="mt-2 flex justify-between text-[11px] text-muted-foreground">
                <span className="capitalize">{stage}...</span>
                <span className="font-semibold text-primary">{progressPercent}%</span>
              </div>
            </div>

            {backgroundDoc && stage !== 'ready' ? (
              <button
                type="button"
                onClick={continueInBackground}
                className="mx-auto h-9 rounded-xl border border-border bg-background px-4 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
              >
                Continue in background
              </button>
            ) : null}

            {/* Processing Step Trace */}
            <div className="rounded-2xl border border-border bg-background p-4 text-left text-xs space-y-2">
              <div className="flex items-center gap-2">
                {progressPercent >= 20 ? (
                  <CheckCircle2 className="size-3.5 text-success" />
                ) : (
                  <span className="size-2 rounded-full bg-muted-foreground" />
                )}
                <span className={cn(progressPercent >= 20 ? 'text-foreground font-medium' : 'text-muted-foreground')}>
                  File upload & format verification
                </span>
              </div>

              <div className="flex items-center gap-2">
                {progressPercent >= 45 ? (
                  <CheckCircle2 className="size-3.5 text-success" />
                ) : (
                  <span className="size-2 rounded-full bg-muted-foreground" />
                )}
                <span className={cn(progressPercent >= 45 ? 'text-foreground font-medium' : 'text-muted-foreground')}>
                  Layout extraction & OCR parsing
                </span>
              </div>

              <div className="flex items-center gap-2">
                {progressPercent >= 70 ? (
                  <CheckCircle2 className="size-3.5 text-success" />
                ) : (
                  <span className="size-2 rounded-full bg-muted-foreground" />
                )}
                <span className={cn(progressPercent >= 70 ? 'text-foreground font-medium' : 'text-muted-foreground')}>
                  Semantic chunk generation
                </span>
              </div>

              <div className="flex items-center gap-2">
                {progressPercent >= 90 ? (
                  <CheckCircle2 className="size-3.5 text-success" />
                ) : (
                  <span className="size-2 rounded-full bg-muted-foreground" />
                )}
                <span className={cn(progressPercent >= 90 ? 'text-foreground font-medium' : 'text-muted-foreground')}>
                  Vector indexing for grounded RAG
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
