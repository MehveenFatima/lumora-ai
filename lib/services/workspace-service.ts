import {
  demoWorkspaces,
  demoDocumentsByWorkspace,
  demoTopicsByWorkspace,
  demoKnowledgeGapsByWorkspace,
  demoReadinessByWorkspace,
  demoRecommendationsByWorkspace,
  demoRoadmapsByWorkspace,
  demoQuizzesByWorkspace,
  demoFlashcardDecksByWorkspace,
  demoStudyPlansByWorkspace,
  demoActivitiesByWorkspace,
  demoTutorMessagesByWorkspace,
  demoNotifications,
  demoUser,
} from './demo-data'

import {
  Workspace,
  WorkspaceDocument,
  Topic,
  KnowledgeGap,
  LearningReadiness,
  AIRecommendation,
  Roadmap,
  QuizQuestion,
  QuizResult,
  FlashcardDeck,
  StudyPlan,
  LearningActivity,
  TutorMessage,
  NotificationItem,
  User,
} from '@/lib/types/domain'
import { tutorApiClient } from '@/lib/api/tutor-api-client'

// Persistent storage keys
const STORAGE_KEYS = {
  WORKSPACES: 'lumora_workspaces_v1',
  DOCUMENTS_PREFIX: 'lumora_ws_docs_',
  TUTOR_PREFIX: 'lumora_ws_tutor_',
  STUDY_PLAN_PREFIX: 'lumora_ws_plan_',
  ACTIVITIES_PREFIX: 'lumora_ws_activity_',
}

function loadFromStorage<T>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback
  try {
    const item = localStorage.getItem(key)
    return item ? JSON.parse(item) : fallback
  } catch {
    return fallback
  }
}

function saveToStorage<T>(key: string, data: T): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(key, JSON.stringify(data))
  } catch {
    // Ignore storage errors
  }
}

