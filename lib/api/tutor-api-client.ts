import { TutorMessage, TutorCitation, WorkspaceDocument, Workspace } from '@/lib/types/domain'

export interface BackendTutorResponse {
  conversation_id: string
  message: {
    id: string
    role: 'user' | 'assistant' | 'system'
    content: string
    timestamp?: string
  }
  citations: Array<{
    id: string
    document_id: string
    document_name: string
    page_or_slide: number
    excerpt: string
    relevance_score: number
  }>
  retrieval: {
    chunks_considered: number
    grounded: boolean
    top_similarity_score?: number
    model_name?: string
  }
  suggested_follow_ups?: string[]
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const configuredBase = process.env.NEXT_PUBLIC_API_BASE_URL
  const urlsToTry: string[] = []

  // 1. Try relative URL first (Next.js native API route handler)
  urlsToTry.push(path)

  // 2. Try configured base if specified
  if (configuredBase) {
    urlsToTry.unshift(`${configuredBase}${path}`)
  } else {
    urlsToTry.push(`http://localhost:8000${path}`)
  }

  let lastError: any = null
  for (const url of urlsToTry) {
    try {
      const res = await fetch(url, options)
      if (res.ok || res.status < 500) {
        return res
      }
    } catch (err) {
      lastError = err
    }
  }

  throw lastError || new Error(`Failed to reach API endpoint: ${path}`)
}

