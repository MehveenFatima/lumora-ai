import type { TutorMessage, TutorCitation, WorkspaceDocument, Workspace } from '../types/domain'
import { localToday } from '../dates'

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

export interface HealthData {
  status: string
  service?: string
  version?: string
  backend?: string
  presentation_mode?: boolean
  database?: {
    status?: string
    type?: string
    pool_active?: boolean
    url_configured?: boolean
    error?: string
  }
  vector?: {
    capability?: string
    provider?: string
    dimensions?: number
  }
  gemini?: {
    configured?: boolean
    model?: string
    embedding_model?: string
  }
  ai?: {
    status?: 'healthy' | 'degraded' | 'unavailable' | string
    gateway_status?: string
    fallback_available?: boolean
    providers?: Record<
      string,
      {
        configured?: boolean
        status?: string
        model?: string
        consecutive_failures?: number
        success_count?: number
        cooldown_remaining_seconds?: number
        last_error?: string
      }
    >
    routing?: Record<string, { primary?: string; fallback?: string }>
  }
  storage?: {
    status?: string
    bucket?: string
  }
  timestamp?: string
}

const DEFAULT_SERVER_BACKEND_URL = 'http://127.0.0.1:8000'
function mapDocument(doc: any): WorkspaceDocument {
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
    errorMessage: doc.error_message || undefined,
  }
}

// Quiz creation and next-batch generate questions with the AI provider; match the 60 s proxy limit
const QUIZ_GENERATION_TIMEOUT_MS = 60000