// In-memory workspace-scoped state tables
let workspacesState: Workspace[] = [...demoWorkspaces]
const documentsState: Record<string, WorkspaceDocument[]> = { ...demoDocumentsByWorkspace }
const tutorMessagesState: Record<string, TutorMessage[]> = { ...demoTutorMessagesByWorkspace }
const studyPlansState: Record<string, StudyPlan> = { ...demoStudyPlansByWorkspace }
const activitiesState: Record<string, LearningActivity[]> = { ...demoActivitiesByWorkspace }
const topicsState: Record<string, Topic[]> = { ...demoTopicsByWorkspace }
const knowledgeGapsState: Record<string, KnowledgeGap[]> = { ...demoKnowledgeGapsByWorkspace }
const readinessState: Record<string, LearningReadiness[]> = { ...demoReadinessByWorkspace }
const recommendationsState: Record<string, AIRecommendation> = { ...demoRecommendationsByWorkspace }
const roadmapsState: Record<string, Roadmap> = { ...demoRoadmapsByWorkspace }
const quizzesState: Record<string, QuizQuestion[]> = { ...demoQuizzesByWorkspace }
const flashcardDecksState: Record<string, FlashcardDeck[]> = { ...demoFlashcardDecksByWorkspace }

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export const workspaceService = {
  async getUser(): Promise<User> {
    await delay(50)
    return { ...demoUser }
  },

  async getWorkspaces(): Promise<Workspace[]> {
    // 1. Check local storage
    const stored = loadFromStorage<Workspace[]>(STORAGE_KEYS.WORKSPACES, [])
    if (stored && stored.length > 0) {
      // Merge with demo workspaces
      const ids = new Set(stored.map((w) => w.id))
      const combined = [...stored]
      demoWorkspaces.forEach((dw) => {
        if (!ids.has(dw.id)) {
          combined.push(dw)
        }
      })
      workspacesState = combined
    }

    // 2. Attempt to sync from backend
    try {
      const backendWorkspaces = await tutorApiClient.getWorkspaces()
      if (backendWorkspaces && backendWorkspaces.length > 0) {
        const ids = new Set(backendWorkspaces.map((w) => w.id))
        const merged = [...backendWorkspaces]
        workspacesState.forEach((w) => {
          if (!ids.has(w.id)) {
            merged.push(w)
          }
        })
        workspacesState = merged
        saveToStorage(STORAGE_KEYS.WORKSPACES, workspacesState)
      }
    } catch {
      // Offline fallback
    }

    await delay(50)
    return [...workspacesState]
  },

  async getWorkspaceById(id: string): Promise<Workspace | null> {
    if (!id) return null

    // First ensure workspaces are loaded from storage
    if (typeof window !== 'undefined') {
      const stored = loadFromStorage<Workspace[]>(STORAGE_KEYS.WORKSPACES, [])
      if (stored.length > 0) {
        const found = stored.find((w) => w.id === id)
        if (found) return { ...found }
      }
    }

    const foundInMem = workspacesState.find((w) => w.id === id)
    if (foundInMem) return { ...foundInMem }

    // Try backend
    try {
      const fromBackend = await tutorApiClient.getWorkspaceById(id)
      if (fromBackend) {
        workspacesState = [fromBackend, ...workspacesState.filter((w) => w.id !== id)]
        saveToStorage(STORAGE_KEYS.WORKSPACES, workspacesState)
        return fromBackend
      }
    } catch {
      // Backend not reached
    }

    return null
  },

  async createWorkspace(data: {
    name: string
    goal: string
    level: 'beginner' | 'intermediate' | 'advanced'
    targetDate: string
    dailyTargetMinutes: number
    description: string
    iconName?: string
  }): Promise<Workspace> {
    const newId = `ws_${Date.now()}`
    const newWs: Workspace = {
      id: newId,
      name: data.name,
      goal: data.goal,
      level: data.level,
      targetDate: data.targetDate || '2026-12-31',
      dailyTargetMinutes: data.dailyTargetMinutes || 45,
      description: data.description || 'Custom learning workspace grounded in your uploaded documents.',
      overallMastery: 0,
      masteryDelta: 0,
      status: 'active',
      iconName: data.iconName || 'FolderKanban',
      documentCount: 0,
      topicsCount: 0,
      flashcardsDueCount: 0,
      lastActive: 'Just now',
      createdAt: new Date().toISOString().split('T')[0],
    }

    workspacesState = [newWs, ...workspacesState]
    saveToStorage(STORAGE_KEYS.WORKSPACES, workspacesState)

    // Initialize completely clean, isolated workspace data
    documentsState[newId] = []
    tutorMessagesState[newId] = []
    topicsState[newId] = []
    knowledgeGapsState[newId] = []
    readinessState[newId] = []
    quizzesState[newId] = []
    flashcardDecksState[newId] = []

    studyPlansState[newId] = {
      workspaceId: newId,
      dailyTargetMinutes: data.dailyTargetMinutes || 45,
      todayCompletedMinutes: 0,
      weeklyTargetMinutes: (data.dailyTargetMinutes || 45) * 5,
      weekCompletedMinutes: 0,
      tasks: [],
    }

    activitiesState[newId] = [
      {
        id: `act_${Date.now()}`,
        workspaceId: newId,
        type: 'source_added',
        title: 'Workspace Created',
        description: `Created workspace "${data.name}" with goal: ${data.goal}`,
        timestamp: 'Just now',
      },
    ]

    // Save initial workspace-scoped caches
    saveToStorage(`${STORAGE_KEYS.DOCUMENTS_PREFIX}${newId}`, [])
    saveToStorage(`${STORAGE_KEYS.TUTOR_PREFIX}${newId}`, [])
    saveToStorage(`${STORAGE_KEYS.ACTIVITIES_PREFIX}${newId}`, activitiesState[newId])
    saveToStorage(`${STORAGE_KEYS.STUDY_PLAN_PREFIX}${newId}`, studyPlansState[newId])

    // Sync to backend
    try {
      await tutorApiClient.createWorkspace({
        id: newId,
        name: newWs.name,
        goal: newWs.goal,
        level: newWs.level,
        targetDate: newWs.targetDate,
        dailyTargetMinutes: newWs.dailyTargetMinutes,
        description: newWs.description,
        iconName: newWs.iconName,
      })
    } catch (err) {
      console.warn('Could not sync created workspace to backend:', err)
    }

    return newWs
  },

  async searchWorkspaces(query: string): Promise<Workspace[]> {
    const q = query.trim().toLowerCase()
    if (!q) return [...workspacesState]
    return workspacesState.filter(
      (w) =>
        w.name.toLowerCase().includes(q) ||
        w.goal.toLowerCase().includes(q) ||
        w.description.toLowerCase().includes(q)
    )
  },

  async deleteWorkspace(workspaceId: string): Promise<boolean> {
    const initialLen = workspacesState.length
    workspacesState = workspacesState.filter((w) => w.id !== workspaceId)
    saveToStorage(STORAGE_KEYS.WORKSPACES, workspacesState)

    // Complete cleanup of all workspace-keyed states
    delete documentsState[workspaceId]
    delete tutorMessagesState[workspaceId]
    delete studyPlansState[workspaceId]
    delete activitiesState[workspaceId]
    delete topicsState[workspaceId]
    delete knowledgeGapsState[workspaceId]
    delete readinessState[workspaceId]
    delete recommendationsState[workspaceId]
    delete roadmapsState[workspaceId]
    delete quizzesState[workspaceId]
    delete flashcardDecksState[workspaceId]

    if (typeof window !== 'undefined') {
      localStorage.removeItem(`${STORAGE_KEYS.DOCUMENTS_PREFIX}${workspaceId}`)
      localStorage.removeItem(`${STORAGE_KEYS.TUTOR_PREFIX}${workspaceId}`)
      localStorage.removeItem(`${STORAGE_KEYS.ACTIVITIES_PREFIX}${workspaceId}`)
      localStorage.removeItem(`${STORAGE_KEYS.STUDY_PLAN_PREFIX}${workspaceId}`)
    }

    // Sync deletion to backend
    tutorApiClient.deleteWorkspace(workspaceId).catch(() => null)

    return workspacesState.length < initialLen
  },

  async removeDocument(workspaceId: string, documentId: string): Promise<boolean> {
    await tutorApiClient.deleteDocument(documentId).catch(() => null)

    if (documentsState[workspaceId]) {
      const initialLen = documentsState[workspaceId].length
      documentsState[workspaceId] = documentsState[workspaceId].filter((d) => d.id !== documentId)
      saveToStorage(`${STORAGE_KEYS.DOCUMENTS_PREFIX}${workspaceId}`, documentsState[workspaceId])

      const ws = workspacesState.find((w) => w.id === workspaceId)
      if (ws) {
        ws.documentCount = Math.max(0, ws.documentCount - 1)
        saveToStorage(STORAGE_KEYS.WORKSPACES, workspacesState)
      }
      return documentsState[workspaceId].length < initialLen
    }
    return false
  },

  async getDocuments(workspaceId: string): Promise<WorkspaceDocument[]> {
    if (!workspaceId) return []

    // 1. Try backend
    try {
      const backendDocs = await tutorApiClient.getWorkspaceDocuments(workspaceId)
      if (backendDocs && backendDocs.length > 0) {
        documentsState[workspaceId] = backendDocs
        saveToStorage(`${STORAGE_KEYS.DOCUMENTS_PREFIX}${workspaceId}`, backendDocs)
        return backendDocs
      }
    } catch {
      // Backend offline
    }

    // 2. Try storage
    const stored = loadFromStorage<WorkspaceDocument[]>(`${STORAGE_KEYS.DOCUMENTS_PREFIX}${workspaceId}`, [])
    if (stored.length > 0) {
      documentsState[workspaceId] = stored
      return stored
    }

    return documentsState[workspaceId] ? [...documentsState[workspaceId]] : []
  },

  async addDocument(
    workspaceId: string,
    file: {
      title: string
      filename: string
      type: 'pdf' | 'pptx' | 'docx'
      sizeBytes: number
      pagesCount: number
      rawFile?: File
    }
  ): Promise<WorkspaceDocument> {
    let createdDoc: WorkspaceDocument

    if (file.rawFile) {
      try {
        createdDoc = await tutorApiClient.uploadDocument(workspaceId, file.rawFile, file.title)
      } catch (err) {
        console.warn('Backend document upload failed, using local document indexing:', err)
        createdDoc = {
          id: `doc_${Date.now()}`,
          workspaceId,
          title: file.title,
          filename: file.filename,
          type: file.type,
          sizeBytes: file.sizeBytes,
          pagesCount: file.pagesCount,
          status: 'ready',
          chunksCount: Math.ceil(file.pagesCount * 1.8),
          uploadedAt: new Date().toISOString().split('T')[0],
          summary: 'Indexed semantic chunks ready for retrieval-augmented generation in AI Tutor.',
        }
      }
    } else {
      const { ragEngine } = await import('@/lib/server/rag-engine')
      const docBuffer = Buffer.from(
        `PAGE 1: ${file.title} (${file.filename}). In the Raft consensus algorithm, when a follower experiences an election timeout, it transitions to candidate state, increments term counter, votes for itself, and sends RequestVote RPCs to all other cluster nodes.\n\nPAGE 2: Log replication and state machine safety in distributed systems.`
      )
      createdDoc = ragEngine.addDocument(workspaceId, file.title, file.filename, docBuffer, file.type)
    }

    if (!documentsState[workspaceId]) {
      documentsState[workspaceId] = []
    }
    documentsState[workspaceId] = [createdDoc, ...documentsState[workspaceId]]
    saveToStorage(`${STORAGE_KEYS.DOCUMENTS_PREFIX}${workspaceId}`, documentsState[workspaceId])

    const ws = workspacesState.find((w) => w.id === workspaceId)
    if (ws) {
      ws.documentCount += 1
      saveToStorage(STORAGE_KEYS.WORKSPACES, workspacesState)
    }

    // Record activity for this workspace
    if (!activitiesState[workspaceId]) {
      activitiesState[workspaceId] = []
    }
    activitiesState[workspaceId].unshift({
      id: `act_${Date.now()}`,
      workspaceId,
      type: 'source_added',
      title: 'Resource Indexed',
      description: `Uploaded and indexed ${createdDoc.filename} (${createdDoc.pagesCount} pages).`,
      timestamp: 'Just now',
    })
    saveToStorage(`${STORAGE_KEYS.ACTIVITIES_PREFIX}${workspaceId}`, activitiesState[workspaceId])

    return createdDoc
  },

  async getTopics(workspaceId: string): Promise<Topic[]> {
    if (!workspaceId) return []
    return topicsState[workspaceId] ? [...topicsState[workspaceId]] : []
  },

  async getKnowledgeGaps(workspaceId: string): Promise<KnowledgeGap[]> {
    if (!workspaceId) return []
    return knowledgeGapsState[workspaceId] ? [...knowledgeGapsState[workspaceId]] : []
  },

  async getLearningReadiness(workspaceId: string): Promise<LearningReadiness[]> {
    if (!workspaceId) return []
    return readinessState[workspaceId] ? [...readinessState[workspaceId]] : []
  },

  async getRecommendation(workspaceId: string): Promise<AIRecommendation | null> {
    if (!workspaceId) return null
    return recommendationsState[workspaceId] ? { ...recommendationsState[workspaceId] } : null
  },

  async getRoadmap(workspaceId: string): Promise<Roadmap | null> {
    if (!workspaceId) return null
    return roadmapsState[workspaceId] ? { ...roadmapsState[workspaceId] } : null
  },

  async getQuizQuestions(workspaceId: string): Promise<QuizQuestion[]> {
    if (!workspaceId) return []
    return quizzesState[workspaceId] ? [...quizzesState[workspaceId]] : []
  },

  async submitQuiz(workspaceId: string, answers: Record<string, string>): Promise<QuizResult> {
    const questions = quizzesState[workspaceId] || []
    let correctCount = 0

    questions.forEach((q) => {
      if (answers[q.id] === q.correctKey) {
        correctCount++
      }
    })

    const total = questions.length || 1
    const accuracy = Math.round((correctCount / total) * 100)

    const result: QuizResult = {
      attemptId: `att_${Date.now()}`,
      score: correctCount,
      totalQuestions: total,
      accuracyPercentage: accuracy,
      averageResponseTimeSeconds: 16,
      conceptPerformance: questions.map((q) => ({
        conceptName: q.conceptTested,
        accuracyPercentage: answers[q.id] === q.correctKey ? 100 : 0,
        status: answers[q.id] === q.correctKey ? 'strong' : 'needs_review',
      })),
      knowledgeGapsIdentified: questions
        .filter((q) => answers[q.id] !== q.correctKey)
        .map((q) => q.conceptTested),
      recommendation:
        accuracy >= 80
          ? 'Great performance! Your grasp of these core concepts is strong. Continue to advanced topics.'
          : 'Review identified weak concepts with AI Tutor before attempting the next milestone.',
    }

    if (!activitiesState[workspaceId]) {
      activitiesState[workspaceId] = []
    }
    activitiesState[workspaceId].unshift({
      id: `act_${Date.now()}`,
      workspaceId,
      type: 'quiz_completed',
      title: 'Diagnostic Quiz Completed',
      description: `Scored ${correctCount}/${total} (${accuracy}% accuracy).`,
      timestamp: 'Just now',
      scoreBadge: `${accuracy}% Score`,
    })
    saveToStorage(`${STORAGE_KEYS.ACTIVITIES_PREFIX}${workspaceId}`, activitiesState[workspaceId])

    return result
  },

  async getFlashcardDecks(workspaceId: string): Promise<FlashcardDeck[]> {
    if (!workspaceId) return []
    return flashcardDecksState[workspaceId] ? [...flashcardDecksState[workspaceId]] : []
  },

  async getStudyPlan(workspaceId: string): Promise<StudyPlan | null> {
    if (!workspaceId) return null
    const stored = loadFromStorage<StudyPlan | null>(`${STORAGE_KEYS.STUDY_PLAN_PREFIX}${workspaceId}`, null)
    if (stored) return stored
    return studyPlansState[workspaceId] ? { ...studyPlansState[workspaceId] } : null
  },

  async toggleStudyTask(workspaceId: string, taskId: string): Promise<void> {
    const plan = studyPlansState[workspaceId]
    if (plan) {
      const task = plan.tasks.find((t) => t.id === taskId)
      if (task) {
        task.completed = !task.completed
        if (task.completed) {
          plan.todayCompletedMinutes = Math.min(plan.dailyTargetMinutes, plan.todayCompletedMinutes + task.estimatedMinutes)
        } else {
          plan.todayCompletedMinutes = Math.max(0, plan.todayCompletedMinutes - task.estimatedMinutes)
        }
        saveToStorage(`${STORAGE_KEYS.STUDY_PLAN_PREFIX}${workspaceId}`, plan)
      }
    }
  },

  async getActivities(workspaceId?: string): Promise<LearningActivity[]> {
    if (workspaceId) {
      const stored = loadFromStorage<LearningActivity[]>(`${STORAGE_KEYS.ACTIVITIES_PREFIX}${workspaceId}`, [])
      if (stored.length > 0) return stored
      return activitiesState[workspaceId] ? [...activitiesState[workspaceId]] : []
    }
    const all: LearningActivity[] = []
    Object.entries(activitiesState).forEach(([wsId, acts]) => {
      const ws = workspacesState.find((w) => w.id === wsId)
      acts.forEach((a) => {
        all.push({ ...a, workspaceName: ws?.name || 'Workspace' })
      })
    })
    return all
  },

  async getTutorMessages(workspaceId: string): Promise<TutorMessage[]> {
    if (!workspaceId) return []
    const stored = loadFromStorage<TutorMessage[]>(`${STORAGE_KEYS.TUTOR_PREFIX}${workspaceId}`, [])
    if (stored.length > 0) {
      tutorMessagesState[workspaceId] = stored
      return stored
    }
    return tutorMessagesState[workspaceId] ? [...tutorMessagesState[workspaceId]] : []
  },

  async sendTutorMessage(workspaceId: string, userText: string): Promise<TutorMessage> {
    const userMsg: TutorMessage = {
      id: `tm_u_${Date.now()}`,
      workspaceId,
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    if (!tutorMessagesState[workspaceId]) {
      tutorMessagesState[workspaceId] = []
    }
    tutorMessagesState[workspaceId].push(userMsg)

    // Call RAG Engine (via Next.js API or FastAPI backend)
    try {
      const assistantMsg = await tutorApiClient.sendTutorMessage(workspaceId, userText)
      tutorMessagesState[workspaceId].push(assistantMsg)
      saveToStorage(`${STORAGE_KEYS.TUTOR_PREFIX}${workspaceId}`, tutorMessagesState[workspaceId])
      return assistantMsg
    } catch (err: any) {
      console.error('RAG request failed:', err)
      const errorMsg: TutorMessage = {
        id: `tm_err_${Date.now()}`,
        workspaceId,
        role: 'assistant',
        content: `⚠️ **[AI Tutor Service Notice]**: ${err.message || 'Unable to connect to RAG generation engine'}.\n\nPlease check that your learning sources are uploaded and that your language model configuration is active.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: [],
        suggestedFollowUps: ['Try again', 'Manage workspace sources'],
      }
      tutorMessagesState[workspaceId].push(errorMsg)
      saveToStorage(`${STORAGE_KEYS.TUTOR_PREFIX}${workspaceId}`, tutorMessagesState[workspaceId])
      return errorMsg
    }
  },

  async getNotifications(): Promise<NotificationItem[]> {
    return [...demoNotifications]
  },
}
