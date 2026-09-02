import { TutorMessage, TutorCitation, WorkspaceDocument, Workspace } from '@/lib/types/domain'

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

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
  }
  suggested_follow_ups?: string[]
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
    const url = `${API_BASE_URL}/api/v1/workspaces`
    const response = await fetch(url, {
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
      targetDate: ws.target_date || '2026-12-31',
      dailyTargetMinutes: ws.daily_target_minutes || 45,
      description: ws.description || '',
      overallMastery: ws.overall_mastery || 0,
      masteryDelta: ws.mastery_delta || 0,
      status: ws.status || 'active',
      iconName: ws.icon_name || 'FolderKanban',
      documentCount: ws.document_count || 0,
      topicsCount: 0,
      flashcardsDueCount: 0,
      lastActive: 'Just now',
      createdAt: ws.created_at ? ws.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
    }
  },

  async getWorkspaces(): Promise<Workspace[]> {
    const url = `${API_BASE_URL}/api/v1/workspaces`
    try {
      const response = await fetch(url)
      if (!response.ok) return []
      const data = await response.json()
      return (data.workspaces || []).map((ws: any) => ({
        id: ws.id,
        name: ws.name,
        goal: ws.goal,
        level: ws.level,
        targetDate: ws.target_date || '2026-12-31',
        dailyTargetMinutes: ws.daily_target_minutes || 45,
        description: ws.description || '',
        overallMastery: ws.overall_mastery || 0,
        masteryDelta: ws.mastery_delta || 0,
        status: ws.status || 'active',
        iconName: ws.icon_name || 'FolderKanban',
        documentCount: ws.document_count || 0,
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
    const url = `${API_BASE_URL}/api/v1/workspaces/${workspaceId}`
    try {
      const response = await fetch(url)
      if (!response.ok) return null
      const ws = await response.json()
      return {
        id: ws.id,
        name: ws.name,
        goal: ws.goal,
        level: ws.level,
        targetDate: ws.target_date || '2026-12-31',
        dailyTargetMinutes: ws.daily_target_minutes || 45,
        description: ws.description || '',
        overallMastery: ws.overall_mastery || 0,
        masteryDelta: ws.mastery_delta || 0,
        status: ws.status || 'active',
        iconName: ws.icon_name || 'FolderKanban',
        documentCount: ws.document_count || 0,
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
    const url = `${API_BASE_URL}/api/v1/workspaces/${workspaceId}`
    try {
      const response = await fetch(url, { method: 'DELETE' })
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
    const url = `${API_BASE_URL}/api/v1/workspaces/${workspaceId}/tutor`

    try {
      const response = await fetch(url, {
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
    } catch (err: any) {
      console.warn('FastAPI backend request failed, falling back to local grounded synthesis:', err.message)
      throw err
    }
  },

  // DOCUMENT INGESTION
  async uploadDocument(
    workspaceId: string,
    file: File,
    title?: string
  ): Promise<WorkspaceDocument> {
    const url = `${API_BASE_URL}/api/v1/workspaces/${workspaceId}/documents`
    const formData = new FormData()
    formData.append('file', file)
    if (title) {
      formData.append('title', title)
    }

    const response = await fetch(url, {
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
      workspaceId: doc.workspace_id,
      title: doc.title,
      filename: doc.filename,
      type: doc.file_type,
      sizeBytes: doc.file_size,
      pagesCount: doc.page_count,
      status: doc.status,
      chunksCount: doc.chunk_count,
      uploadedAt: doc.created_at ? doc.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
      summary: doc.summary,
    }
  },

  async getWorkspaceDocuments(workspaceId: string): Promise<WorkspaceDocument[]> {
    const url = `${API_BASE_URL}/api/v1/workspaces/${workspaceId}/documents`
    try {
      const response = await fetch(url)
      if (!response.ok) return []
      const data = await response.json()
      return (data.documents || []).map((doc: any) => ({
        id: doc.id,
        workspaceId: doc.workspace_id,
        title: doc.title,
        filename: doc.filename,
        type: doc.file_type,
        sizeBytes: doc.file_size,
        pagesCount: doc.page_count,
        status: doc.status,
        chunksCount: doc.chunk_count,
        uploadedAt: doc.created_at ? doc.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
        summary: doc.summary,
      }))
    } catch {
      return []
    }
  },

  async deleteDocument(documentId: string): Promise<boolean> {
    const url = `${API_BASE_URL}/api/v1/documents/${documentId}`
    try {
      const response = await fetch(url, { method: 'DELETE' })
      return response.ok
    } catch {
      return false
    }
  },
}