function getBaseUrl(): string {
  if (typeof window !== 'undefined') {
    // In browser: strictly relative path, always routed through Next.js proxy
    return ''
  }
  // In server-side Node.js / SSR: absolute URL to FastAPI backend
  return process.env.BACKEND_API_URL || DEFAULT_SERVER_BACKEND_URL
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const isBrowser = typeof window !== 'undefined'
  let cleanPath = path
  if (cleanPath.startsWith('http://') || cleanPath.startsWith('https://')) {
    try {
      const parsed = new URL(cleanPath)
      cleanPath = parsed.pathname + parsed.search
    } catch {
      // ignore
    }
  }
  if (!cleanPath.startsWith('/')) {
    cleanPath = `/${cleanPath}`
  }
  // Browser requests MUST ALWAYS be relative to use the Next.js /api/v1 proxy
  const url = isBrowser ? cleanPath : `${getBaseUrl()}${cleanPath}`

  const headers = new Headers(options.headers || {})
  if (isBrowser) {
    // The learner's local date, so date rules (e.g. target completion dates) follow their calendar
    headers.set('X-Client-Date', localToday())
  }
  const fetchOptions: RequestInit = {
    ...options,
    headers,
    signal: options.signal || AbortSignal.timeout(30000),
  }

  try {
    const res = await fetch(url, fetchOptions)
    // Session expired or missing: send the user to sign in, then back to where they were
    if (res.status === 401 && isBrowser && !window.location.pathname.startsWith('/login')) {
      const next = encodeURIComponent(window.location.pathname + window.location.search)
      // Clear the stale cookie first, otherwise the route guard would bounce back to /dashboard
      await fetch('/api/v1/auth/logout', { method: 'POST' }).catch(() => null)
      window.location.assign(`/login?next=${next}`)
    }
    return res
  } catch (err: any) {
    console.error(`[API Client] apiFetch failed for endpoint ${cleanPath}:`, err)
    const isTimeout = err?.name === 'TimeoutError' || err?.message?.includes('timeout') || err?.message?.includes('aborted')
    if (isTimeout) {
      const timeoutErr: any = new Error(`Request to '${cleanPath}' timed out.`)
      timeoutErr.code = 'TIMEOUT'
      throw timeoutErr
    }
    throw new Error(
      `Unable to reach backend service via '${cleanPath}'. (${err?.message || err})`
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
      const errorDetail =
        err.detail ||
        err.message ||
        err.error ||
        (response.status === 500
          ? 'Backend server error (HTTP 500): please verify backend service is operational.'
          : `Failed to create workspace on backend (HTTP ${response.status})`)
      throw new Error(errorDetail)
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

  async getWorkspaces(init: RequestInit = {}): Promise<Workspace[]> {
    try {
      const response = await apiFetch('/api/v1/workspaces', init)
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

  async getWorkspaceById(workspaceId: string, init: RequestInit = {}): Promise<Workspace | null> {
    try {
      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}`, init)
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

    const mappedCitations: TutorCitation[] = (data.citations || []).map((c) => ({
      id: c.id,
      documentId: c.document_id,
      documentName: c.document_name,
      pageOrSlide: c.page_or_slide,
      excerpt: c.excerpt,
      relevanceScore: c.relevance_score,
    }))

    return {
      id: data.message?.id || 'msg-fallback',
      workspaceId,
      conversationId: data.conversation_id,
      role: 'assistant',
      content: data.message?.content || '',
      timestamp: data.message?.timestamp || new Date().toISOString(),
      citations: mappedCitations,
      suggestedFollowUps: data.suggested_follow_ups || [
        'Can you walk through a concrete example?',
        'What are common edge cases?',
        'Quiz me on this concept',
      ],
    }
  },

  async askTutor(
    workspaceId: string,
    message: string,
    conversationId?: string,
    currentDocumentId?: string
  ): Promise<TutorMessage> {
    return this.sendTutorMessage(workspaceId, message, conversationId, currentDocumentId)
  },

  async getTutorHistory(
    workspaceId: string,
    conversationId?: string
  ): Promise<{ conversationId: string; messages: TutorMessage[] }> {
    try {
      const url = conversationId
        ? `/api/v1/workspaces/${workspaceId}/tutor/history?conversation_id=${encodeURIComponent(conversationId)}`
        : `/api/v1/workspaces/${workspaceId}/tutor/history`
      const response = await apiFetch(url)
      if (!response.ok) {
        return { conversationId: '', messages: [] }
      }
      const data = await response.json()
      const convId = data.conversation_id || ''
      const messages: TutorMessage[] = (data.messages || []).map((m: any) => ({
        id: m.id,
        workspaceId,
        conversationId: convId,
        role: m.role,
        content: m.content,
        timestamp: m.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: [],
        suggestedFollowUps: [],
      }))
      return { conversationId: convId, messages }
    } catch {
      return { conversationId: '', messages: [] }
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

    // Small files are processed within the request; larger ones return 202 and finish in the
    // background (follow them with getDocument). Allow time for the file itself to upload.
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/documents`, {
      method: 'POST',
      body: formData,
      signal: AbortSignal.timeout(300000),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `Failed to upload document (HTTP ${response.status})`)
    }

    return mapDocument(await response.json())
  },

  /** One document's current state; used to follow uploads that finish in the background. */
  async getDocument(documentId: string): Promise<WorkspaceDocument | null> {
    try {
      const response = await apiFetch(`/api/v1/documents/${documentId}`)
      if (!response.ok) return null
      return mapDocument(await response.json())
    } catch {
      return null
    }
  },

  async getWorkspaceDocuments(workspaceId: string): Promise<WorkspaceDocument[]> {
    try {
      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/documents`)
      if (!response.ok) return []
      const data = await response.json()
      return (data.documents || []).map(mapDocument)
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
  async getActiveQuizSession(workspaceId: string): Promise<any> {
    try {
      const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/active`)
      if (response.status === 404 || !response.ok) {
        return null
      }
      return await response.json()
    } catch {
      return null
    }
  },

  async createQuizSession(
    workspaceId: string,
    data: { targetQuestionCount?: number; topic?: string; initialDifficulty?: number } = {}
  ): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // Question generation calls the AI provider, so allow as long as the API proxy does
      signal: AbortSignal.timeout(QUIZ_GENERATION_TIMEOUT_MS),
      body: JSON.stringify({
        target_question_count: data.targetQuestionCount || 5,
        topic: data.topic,
        initial_difficulty: data.initialDifficulty || 2,
      }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      const code =
        err.code ||
        err.detail?.code ||
        (typeof err.detail === 'string' && err.detail.includes('NO_INDEXED_DOCUMENTS')
          ? 'NO_INDEXED_DOCUMENTS'
          : null)
      const message =
        err.message ||
        err.detail?.message ||
        (typeof err.detail === 'string'
          ? err.detail
          : `Failed to create quiz session (HTTP ${response.status})`)
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
      signal: AbortSignal.timeout(QUIZ_GENERATION_TIMEOUT_MS),
      body: JSON.stringify({
        batch_size: data.batchSize || 5,
      }),
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      const code = err.code || err.detail?.code || null
      const message =
        err.message ||
        err.detail?.message ||
        (typeof err.detail === 'string'
          ? err.detail
          : `Failed to start next quiz batch (HTTP ${response.status})`)
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
      throw new Error(err.message || err.detail || `Failed to fetch quiz session (HTTP ${response.status})`)
    }
    return response.json()
  },

  async getQuizSummary(workspaceId: string, quizId: string): Promise<any> {
    return this.getQuizSession(workspaceId, quizId)
  },

  async getQuizQuestion(workspaceId: string, quizId: string, questionId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/${quizId}/questions/${questionId}`)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.message || err.detail || `Failed to fetch quiz question (HTTP ${response.status})`)
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
      throw new Error(err.message || err.detail || `Failed to submit quiz attempt (HTTP ${response.status})`)
    }
    return response.json()
  },

  async submitAttempt(
    workspaceId: string,
    quizId: string,
    questionId: string,
    data: { selectedOption: string; responseTimeMs: number }
  ): Promise<any> {
    return this.submitQuizAttempt(workspaceId, quizId, questionId, data)
  },

  async completeQuizSession(workspaceId: string, quizId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/quizzes/${quizId}/complete`, {
      method: 'POST',
    })

    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.message || err.detail || `Failed to complete quiz (HTTP ${response.status})`)
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

  // ----------------------------------------------------
  // PHASE 3: TOPIC MASTERY & LEARNER KNOWLEDGE PROFILE
  // ----------------------------------------------------
  async getWorkspaceMastery(workspaceId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/mastery`)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to fetch workspace mastery (HTTP ${response.status})`)
    }
    return response.json()
  },

  async getTopicMasteryList(workspaceId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/mastery/topics`)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to fetch topic mastery list (HTTP ${response.status})`)
    }
    return response.json()
  },

  async getTopicDetail(workspaceId: string, topicName: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/mastery/topics/${encodeURIComponent(topicName)}`)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to fetch topic details for '${topicName}' (HTTP ${response.status})`)
    }
    return response.json()
  },

  async getLearnerProfile(workspaceId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/learner-profile`)
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `Failed to fetch learner profile (HTTP ${response.status})`)
    }
    return response.json()
  },

  // 6. FLASHCARDS, STUDY PLAN & ACTIVITY API METHODS
  async getFlashcards(workspaceId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/flashcards`)
    if (!response.ok) return { workspace_id: workspaceId, total_count: 0, flashcards: [] }
    return response.json()
  },

  async getMasteryHistory(workspaceId: string, days = 30): Promise<{ points: { date: string; mastery_percentage: number }[] }> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/mastery/history?days=${days}`)
    if (!response.ok) return { points: [] }
    return response.json()
  },

  async reviewFlashcard(
    workspaceId: string,
    cardId: string,
    rating: 'again' | 'hard' | 'good' | 'easy'
  ): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/flashcards/${cardId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rating }),
    })
    if (!response.ok) throw new Error(`Failed to save flashcard review (${response.status})`)
    return response.json()
  },

  async generateFlashcards(workspaceId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/flashcards/generate`, {
      method: 'POST',
    })
    if (!response.ok) return { workspace_id: workspaceId, total_count: 0, flashcards: [] }
    return response.json()
  },

  async getStudyPlan(workspaceId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/study-plan`)
    if (!response.ok) return null
    return response.json()
  },

  /** Updates a workspace's target completion date and/or daily target. Throws with the API's message. */
  async updateWorkspace(
    workspaceId: string,
    data: { targetDate?: string; dailyTargetMinutes?: number; name?: string; goal?: string },
  ): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_date: data.targetDate,
        daily_target_minutes: data.dailyTargetMinutes,
        name: data.name,
        goal: data.goal,
      }),
    })
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = body?.detail
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail) && detail[0]?.msg
            ? String(detail[0].msg).replace(/^Value error, /, '')
            : `Could not update the workspace (HTTP ${response.status})`
      throw new Error(message)
    }
    return body
  },

  async toggleStudyTask(workspaceId: string, taskId: string): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/study-plan/tasks/${taskId}/toggle`, {
      method: 'POST',
    })
    if (!response.ok) return null
    return response.json()
  },

  async getActivities(workspaceId?: string): Promise<any> {
    const url = workspaceId
      ? `/api/v1/workspaces/${workspaceId}/activity`
      : `/api/v1/activities`
    const response = await apiFetch(url)
    if (!response.ok) return { total_count: 0, activities: [] }
    return response.json()
  },

  async addActivity(workspaceId: string, data: { event_type: string; title: string; description: string }): Promise<any> {
    const response = await apiFetch(`/api/v1/workspaces/${workspaceId}/activity`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (!response.ok) return null
    return response.json()
  },

  async getHealth(): Promise<HealthData> {
    const response = await apiFetch('/api/v1/health')
    if (!response.ok) {
      throw new Error(`Health check failed (HTTP ${response.status})`)
    }
    return response.json()
  },
}
