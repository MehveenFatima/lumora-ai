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

function getBaseUrl(): string {
  if (typeof window !== 'undefined') {
    // In browser: relative path for Next.js proxy rewrite
    return ''
  }
  // In server-side Node.js / SSR: absolute URL to FastAPI backend
  return process.env.BACKEND_API_URL || 'http://127.0.0.1:8000'
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const base = getBaseUrl()
  const cleanPath = path.startsWith('/') ? path : `/${path}`
  const url = path.startsWith('http') ? path : `${base}${cleanPath}`

  try {
    const res = await fetch(url, options)
    return res
  } catch (err: any) {
    console.error(`apiFetch failed for endpoint ${url}:`, err)
    throw new Error(
      `Unable to reach backend at '${url}'. Please ensure FastAPI is running on http://127.0.0.1:8000. (${err?.message || err})`
    )
  }
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
    conversationId?: string,
    currentDocumentId?: string
  ): Promise<TutorMessage> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/tutor`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        current_document_id: currentDocumentId,
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
  },

  // DOCUMENT INGESTION
  async uploadDocument(
    workspaceId: string,
    file: File,
    title?: string
  ): Promise<WorkspaceDocument> {
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

  // 4. QUIZ API METHODS
  async createQuizSession(
    workspaceId: string,
    data: { targetQuestionCount?: number; topic?: string; initialDifficulty?: number } = {}
  ): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_question_count: data.targetQuestionCount || 5,
        topic: data.topic,
        initial_difficulty: data.initialDifficulty || 2,
      }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      const code = err.detail?.code || (typeof err.detail === 'string' && err.detail.includes('NO_INDEXED_DOCUMENTS') ? 'NO_INDEXED_DOCUMENTS' : null)
      const message = err.detail?.message || (typeof err.detail === 'string' ? err.detail : `Failed to create quiz session (HTTP ${response.status})`)
      const errorObj: any = new Error(message)
      if (code) errorObj.code = code
      throw errorObj
    }
    return response.json()
  },

  async startNextQuizBatch(
    workspaceId: string,
    quizId: string,
    data: { batchSize?: number } = {}
  ): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/${quizId}/next-batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        batch_size: data.batchSize || 5,
      }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      const code = err.detail?.code || null
      const message = err.detail?.message || (typeof err.detail === 'string' ? err.detail : `Failed to start next quiz batch (HTTP ${response.status})`)
      const errorObj: any = new Error(message)
      if (code) errorObj.code = code
      throw errorObj
    }
    return response.json()
  },

  async getQuizSession(workspaceId: string, quizId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/${quizId}`)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to fetch quiz session (HTTP ${response.status})`)
    }
    return response.json()
  },

  async getQuizQuestion(workspaceId: string, quizId: string, questionId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/${quizId}/questions/${questionId}`)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to fetch quiz question (HTTP ${response.status})`)
    }
    return response.json()
  },

  async submitQuizAttempt(
    workspaceId: string,
    quizId: string,
    questionId: string,
    data: { selectedOption: string; responseTimeMs: number }
  ): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/${quizId}/questions/${questionId}/attempt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        selected_option: data.selectedOption,
        response_time_ms: data.responseTimeMs,
      }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to submit quiz attempt (HTTP ${response.status})`)
    }
    return response.json()
  },

  async completeQuizSession(workspaceId: string, quizId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/${quizId}/complete`, {
      method: 'POST',
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to complete quiz (HTTP ${response.status})`)
    }
    return response.json()
  },

  async getQuizHistory(workspaceId: string): Promise<any> {
    try {
      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/history`)
      if (!response.ok) return { sessions: [], total_count: 0 }
      return response.json()
    } catch {
      return { sessions: [], total_count: 0 }
    }
  },
}