export const tutorApiClient = {
  // WORKSPACE API METHODS
  async createWorkspace(data: {
    id?: string
    name: string
    goal: string
    level: string
    targetDate?: string
    dailyTargetMinutes?: number
    description?: string
    iconName?: string
  }): Promise<Workspace> {
    try {
      const response = await apiFetch('/api/v1/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: data.id,
          name: data.name,
          goal: data.goal,
          level: data.level,
          target_date: data.targetDate,
          daily_target_minutes: data.dailyTargetMinutes,
          description: data.description,
          icon_name: data.iconName,
        }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `Failed to create workspace on backend (HTTP ${response.status})`)
      }

      const ws = await response.json()
      return {
        id: ws.id,
        name: ws.name,
        goal: ws.goal,
        level: ws.level,
        targetDate: ws.target_date || ws.targetDate || '2026-12-31',
        dailyTargetMinutes: ws.daily_target_minutes || ws.dailyTargetMinutes || 45,
        description: ws.description || '',
        overallMastery: ws.overall_mastery || ws.overallMastery || 0,
        masteryDelta: ws.mastery_delta || ws.masteryDelta || 0,
        status: ws.status || 'active',
        iconName: ws.icon_name || ws.iconName || 'FolderKanban',
        documentCount: ws.document_count || ws.documentCount || 0,
        topicsCount: 0,
        flashcardsDueCount: 0,
        lastActive: 'Just now',
        createdAt: ws.created_at ? ws.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
      }
    } catch {
      // In server-side / Node execution environment
      const { ragEngine } = await import('@/lib/server/rag-engine')
      const created = ragEngine.createWorkspace({
        id: data.id || `ws_${Date.now()}`,
        name: data.name,
        goal: data.goal,
        level: data.level,
        targetDate: data.targetDate || '2026-12-31',
        dailyTargetMinutes: data.dailyTargetMinutes || 45,
        description: data.description || '',
        iconName: data.iconName || 'FolderKanban',
      })
      return {
        id: created.id,
        name: created.name,
        goal: created.goal,
        level: (created.level as any) || 'intermediate',
        targetDate: created.targetDate || '2026-12-31',
        dailyTargetMinutes: created.dailyTargetMinutes || 45,
        description: created.description || '',
        overallMastery: 0,
        masteryDelta: 0,
        status: 'active',
        iconName: created.iconName || 'FolderKanban',
        documentCount: 0,
        topicsCount: 0,
        flashcardsDueCount: 0,
        lastActive: 'Just now',
        createdAt: new Date().toISOString().split('T')[0],
      }
    }
  },

  async getWorkspaces(): Promise<Workspace[]> {
    try {
      const response = await apiFetch('/api/v1/workspaces')
      if (!response.ok) return []
      const data = await response.json()
      return (data.workspaces || []).map((ws: any) => ({
        id: ws.id,
        name: ws.name,
        goal: ws.goal,
        level: ws.level,
        targetDate: ws.target_date || ws.targetDate || '2026-12-31',
        dailyTargetMinutes: ws.daily_target_minutes || ws.dailyTargetMinutes || 45,
        description: ws.description || '',
        overallMastery: ws.overall_mastery || ws.overallMastery || 0,
        masteryDelta: ws.mastery_delta || ws.masteryDelta || 0,
        status: ws.status || 'active',
        iconName: ws.icon_name || ws.iconName || 'FolderKanban',
        documentCount: ws.document_count || ws.documentCount || 0,
        topicsCount: 0,
        flashcardsDueCount: 0,
        lastActive: 'Recently',
        createdAt: ws.created_at ? ws.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
      }))
    } catch {
      return []
    }
  },

  async getWorkspaceById(workspaceId: string): Promise<Workspace | null> {
    try {
      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}`)
      if (!response.ok) return null
      const ws = await response.json()
      return {
        id: ws.id,
        name: ws.name,
        goal: ws.goal,
        level: ws.level,
        targetDate: ws.target_date || ws.targetDate || '2026-12-31',
        dailyTargetMinutes: ws.daily_target_minutes || ws.dailyTargetMinutes || 45,
        description: ws.description || '',
        overallMastery: ws.overall_mastery || ws.overallMastery || 0,
        masteryDelta: ws.mastery_delta || ws.masteryDelta || 0,
        status: ws.status || 'active',
        iconName: ws.icon_name || ws.iconName || 'FolderKanban',
        documentCount: ws.document_count || ws.documentCount || 0,
        topicsCount: 0,
        flashcardsDueCount: 0,
        lastActive: 'Just now',
        createdAt: ws.created_at ? ws.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
      }
    } catch {
      return null
    }
  },

  async deleteWorkspace(workspaceId: string): Promise<boolean> {
    try {
      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}`, { method: 'DELETE' })
      return response.ok
    } catch {
      return false
    }
  },

  // TUTOR & RAG CHAT
  async sendTutorMessage(
    workspaceId: string,
    message: string,
    conversationId?: string
  ): Promise<TutorMessage> {
    try {
      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/tutor`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          conversation_id: conversationId,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(
          errorData.detail || `Server returned HTTP ${response.status}`
        )
      }

      const data: BackendTutorResponse = await response.json()

      const mappedCitations: TutorCitation[] = data.citations.map((c) => ({
        id: c.id,
        documentId: c.document_id,
        documentName: c.document_name,
        pageOrSlide: c.page_or_slide,
        excerpt: c.excerpt,
        relevanceScore: c.relevance_score,
      }))

      return {
        id: data.message.id,
        workspaceId,
        role: 'assistant',
        content: data.message.content,
        timestamp:
          data.message.timestamp ||
          new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: mappedCitations,
        suggestedFollowUps: data.suggested_follow_ups || [
          'Can you walk through a concrete example?',
          'What are common edge cases?',
          'Quiz me on this concept',
        ],
      }
    } catch {
      // In server-side/Node context where HTTP server isn't listening, execute via direct ragEngine
      const { ragEngine } = await import('@/lib/server/rag-engine')
      const { answer, citations, isGrounded } = await ragEngine.generateGroundedAnswer(
        workspaceId,
        message
      )
      return {
        id: `tm_a_${Date.now()}`,
        workspaceId,
        role: 'assistant',
        content: answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations,
        suggestedFollowUps: isGrounded
          ? [
              'Can you explain this concept in more depth?',
              'What are common edge cases or practical examples?',
              'Quiz me on this concept',
            ]
          : [
              'How do I upload learning materials?',
              'What file formats are supported?',
            ],
      }
    }
  },

  // DOCUMENT INGESTION
  async uploadDocument(
    workspaceId: string,
    file: File,
    title?: string
  ): Promise<WorkspaceDocument> {
    try {
      const formData = new FormData()
      formData.append('file', file)
      if (title) {
        formData.append('title', title)
      }

      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/documents`, {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `Failed to upload document (HTTP ${response.status})`)
      }

      const doc = await response.json()
      return {
        id: doc.id,
        workspaceId: doc.workspace_id || doc.workspaceId,
        title: doc.title,
        filename: doc.filename,
        type: doc.file_type || doc.type,
        sizeBytes: doc.file_size || doc.sizeBytes,
        pagesCount: doc.page_count || doc.pagesCount,
        status: doc.status,
        chunksCount: doc.chunk_count || doc.chunksCount,
        uploadedAt: doc.created_at ? doc.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
        summary: doc.summary,
      }
    } catch {
      const { ragEngine } = await import('@/lib/server/rag-engine')
      const arrayBuf = await file.arrayBuffer()
      const buffer = Buffer.from(arrayBuf)
      const docTitle = title || file.name.replace(/\.[^/.]+$/, '')
      const ext = file.name.toLowerCase()
      const fType: 'pdf' | 'docx' | 'pptx' = ext.endsWith('.docx')
        ? 'docx'
        : ext.endsWith('.pptx')
        ? 'pptx'
        : 'pdf'

      return ragEngine.addDocument(workspaceId, docTitle, file.name, buffer, fType)
    }
  },

  async getWorkspaceDocuments(workspaceId: string): Promise<WorkspaceDocument[]> {
    try {
      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/documents`)
      if (!response.ok) return []
      const data = await response.json()
      return (data.documents || []).map((doc: any) => ({
        id: doc.id,
        workspaceId: doc.workspace_id || doc.workspaceId,
        title: doc.title,
        filename: doc.filename,
        type: doc.file_type || doc.type,
        sizeBytes: doc.file_size || doc.sizeBytes,
        pagesCount: doc.page_count || doc.pagesCount,
        status: doc.status,
        chunksCount: doc.chunk_count || doc.chunksCount,
        uploadedAt: doc.created_at ? doc.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
        summary: doc.summary,
      }))
    } catch {
      return []
    }
  },

  async deleteDocument(documentId: string): Promise<boolean> {
    try {
      const response = await apiFetch(`/api/v1/documents/${documentId}`, { method: 'DELETE' })
      return response.ok
    } catch {
      return false
    }
  },
}
