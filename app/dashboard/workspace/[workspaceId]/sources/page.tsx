'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import {
  FileText,
  Plus,
  Search,
  Upload,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileCode,
  FileSpreadsheet,
  File,
  X,
  ExternalLink,
  Sparkles,
  Loader2,
  Trash2,
  Eye,
  Download,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import { tutorApiClient } from '@/lib/api/tutor-api-client'
import {
  Workspace,
  WorkspaceDocument,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { AddSourceModal } from '@/components/workspace/add-source-modal'
import { cn } from '@/lib/utils'

const IN_PROGRESS = new Set(['uploading', 'processing', 'extracting', 'indexing'])

function statusBadge(status: string) {
  if (status === 'ready') return { variant: 'success' as const, label: 'Ready' }
  if (status === 'failed') return { variant: 'destructive' as const, label: 'Failed' }
  return { variant: 'warning' as const, label: 'Processing' }
}

export default function SourcesPage() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDoc, setSelectedDoc] = useState<WorkspaceDocument | null>(null)
  const [addSourceModalOpen, setAddSourceModalOpen] = useState(false)
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!workspaceId) return

    async function loadDocs() {
      const [ws, docs] = await Promise.all([
        workspaceService.getWorkspaceById(workspaceId),
        workspaceService.getDocuments(workspaceId),
      ])
      setWorkspace(ws)
      setDocuments(docs)
    }
    loadDocs()
  }, [workspaceId])

  // While any document is still being processed, refresh the list every few seconds
  const hasProcessing = documents.some((d) => IN_PROGRESS.has(d.status))
  useEffect(() => {
    if (!workspaceId || !hasProcessing) return
    const t = setInterval(async () => {
      const latest = await tutorApiClient.getWorkspaceDocuments(workspaceId)
      if (latest) {
        setDocuments(latest)
        setSelectedDoc((sel) => (sel ? latest.find((d) => d.id === sel.id) || sel : sel))
      }
    }, 3000)
    return () => clearInterval(t)
  }, [workspaceId, hasProcessing])

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => {
      setToastMessage(null)
    }, 3000)
  }

  const handleSourceAdded = (newDoc: WorkspaceDocument) => {
    setDocuments((prev) => [newDoc, ...prev])
    if (workspace) {
      setWorkspace({ ...workspace, documentCount: workspace.documentCount + 1 })
    }
    showToast(newDoc.status === 'ready' ? 'Source added successfully.' : 'Upload received — processing in the background.')
  }

  const handleRemoveDoc = async (docId: string) => {
    await workspaceService.removeDocument(workspaceId, docId)
    setDocuments((prev) => prev.filter((d) => d.id !== docId))
    if (selectedDoc?.id === docId) {
      setSelectedDoc(null)
    }
    if (workspace) {
      setWorkspace({ ...workspace, documentCount: Math.max(0, workspace.documentCount - 1) })
    }
    showToast('Source removed from workspace.')
  }

  const filteredDocs = documents.filter((doc) =>
    doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6 md:py-8 space-y-6">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-xs font-semibold text-foreground shadow-card animate-in fade-in slide-in-from-bottom-3 duration-200">
          <CheckCircle2 className="size-4 text-success" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              Source Repository
            </span>
            <span className="text-muted-foreground">•</span>
            <span className="text-xs text-muted-foreground">{workspace?.name}</span>
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold text-foreground md:text-3xl">
            Knowledge Base Sources
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            All learning resources indexed into vector embeddings for grounded AI tutoring and quiz generation.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search sources..."
              className="h-9 w-48 rounded-xl border border-input bg-card pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground/60 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
            />
          </div>

          <button
            onClick={() => setAddSourceModalOpen(true)}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-primary px-3.5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
          >
            <Plus className="size-4" />
            <span>Add Source</span>
          </button>
        </div>
      </div>

      {/* Sources Grid & Document Inspector Drawer */}
      <div className="grid gap-6 lg:grid-cols-12">
        <div className={cn('space-y-3', selectedDoc ? 'lg:col-span-8' : 'lg:col-span-12')}>
          {filteredDocs.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-border bg-card/40 p-12 text-center">
              <FileText className="mx-auto size-10 text-muted-foreground/60" />
              <h3 className="mt-3 font-display text-sm font-semibold text-foreground">No sources found</h3>
              <p className="mt-1 text-xs text-muted-foreground">
                Upload your first textbook, lecture PDF, or notes to build the workspace knowledge base.
              </p>
              <button
                onClick={() => setAddSourceModalOpen(true)}
                className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-glow"
              >
                <Upload className="size-3.5" /> Upload Resource
              </button>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {filteredDocs.map((doc) => {
                const isSelected = selectedDoc?.id === doc.id
                return (
                  <div
                    key={doc.id}
                    onClick={() => setSelectedDoc(doc)}
                    className={cn(
                      'flex flex-col justify-between rounded-3xl border p-5 transition-all cursor-pointer shadow-soft hover:shadow-card',
                      isSelected
                        ? 'border-primary bg-card ring-1 ring-primary/40'
                        : 'border-border bg-card hover:border-primary/40'
                    )}
                  >
                    <div>
                      <div className="flex items-start justify-between">
                        <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                          <FileText className="size-5" />
                        </span>
                        <Badge
                          variant={statusBadge(doc.status).variant}
                          size="sm"
                          className="gap-1 text-[10px]"
                        >
                          {IN_PROGRESS.has(doc.status) ? <Loader2 className="size-3 animate-spin" /> : null}
                          {statusBadge(doc.status).label}
                        </Badge>
                      </div>

                      <h3 className="mt-3 font-display text-sm font-semibold text-foreground line-clamp-1">
                        {doc.title}
                      </h3>
                      <p className="mt-0.5 text-[11px] text-muted-foreground truncate">{doc.filename}</p>
                      <p
                        className={cn(
                          'mt-2 text-xs line-clamp-2',
                          doc.status === 'failed' ? 'text-destructive' : 'text-muted-foreground',
                        )}
                      >
                        {doc.status === 'failed'
                          ? doc.errorMessage || 'This file could not be processed.'
                          : IN_PROGRESS.has(doc.status)
                            ? 'Reading, chunking and indexing this file…'
                            : doc.summary}
                      </p>
                    </div>

                    <div className="mt-4 border-t border-border/70 pt-3 flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>{doc.pagesCount} pages / slides</span>
                      <span className="font-semibold text-primary">{doc.chunksCount} chunks</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Selected Document Details Side-Drawer */}
        {selectedDoc && (
          <aside className="lg:col-span-4 rounded-3xl border border-border bg-card p-6 shadow-card space-y-5 animate-in fade-in duration-150">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
                Source Inspector
              </span>
              <button
                onClick={() => setSelectedDoc(null)}
                className="text-xs text-muted-foreground hover:text-foreground"
              >
                Close
              </button>
            </div>

            <div>
              <h2 className="font-display text-base font-semibold text-foreground">{selectedDoc.title}</h2>
              <p className="mt-0.5 text-xs text-muted-foreground">{selectedDoc.filename}</p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-xl border border-border bg-background p-3">
                <span className="text-[10px] text-muted-foreground">Index Status</span>
                <p
                  className={cn(
                    'mt-1 flex items-center gap-1 font-semibold',
                    selectedDoc.status === 'ready'
                      ? 'text-success'
                      : selectedDoc.status === 'failed'
                        ? 'text-destructive'
                        : 'text-warning',
                  )}
                >
                  {selectedDoc.status === 'ready' ? (
                    <CheckCircle2 className="size-3" />
                  ) : selectedDoc.status === 'failed' ? (
                    <AlertCircle className="size-3" />
                  ) : (
                    <Loader2 className="size-3 animate-spin" />
                  )}
                  {statusBadge(selectedDoc.status).label}
                </p>
              </div>

              <div className="rounded-xl border border-border bg-background p-3">
                <span className="text-[10px] text-muted-foreground">Semantic Chunks</span>
                <p className="mt-1 font-semibold text-foreground">{selectedDoc.chunksCount} vectors</p>
              </div>

              <div className="rounded-xl border border-border bg-background p-3">
                <span className="text-[10px] text-muted-foreground">Page Count</span>
                <p className="mt-1 font-semibold text-foreground">{selectedDoc.pagesCount} pages</p>
              </div>

              <div className="rounded-xl border border-border bg-background p-3">
                <span className="text-[10px] text-muted-foreground">File Size</span>
                <p className="mt-1 font-semibold text-foreground">
                  {(selectedDoc.sizeBytes / (1024 * 1024)).toFixed(1)} MB
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-background p-4 text-xs">
              <span className="font-semibold text-primary">RAG Index Summary</span>
              <p className="mt-1.5 leading-relaxed text-muted-foreground">
                {selectedDoc.summary ||
                  'Document has been pre-processed with semantic chunking and layout parsing. Citations are ready for the AI Tutor.'}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <a
                href={`/api/v1/documents/${selectedDoc.id}/view`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-1.5 rounded-xl border border-border bg-background py-2 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
              >
                <Eye className="size-3.5" />
                <span>View PDF</span>
              </a>
              <a
                href={`/api/v1/documents/${selectedDoc.id}/download`}
                download
                className="flex items-center justify-center gap-1.5 rounded-xl border border-border bg-background py-2 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
              >
                <Download className="size-3.5" />
                <span>Download</span>
              </a>
            </div>

            <div className="border-t border-border pt-3">
              <button
                onClick={() => handleRemoveDoc(selectedDoc.id)}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-background py-2 text-xs font-semibold text-muted-foreground transition-colors hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
              >
                <Trash2 className="size-3.5" />
                <span>Remove Source from Workspace</span>
              </button>
            </div>
          </aside>
        )}
      </div>

      {/* Improved Add Source Modal */}
      <AddSourceModal
        isOpen={addSourceModalOpen}
        workspaceId={workspaceId}
        workspaceName={workspace?.name}
        onClose={() => setAddSourceModalOpen(false)}
        onSourceAdded={handleSourceAdded}
      />
    </div>
  )
}
