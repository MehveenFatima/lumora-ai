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

// Simulated in-memory storage for demo mutations
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

  async getDocuments(workspaceId: string): Promise<WorkspaceDocument[]> {
    await delay(120)
    return documentsState[workspaceId] ? [...documentsState[workspaceId]] : []
  },

  async addDocument(workspaceId: string, file: { title: string; filename: string; type: 'pdf' | 'pptx' | 'docx'; sizeBytes: number; pagesCount: number }): Promise<WorkspaceDocument> {
    await delay(400)
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

    // Update document count in workspace
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
    // Return aggregated activities across all workspaces for global dashboard
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
    await delay(600)
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

    // Generate grounded contextual response
    const docs = documentsState[workspaceId] || []
    const topDoc = docs[0] || { filename: 'Workspace_Notes.pdf', id: 'doc_default' }

    const assistantMsg: TutorMessage = {
      id: `tm_a_${Date.now()}`,
      workspaceId,
      role: 'assistant',
      content: `Grounded in **${topDoc.filename}**:

Based on your workspace sources regarding **${userText.slice(0, 40)}...**, here is the grounded explanation:

When analyzing this concept, the underlying invariant requires continuous verification of state transitions. In our indexed notes, this is formulated as a step-by-step procedure:

1. **Initialization**: Establish baseline boundary conditions and allocate necessary tracking data structures.
2. **Execution & Exploration**: Process each component systematically while avoiding redundant traversals.
3. **Validation**: Check against edge cases and verify that time/space constraints are satisfied.`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      citations: [
        {
          id: `cit_${Date.now()}`,
          documentId: topDoc.id,
          documentName: topDoc.filename,
          pageOrSlide: 24,
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
