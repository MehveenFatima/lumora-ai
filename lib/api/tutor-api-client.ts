import { TutorMessage, TutorCitation, WorkspaceDocument } from '@/lib/types/domain'

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
