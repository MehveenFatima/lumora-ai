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
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import {
  Workspace,
  WorkspaceDocument,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export default function SourcesPage() {
  const params = useParams()
  const workspaceId = (params?.workspaceId as string) || 'dsa'

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [documents, setDocuments] = useState<WorkspaceDocument[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDoc, setSelectedDoc] = useState<WorkspaceDocument | null>(null)
  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [isUploading, setIsUploading] = useState(false)

  // Upload modal states
  const [newTitle, setNewTitle] = useState('')
  const [newFilename, setNewFilename] = useState('')
  const [fileType, setFileType] = useState<'pdf' | 'pptx' | 'docx'>('pdf')
  const [pagesCount, setPagesCount] = useState(48)

  useEffect(() => {
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

  const handleUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTitle.trim()) return

    setIsUploading(true)
    try {
      const newDoc = await workspaceService.addDocument(workspaceId, {
        title: newTitle.trim(),
        filename: newFilename.trim() || `${newTitle.trim().replace(/\s+/g, '_')}.${fileType}`,
        type: fileType,
        sizeBytes: 8500000,
        pagesCount,
      })

      setDocuments((prev) => [newDoc, ...prev])
      setIsUploading(false)
      setUploadModalOpen(false)
      setNewTitle('')
      setNewFilename('')
    } catch (err) {
      console.error(err)
      setIsUploading(false)
    }
  }

  const filteredDocs = documents.filter((doc) =>
    doc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    doc.filename.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6 md:py-8 space-y-6">
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
            onClick={() => setUploadModalOpen(true)}
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
                onClick={() => setUploadModalOpen(true)}
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
                          variant={doc.status === 'ready' ? 'success' : 'warning'}
                          size="sm"
                          className="capitalize text-[10px]"
                        >
                          {doc.status}
                        </Badge>
                      </div>

                      <h3 className="mt-3 font-display text-sm font-semibold text-foreground line-clamp-1">
                        {doc.title}
                      </h3>
                      <p className="mt-0.5 text-[11px] text-muted-foreground truncate">{doc.filename}</p>
                      <p className="mt-2 text-xs text-muted-foreground line-clamp-2">{doc.summary}</p>
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
                <p className="mt-1 font-semibold capitalize text-success flex items-center gap-1">
                  <CheckCircle2 className="size-3" /> {selectedDoc.status}
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
          </aside>
        )}
      </div>

      {/* Upload Source Modal */}
      {uploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setUploadModalOpen(false)} aria-hidden />

          <div className="relative w-full max-w-md rounded-3xl border border-border bg-card p-6 shadow-card animate-in fade-in zoom-in-95 duration-150">
            <button
              onClick={() => setUploadModalOpen(false)}
              className="absolute right-5 top-5 flex size-8 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground"
            >
              <X className="size-4" />
            </button>

            <div className="flex items-center gap-2.5">
              <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Upload className="size-4" />
              </span>
              <div>
                <h3 className="font-display text-base font-semibold text-foreground">Add Workspace Source</h3>
                <p className="text-xs text-muted-foreground">PDF, PPTX, or DOCX documents</p>
              </div>
            </div>

            <form onSubmit={handleUploadSubmit} className="mt-5 space-y-4">
              <div>
                <label className="text-xs font-semibold text-foreground">Document Title *</label>
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="e.g. Graph Algorithms Deep Dive"
                  className="mt-1.5 h-10 w-full rounded-xl border border-input bg-background px-3 text-xs text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-foreground">Resource Type</label>
                <div className="mt-1.5 grid grid-cols-3 gap-2">
                  {(['pdf', 'pptx', 'docx'] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setFileType(t)}
                      className={cn(
                        'rounded-xl border p-2 text-center text-xs font-semibold uppercase transition-all',
                        fileType === t
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border bg-background text-muted-foreground'
                      )}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-foreground">Estimated Page / Slide Count</label>
                <input
                  type="number"
                  value={pagesCount}
                  onChange={(e) => setPagesCount(Number(e.target.value))}
                  min={1}
                  max={500}
                  className="mt-1.5 h-10 w-full rounded-xl border border-input bg-background px-3 text-xs text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={!newTitle.trim() || isUploading}
                  className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-40"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="size-4 animate-spin" /> Indexing Document Vectors...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="size-4" /> Index into Workspace
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
