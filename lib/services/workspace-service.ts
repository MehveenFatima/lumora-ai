import {
  demoNotifications,
  demoUser,
  dsaTopics,
  dsaKnowledgeGaps,
  dsaLearningReadiness,
  dsaRecommendation,
  dsaRoadmap,
  dsaQuizQuestions,
  dsaFlashcardDecks,
  dsaStudyPlan,
  dsaLearningActivities,
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
  MasteryStatus,
} from '@/lib/types/domain'
import { tutorApiClient } from '@/lib/api/tutor-api-client'

// In-memory workspace-scoped state tables with presentation seed strictly for 'dsa'
let workspacesCache: Workspace[] = []
const documentsCache: Record<string, WorkspaceDocument[]> = {}
const tutorMessagesCache: Record<string, TutorMessage[]> = {}
const studyPlansCache: Record<string, StudyPlan> = {
  dsa: { ...dsaStudyPlan },
}
const activitiesCache: Record<string, LearningActivity[]> = {
  dsa: [...dsaLearningActivities],
}
const topicsCache: Record<string, Topic[]> = {
  dsa: [...dsaTopics],
}
const knowledgeGapsCache: Record<string, KnowledgeGap[]> = {
  dsa: [...dsaKnowledgeGaps],
}
const readinessCache: Record<string, LearningReadiness[]> = {
  dsa: [...dsaLearningReadiness],
}
const recommendationsCache: Record<string, AIRecommendation> = {
  dsa: { ...dsaRecommendation },
}
const roadmapsCache: Record<string, Roadmap> = {
  dsa: { ...dsaRoadmap },
}
const quizzesCache: Record<string, QuizQuestion[]> = {
  dsa: [...dsaQuizQuestions],
}
const flashcardDecksCache: Record<string, FlashcardDeck[]> = {
  dsa: [...dsaFlashcardDecks],
}

