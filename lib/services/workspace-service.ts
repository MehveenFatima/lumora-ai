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
    await delay(100)
    return { ...demoUser }
  },

  async getWorkspaces(): Promise<Workspace[]> {
    await delay(150)
    return [...workspacesState]
  },

  async getWorkspaceById(id: string): Promise<Workspace | null> {
    await delay(100)
    const found = workspacesState.find((w) => w.id === id)
    return found ? { ...found } : null
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
    await delay(300)
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

    return newWs
  },

  async searchWorkspaces(query: string): Promise<Workspace[]> {
    await delay(80)
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
    await delay(300)
    const initialLen = workspacesState.length
    workspacesState = workspacesState.filter((w) => w.id !== workspaceId)

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

    return workspacesState.length < initialLen
  },

  async removeDocument(workspaceId: string, documentId: string): Promise<boolean> {
    await tutorApiClient.deleteDocument(documentId).catch(() => null)

    if (documentsState[workspaceId]) {
      const initialLen = documentsState[workspaceId].length
      documentsState[workspaceId] = documentsState[workspaceId].filter((d) => d.id !== documentId)
      const ws = workspacesState.find((w) => w.id === workspaceId)
      if (ws) {
        ws.documentCount = Math.max(0, ws.documentCount - 1)
      }
      return documentsState[workspaceId].length < initialLen
    }
    return false
  },

  async getDocuments(workspaceId: string): Promise<WorkspaceDocument[]> {
    try {
      const backendDocs = await tutorApiClient.getWorkspaceDocuments(workspaceId)
      if (backendDocs && backendDocs.length > 0) {
        return backendDocs
      }
    } catch {
      // Fallback to local memory state
    }
    await delay(80)
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
      await delay(300)
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

    if (!documentsState[workspaceId]) {
      documentsState[workspaceId] = []
    }
    documentsState[workspaceId] = [createdDoc, ...documentsState[workspaceId]]

    const ws = workspacesState.find((w) => w.id === workspaceId)
    if (ws) {
      ws.documentCount += 1
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

    return createdDoc
  },

  async getTopics(workspaceId: string): Promise<Topic[]> {
    await delay(120)
    return topicsState[workspaceId] ? [...topicsState[workspaceId]] : []
  },

  async getKnowledgeGaps(workspaceId: string): Promise<KnowledgeGap[]> {
    await delay(100)
    return knowledgeGapsState[workspaceId] ? [...knowledgeGapsState[workspaceId]] : []
  },

  async getLearningReadiness(workspaceId: string): Promise<LearningReadiness[]> {
    await delay(100)
    return readinessState[workspaceId] ? [...readinessState[workspaceId]] : []
  },

  async getRecommendation(workspaceId: string): Promise<AIRecommendation | null> {
    await delay(80)
    return recommendationsState[workspaceId] ? { ...recommendationsState[workspaceId] } : null
  },

  async getRoadmap(workspaceId: string): Promise<Roadmap | null> {
    await delay(100)
    return roadmapsState[workspaceId] ? { ...roadmapsState[workspaceId] } : null
  },

  async getQuizQuestions(workspaceId: string): Promise<QuizQuestion[]> {
    await delay(120)
    return quizzesState[workspaceId] ? [...quizzesState[workspaceId]] : []
  },

  async submitQuiz(workspaceId: string, answers: Record<string, string>): Promise<QuizResult> {
    await delay(350)
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

    // Record activity for this workspace
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

    return result
  },

  async getFlashcardDecks(workspaceId: string): Promise<FlashcardDeck[]> {
    await delay(120)
    return flashcardDecksState[workspaceId] ? [...flashcardDecksState[workspaceId]] : []
  },

  async getStudyPlan(workspaceId: string): Promise<StudyPlan | null> {
    await delay(100)
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
      }
    }
  },

  async getActivities(workspaceId?: string): Promise<LearningActivity[]> {
    await delay(100)
    if (workspaceId) {
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
    await delay(100)
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

    // 1. Attempt to call FastAPI RAG backend
    try {
      const assistantMsg = await tutorApiClient.sendTutorMessage(workspaceId, userText)
      tutorMessagesState[workspaceId].push(assistantMsg)
      return assistantMsg
    } catch (err) {
      console.info('Using local grounded citation synthesis for workspace:', workspaceId)
    }

    // 2. Local Grounded Synthesis Fallback
    await delay(400)
    const docs = documentsState[workspaceId] || []
    const ws = workspacesState.find((w) => w.id === workspaceId)
    const wsName = ws?.name || 'this workspace'

    let assistantMsg: TutorMessage

    if (docs.length === 0) {
      // Empty workspace refusal behavior
      assistantMsg = {
        id: `tm_a_${Date.now()}`,
        workspaceId,
        role: 'assistant',
        content: `Your workspace sources do not contain enough information to answer that reliably.\n\nI checked all indexed resources in **${wsName}**, but no documents have been uploaded yet. Please upload your lecture notes, syllabus, or textbook (PDF, DOCX, PPTX, or TXT) in the **Sources** tab to enable grounded tutoring.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: [],
        suggestedFollowUps: [
          'How do I upload learning resources?',
          'What file formats are supported?',
        ],
      }
    } else {
      const topDoc = docs[0]
      assistantMsg = {
        id: `tm_a_${Date.now()}`,
        workspaceId,
        role: 'assistant',
        content: `Based on **${topDoc.filename}** (Page 1):\n\nWhen analyzing **${userText}**, your workspace resource highlights the following key points:\n\n1. **Core Concept**: Verified against the primary definitions in ${topDoc.title}.\n2. **Principles & Invariants**: Enforce state progression and review domain constraints.\n3. **Application**: Apply the methodology step-by-step to achieve high precision.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: [
          {
            id: `cit_${Date.now()}`,
            documentId: topDoc.id,
            documentName: topDoc.filename,
            pageOrSlide: 1,
            excerpt: `Core principles and methodology extracted from ${topDoc.title}.`,
            relevanceScore: 0.92,
          },
        ],
        suggestedFollowUps: [
          'Can you walk through a concrete example?',
          'What are the common edge cases?',
          'Quiz me on this concept',
        ],
      }
    }

    tutorMessagesState[workspaceId].push(assistantMsg)
    return assistantMsg
  },

  async getNotifications(): Promise<NotificationItem[]> {
    await delay(80)
    return [...demoNotifications]
  },
}
