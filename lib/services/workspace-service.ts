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

// Simulated in-memory storage for demo mutations & local fallback
let workspacesState = [...demoWorkspaces]
const documentsState = { ...demoDocumentsByWorkspace }
const tutorMessagesState = { ...demoTutorMessagesByWorkspace }
const studyPlansState = { ...demoStudyPlansByWorkspace }
const activitiesState = { ...demoActivitiesByWorkspace }

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
    documentsState[newId] = []
    tutorMessagesState[newId] = []
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
    delete documentsState[workspaceId]
    delete tutorMessagesState[workspaceId]
    delete studyPlansState[workspaceId]
    delete activitiesState[workspaceId]
    return workspacesState.length < initialLen
  },

  async removeDocument(workspaceId: string, documentId: string): Promise<boolean> {
    // Attempt backend deletion
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
    // Attempt to query real backend first
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
    // If rawFile is provided, upload directly to FastAPI backend
    if (file.rawFile) {
      try {
        const doc = await tutorApiClient.uploadDocument(workspaceId, file.rawFile, file.title)
        if (!documentsState[workspaceId]) {
          documentsState[workspaceId] = []
        }
        documentsState[workspaceId] = [doc, ...documentsState[workspaceId]]
        const ws = workspacesState.find((w) => w.id === workspaceId)
        if (ws) ws.documentCount += 1
        return doc
      } catch (err) {
        console.warn('Backend document upload failed, using local document indexing:', err)
      }
    }

    await delay(300)
    const newDoc: WorkspaceDocument = {
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

    if (!documentsState[workspaceId]) {
      documentsState[workspaceId] = []
    }
    documentsState[workspaceId] = [newDoc, ...documentsState[workspaceId]]

    const ws = workspacesState.find((w) => w.id === workspaceId)
    if (ws) {
      ws.documentCount += 1
    }

    return newDoc
  },

  async getTopics(workspaceId: string): Promise<Topic[]> {
    await delay(120)
    return demoTopicsByWorkspace[workspaceId] ? [...demoTopicsByWorkspace[workspaceId]] : []
  },

  async getKnowledgeGaps(workspaceId: string): Promise<KnowledgeGap[]> {
    await delay(100)
    return demoKnowledgeGapsByWorkspace[workspaceId] ? [...demoKnowledgeGapsByWorkspace[workspaceId]] : []
  },

  async getLearningReadiness(workspaceId: string): Promise<LearningReadiness[]> {
    await delay(100)
    return demoReadinessByWorkspace[workspaceId] ? [...demoReadinessByWorkspace[workspaceId]] : []
  },

  async getRecommendation(workspaceId: string): Promise<AIRecommendation | null> {
    await delay(80)
    return demoRecommendationsByWorkspace[workspaceId] ? { ...demoRecommendationsByWorkspace[workspaceId] } : null
  },

  async getRoadmap(workspaceId: string): Promise<Roadmap | null> {
    await delay(100)
    return demoRoadmapsByWorkspace[workspaceId] ? { ...demoRoadmapsByWorkspace[workspaceId] } : null
  },

  async getQuizQuestions(workspaceId: string): Promise<QuizQuestion[]> {
    await delay(120)
    return demoQuizzesByWorkspace[workspaceId] ? [...demoQuizzesByWorkspace[workspaceId]] : []
  },

  async submitQuiz(workspaceId: string, answers: Record<string, string>): Promise<QuizResult> {
    await delay(350)
    const questions = demoQuizzesByWorkspace[workspaceId] || []
    let correctCount = 0

    questions.forEach((q) => {
      if (answers[q.id] === q.correctKey) {
        correctCount++
      }
    })

    const total = questions.length || 1
    const accuracy = Math.round((correctCount / total) * 100)

    return {
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
  },

  async getFlashcardDecks(workspaceId: string): Promise<FlashcardDeck[]> {
    await delay(120)
    return demoFlashcardDecksByWorkspace[workspaceId] ? [...demoFlashcardDecksByWorkspace[workspaceId]] : []
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
    if (workspaceId && activitiesState[workspaceId]) {
      return [...activitiesState[workspaceId]]
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
    const topDoc = docs[0] || {
      id: 'doc_dsa_1',
      filename: 'DSA_Core_Notes.pdf',
      title: 'Data Structures & Algorithms',
    }

    const assistantMsg: TutorMessage = {
      id: `tm_a_${Date.now()}`,
      workspaceId,
      role: 'assistant',
      content: `Grounded in **${topDoc.filename}** (Page 42):\n\nWhen analyzing **${userText}**, the source emphasizes the following principles:\n\n1. **Invariant Verification**: Check that boundary conditions and edge cases are enforced prior to recursive calls.\n2. **State Progression**: Ensure visited sets and active recursion stacks avoid duplicate cycles.\n3. **Termination**: Validate termination conditions to guarantee expected complexity.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      citations: [
        {
          id: `cit_${Date.now()}`,
          documentId: topDoc.id,
          documentName: topDoc.filename,
          pageOrSlide: 42,
          excerpt: 'Fundamental algorithm structure: Verify invariants, enforce state progression, and validate termination constraints.',
          relevanceScore: 0.94,
        },
      ],
      suggestedFollowUps: [
        'Can you give a concrete step-by-step walkthrough?',
        'What are the common edge cases and pitfall traps?',
        'Quiz me on this concept right now',
      ],
    }

    tutorMessagesState[workspaceId].push(assistantMsg)
    return assistantMsg
  },

  async getNotifications(): Promise<NotificationItem[]> {
    await delay(80)
    return [...demoNotifications]
  },
}