export const workspaceService = {
  async getUser(): Promise<User> {
    return { ...demoUser }
  },

  // 1. WORKSPACE METHODS (Authoritative Source: FastAPI + PostgreSQL)
  async getWorkspaces(): Promise<Workspace[]> {
    try {
      const backendWorkspaces = await tutorApiClient.getWorkspaces()
      if (backendWorkspaces) {
        workspacesCache = backendWorkspaces
        return [...workspacesCache]
      }
    } catch (err) {
      console.error('Failed to fetch workspaces from FastAPI backend:', err)
    }
    return [...workspacesCache]
  },

  async getWorkspaceById(id: string): Promise<Workspace | null> {
    if (!id) return null

    try {
      const fromBackend = await tutorApiClient.getWorkspaceById(id)
      if (fromBackend) {
        workspacesCache = [fromBackend, ...workspacesCache.filter((w) => w.id !== id)]
        return fromBackend
      }
      return null
    } catch (err) {
      console.error(`Failed to fetch workspace '${id}' from backend:`, err)
      const found = workspacesCache.find((w) => w.id === id)
      return found ? { ...found } : null
    }
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
    // 1. Authoritative Backend INSERT
    const created = await tutorApiClient.createWorkspace({
      name: data.name,
      goal: data.goal,
      level: data.level,
      targetDate: data.targetDate,
      dailyTargetMinutes: data.dailyTargetMinutes,
      description: data.description,
      iconName: data.iconName || 'FolderKanban',
    })

    // 2. Cache in memory
    workspacesCache = [created, ...workspacesCache.filter((w) => w.id !== created.id)]
    documentsCache[created.id] = []
    tutorMessagesCache[created.id] = []
    topicsCache[created.id] = []
    knowledgeGapsCache[created.id] = []
    readinessCache[created.id] = []
    quizzesCache[created.id] = []
    flashcardDecksCache[created.id] = []

    studyPlansCache[created.id] = {
      workspaceId: created.id,
      dailyTargetMinutes: data.dailyTargetMinutes || 45,
      todayCompletedMinutes: 0,
      weeklyTargetMinutes: (data.dailyTargetMinutes || 45) * 5,
      weekCompletedMinutes: 0,
      tasks: [],
    }

    activitiesCache[created.id] = [
      {
        id: `act_${Date.now()}`,
        workspaceId: created.id,
        type: 'source_added',
        title: 'Workspace Created',
        description: `Created workspace "${data.name}" with goal: ${data.goal}`,
        timestamp: 'Just now',
      },
    ]

    return created
  },

  async searchWorkspaces(query: string): Promise<Workspace[]> {
    const q = query.trim().toLowerCase()
    const all = await this.getWorkspaces()
    if (!q) return all
    return all.filter(
      (w) =>
        w.name.toLowerCase().includes(q) ||
        w.goal.toLowerCase().includes(q) ||
        w.description.toLowerCase().includes(q)
    )
  },

  async deleteWorkspace(workspaceId: string): Promise<boolean> {
    const initialLen = workspacesCache.length
    workspacesCache = workspacesCache.filter((w) => w.id !== workspaceId)

    // Complete cleanup of all workspace-keyed states
    delete documentsCache[workspaceId]
    delete tutorMessagesCache[workspaceId]
    delete studyPlansCache[workspaceId]
    delete activitiesCache[workspaceId]
    delete topicsCache[workspaceId]
    delete knowledgeGapsCache[workspaceId]
    delete readinessCache[workspaceId]
    delete recommendationsCache[workspaceId]
    delete roadmapsCache[workspaceId]
    delete quizzesCache[workspaceId]
    delete flashcardDecksCache[workspaceId]

    // Authoritative Backend DELETE
    const backendDeleted = await tutorApiClient.deleteWorkspace(workspaceId).catch(() => false)
    return backendDeleted || workspacesCache.length < initialLen
  },

  // 2. DOCUMENT METHODS (Authoritative Source: FastAPI + Supabase PostgreSQL + Storage)
  async getDocuments(workspaceId: string): Promise<WorkspaceDocument[]> {
    if (!workspaceId) return []

    try {
      const backendDocs = await tutorApiClient.getWorkspaceDocuments(workspaceId)
      if (backendDocs) {
        documentsCache[workspaceId] = backendDocs
        return backendDocs
      }
    } catch (err) {
      console.error(`Failed to fetch documents for workspace '${workspaceId}':`, err)
    }

    return documentsCache[workspaceId] ? [...documentsCache[workspaceId]] : []
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
    let rawFile = file.rawFile
    if (!rawFile) {
      const blob = new Blob([`Learning Resource: ${file.title}\nFilename: ${file.filename}`], { type: 'text/plain' })
      rawFile = new File([blob], file.filename, { type: 'application/pdf' })
    }

    const createdDoc = await tutorApiClient.uploadDocument(workspaceId, rawFile, file.title)

    if (!documentsCache[workspaceId]) {
      documentsCache[workspaceId] = []
    }
    documentsCache[workspaceId] = [createdDoc, ...documentsCache[workspaceId].filter((d) => d.id !== createdDoc.id)]

    const ws = workspacesCache.find((w) => w.id === workspaceId)
    if (ws) {
      ws.documentCount += 1
    }
    return createdDoc
  },

  async removeDocument(workspaceId: string, documentId: string): Promise<boolean> {
    await tutorApiClient.deleteDocument(documentId).catch(() => null)

    if (documentsCache[workspaceId]) {
      const initialLen = documentsCache[workspaceId].length
      documentsCache[workspaceId] = documentsCache[workspaceId].filter((d) => d.id !== documentId)
      const ws = workspacesCache.find((w) => w.id === workspaceId)
      if (ws) {
        ws.documentCount = Math.max(0, ws.documentCount - 1)
      }
      return documentsCache[workspaceId].length < initialLen
    }
    return false
  },

  // 3. TOPICS & KNOWLEDGE METHODS
  async getTopics(workspaceId: string): Promise<Topic[]> {
    if (!workspaceId) return []
    return topicsCache[workspaceId] ? [...topicsCache[workspaceId]] : []
  },

  async getKnowledgeGaps(workspaceId: string): Promise<KnowledgeGap[]> {
    if (!workspaceId) return []
    return knowledgeGapsCache[workspaceId] ? [...knowledgeGapsCache[workspaceId]] : []
  },

  async getLearningReadiness(workspaceId: string): Promise<LearningReadiness[]> {
    if (!workspaceId) return []
    return readinessCache[workspaceId] ? [...readinessCache[workspaceId]] : []
  },

  async getAIRecommendation(workspaceId: string): Promise<AIRecommendation | null> {
    if (!workspaceId) return null
    return recommendationsCache[workspaceId] || null
  },

  async getRecommendation(workspaceId: string): Promise<AIRecommendation | null> {
    return this.getAIRecommendation(workspaceId)
  },

  async getRoadmap(workspaceId: string): Promise<Roadmap | null> {
    if (!workspaceId) return null
    return roadmapsCache[workspaceId] || null
  },

  // 4. QUIZ & FLASHCARDS METHODS
  async getQuizQuestions(workspaceId: string): Promise<QuizQuestion[]> {
    if (!workspaceId) return []
    return quizzesCache[workspaceId] ? [...quizzesCache[workspaceId]] : []
  },

  async submitQuizResult(
    workspaceId: string,
    answers: Record<string, string>,
    timeSpentSeconds: number = 60
  ): Promise<QuizResult> {
    return this.submitQuiz(workspaceId, answers, timeSpentSeconds)
  },

  async submitQuiz(
    workspaceId: string,
    answers: Record<string, string>,
    timeSpentSeconds: number = 60
  ): Promise<QuizResult> {
    const questions = await this.getQuizQuestions(workspaceId)
    let correctCount = 0
    const gaps: string[] = []

    questions.forEach((q) => {
      if (answers[q.id] === q.correctKey) {
        correctCount++
      } else {
        gaps.push(q.conceptTested)
      }
    })

    const accuracy = questions.length > 0 ? Math.round((correctCount / questions.length) * 100) : 100

    return {
      attemptId: `att_${Date.now()}`,
      score: correctCount * 10,
      totalQuestions: questions.length,
      accuracyPercentage: accuracy,
      averageResponseTimeSeconds: questions.length > 0 ? Math.round(timeSpentSeconds / questions.length) : 0,
      conceptPerformance: questions.map((q) => ({
        conceptName: q.conceptTested,
        accuracyPercentage: answers[q.id] === q.correctKey ? 100 : 0,
        status: (answers[q.id] === q.correctKey ? 'strong' : 'needs_review') as MasteryStatus,
      })),
      knowledgeGapsIdentified: gaps,
      recommendation: gaps.length > 0 ? `Review ${gaps.join(', ')} with AI Tutor.` : 'Excellent performance! Proceed to next level.',
    }
  },

  async getFlashcardDecks(workspaceId: string): Promise<FlashcardDeck[]> {
    if (!workspaceId) return []
    return flashcardDecksCache[workspaceId] ? [...flashcardDecksCache[workspaceId]] : []
  },

  async reviewFlashcard(
    workspaceId: string,
    deckId: string,
    cardId: string,
    rating: 'again' | 'hard' | 'good' | 'easy'
  ): Promise<void> {
    const decks = flashcardDecksCache[workspaceId] || []
    const deck = decks.find((d) => d.id === deckId)
    if (!deck) return

    const card = deck.cards.find((c) => c.id === cardId)
    if (!card) return

    card.lastReviewed = new Date().toISOString().split('T')[0]
    if (rating === 'easy' || rating === 'good') {
      card.intervalDays = (card.intervalDays || 1) * 2
    } else {
      card.intervalDays = 1
    }
  },

  // 5. STUDY PLAN & ACTIVITY METHODS
  async getStudyPlan(workspaceId: string): Promise<StudyPlan | null> {
    if (!workspaceId) return null
    return studyPlansCache[workspaceId] || null
  },

  async toggleTaskCompletion(workspaceId: string, taskId: string): Promise<StudyPlan | null> {
    const plan = studyPlansCache[workspaceId]
    if (!plan) return null

    const task = plan.tasks.find((t) => t.id === taskId)
    if (task) {
      task.completed = !task.completed
      if (task.completed) {
        plan.todayCompletedMinutes += task.estimatedMinutes
        plan.weekCompletedMinutes += task.estimatedMinutes
      } else {
        plan.todayCompletedMinutes = Math.max(0, plan.todayCompletedMinutes - task.estimatedMinutes)
        plan.weekCompletedMinutes = Math.max(0, plan.weekCompletedMinutes - task.estimatedMinutes)
      }
    }
    return { ...plan }
  },

  async toggleStudyTask(workspaceId: string, taskId: string): Promise<StudyPlan | null> {
    return this.toggleTaskCompletion(workspaceId, taskId)
  },

  async getActivities(workspaceId?: string): Promise<LearningActivity[]> {
    if (workspaceId && activitiesCache[workspaceId]) {
      return [...activitiesCache[workspaceId]]
    }
    const all = Object.values(activitiesCache).flat()
    return all.length > 0 ? all : []
  },

  // 6. TUTOR & RAG CHAT (Authoritative Source: FastAPI /api/v1/workspaces/{id}/tutor)
  async getTutorMessages(workspaceId: string): Promise<TutorMessage[]> {
    if (!workspaceId) return []
    return tutorMessagesCache[workspaceId] ? [...tutorMessagesCache[workspaceId]] : []
  },

  async sendTutorMessage(
    workspaceId: string,
    userText: string,
    conversationId?: string,
    currentDocumentId?: string
  ): Promise<TutorMessage> {
    const userMsg: TutorMessage = {
      id: `tm_u_${Date.now()}`,
      workspaceId,
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    if (!tutorMessagesCache[workspaceId]) {
      tutorMessagesCache[workspaceId] = []
    }
    tutorMessagesCache[workspaceId].push(userMsg)

    try {
      const assistantMsg = await tutorApiClient.sendTutorMessage(
        workspaceId,
        userText,
        conversationId,
        currentDocumentId
      )
      tutorMessagesCache[workspaceId].push(assistantMsg)
      return assistantMsg
    } catch (err: any) {
      console.error('RAG request failed on FastAPI backend:', err)
      const errorMsg: TutorMessage = {
        id: `tm_err_${Date.now()}`,
        workspaceId,
        role: 'assistant',
        content: `⚠️ **[AI Tutor Service Notice]**: ${err.message || 'Unable to connect to RAG generation engine'}.\n\nPlease check that your learning sources are uploaded and that your language model configuration is active on FastAPI.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: [],
        suggestedFollowUps: ['Try again', 'Manage workspace sources'],
      }
      tutorMessagesCache[workspaceId].push(errorMsg)
      return errorMsg
    }
  },

  async getNotifications(): Promise<NotificationItem[]> {
    return [...demoNotifications]
  },
}
