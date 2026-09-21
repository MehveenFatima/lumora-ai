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
  RoadmapStage,
  RoadmapNode,
  RoadmapNodeStatus,
  RoadmapAdaptation,
  QuizQuestion,
  QuizResult,
  FlashcardDeck,
  StudyPlan,
  LearningActivity,
  ActivityType,
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

function formatActivityTimestamp(rawTs: any): string {
  if (!rawTs) return 'Just now'
  if (typeof rawTs === 'string') {
    const trimmed = rawTs.trim()
    if (/^\d{1,2}:\d{2}\s*(AM|PM)?$/i.test(trimmed) || trimmed.toLowerCase() === 'just now') {
      return trimmed
    }
    const d = new Date(trimmed)
    if (!isNaN(d.getTime())) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return trimmed
  }
  if (rawTs instanceof Date && !isNaN(rawTs.getTime())) {
    return rawTs.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return 'Just now'
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

  // 3. TOPICS & KNOWLEDGE METHODS (Authoritative Source: FastAPI TopicMasteryEngine & LearnerProfileService)
  async getTopics(workspaceId: string): Promise<Topic[]> {
    if (!workspaceId) return []

    try {
      const res = await tutorApiClient.getTopicMasteryList(workspaceId)
      if (res && res.topics && res.topics.length > 0) {
        const mappedTopics: Topic[] = res.topics.map((t: any) => {
          const concepts = (t.concepts || []).map((c: any) => ({
            id: `c_${c.concept.toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
            name: c.concept,
            mastery: c.mastery_percentage !== undefined ? c.mastery_percentage : Math.round((c.p_mastery || 0.3) * 100),
            status: (c.mastery_status as MasteryStatus) || 'developing',
            whyWeak: c.mastery_status === 'critical_gap' || c.mastery_status === 'needs_review'
              ? `Low assessment accuracy (${Math.round((c.recent_accuracy || 0) * 100)}%) with high knowledge gap priority.`
              : undefined,
            lastAssessed: c.last_practiced_at ? new Date(c.last_practiced_at).toLocaleDateString() : 'Not yet assessed',
          }))

          const trend: 'up' | 'down' | 'steady' =
            t.trend === 'improving' ? 'up' : t.trend === 'declining' ? 'down' : 'steady'

          const weakCount = concepts.filter(
            (c: any) => c.status === 'critical_gap' || c.status === 'needs_review'
          ).length

          return {
            id: `t_${t.topic.toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
            workspaceId: t.workspace_id || workspaceId,
            name: t.topic,
            description: `Curriculum topic containing ${t.concept_count || 1} concept${(t.concept_count || 1) > 1 ? 's' : ''} (${t.assessed_concept_count || 0} assessed).`,
            mastery: t.mastery_percentage !== undefined ? t.mastery_percentage : Math.round((t.mastery_probability || 0.3) * 100),
            trend: trend,
            status: (t.mastery_status as MasteryStatus) || 'developing',
            conceptsCount: t.concept_count || Math.max(concepts.length, 1),
            weakConceptsCount: weakCount,
            concepts: concepts,
            lastReviewDate: t.last_assessed_at ? new Date(t.last_assessed_at).toLocaleDateString() : 'Recent',
            nextReviewDate: 'In 3 days',
            estimatedStudyMinutes: Math.max(15, (t.concept_count || 1) * 10),
          }
        })
        topicsCache[workspaceId] = mappedTopics
        return mappedTopics
      }
    } catch (err) {
      console.warn(`Failed to fetch live topics for workspace '${workspaceId}':`, err)
    }

    // Presentation demo fallback strictly for dsa
    if (workspaceId === 'dsa' && (!topicsCache['dsa'] || topicsCache['dsa'].length === 0)) {
      return [...dsaTopics]
    }

    return topicsCache[workspaceId] ? [...topicsCache[workspaceId]] : []
  },

  async getKnowledgeGaps(workspaceId: string): Promise<KnowledgeGap[]> {
    if (!workspaceId) return []

    try {
      const profile = await tutorApiClient.getLearnerProfile(workspaceId)
      if (profile && profile.top_knowledge_gaps && profile.top_knowledge_gaps.length > 0) {
        const mappedGaps: KnowledgeGap[] = profile.top_knowledge_gaps.map((g: any, idx: number) => {
          const priority = g.gap_priority !== undefined ? g.gap_priority : 0.5
          const severity: 'critical' | 'moderate' | 'mild' =
            priority >= 0.7 ? 'critical' : priority >= 0.4 ? 'moderate' : 'mild'
          const pMastery = g.p_mastery !== undefined ? g.p_mastery : 0.3

          return {
            id: `gap_${workspaceId}_${idx}`,
            workspaceId: workspaceId,
            topicId: `t_${(g.topic || 'general').toLowerCase().replace(/[^a-z0-9]/g, '_')}`,
            topicName: g.topic || 'General',
            conceptName: g.concept || 'Core Concept',
            mastery: Math.round(pMastery * 100),
            reason: g.rationale || `Identified knowledge gap with priority ${Math.round(priority * 100)}%. Focus practice to reinforce understanding.`,
            severity: severity,
            recommendedAction: (g.recommended_action === 'targeted_practice' ? 'quiz' : 'tutor') as any,
          }
        })
        knowledgeGapsCache[workspaceId] = mappedGaps
        return mappedGaps
      } else if (profile && profile.status === 'not_assessed') {
        knowledgeGapsCache[workspaceId] = []
        return []
      }
    } catch (err) {
      console.warn(`Failed to fetch learner profile gaps for '${workspaceId}':`, err)
    }

    // Presentation demo fallback strictly for dsa
    if (workspaceId === 'dsa' && (!knowledgeGapsCache['dsa'] || knowledgeGapsCache['dsa'].length === 0)) {
      return [...dsaKnowledgeGaps]
    }

    return knowledgeGapsCache[workspaceId] ? [...knowledgeGapsCache[workspaceId]] : []
  },

  async getLearningReadiness(workspaceId: string): Promise<LearningReadiness[]> {
    if (!workspaceId) return []
    return readinessCache[workspaceId] ? [...readinessCache[workspaceId]] : []
  },

  async getAIRecommendation(workspaceId: string): Promise<AIRecommendation | null> {
    if (!workspaceId) return null

    try {
      const profile = await tutorApiClient.getLearnerProfile(workspaceId)
      if (profile && profile.recommendations && profile.recommendations.length > 0) {
        const r = profile.recommendations[0]
        const rec: AIRecommendation = {
          id: `rec_${workspaceId}_${Date.now()}`,
          workspaceId: workspaceId,
          title: `Reinforce ${r.concept}`,
          targetConcept: r.concept,
          topicName: r.topic,
          priority: r.gap_priority >= 0.7 ? 'high' : r.gap_priority >= 0.4 ? 'medium' : 'low',
          estimatedMinutes: 15,
          summary: `Targeted review recommended for ${r.concept} in ${r.topic}.`,
          rationale: `BKT estimation shows ${Math.round(r.mastery_probability * 100)}% mastery with ${Math.round(r.gap_priority * 100)}% gap priority. Recommended action: ${(r.recommended_action || '').replace(/_/g, ' ')}.`,
          dataPoints: [
            `Current Mastery Probability: ${Math.round(r.mastery_probability * 100)}%`,
            `Gap Priority Score: ${Math.round(r.gap_priority * 100)}%`,
            `Evidence Confidence: ${r.confidence}`,
            `Mastery Trend: ${(r.trend || '').replace(/_/g, ' ')}`,
          ],
          suggestedAction: r.recommended_action === 'targeted_practice' ? 'quiz' : 'tutor',
        }
        recommendationsCache[workspaceId] = rec
        return rec
      } else if (profile && profile.status === 'not_assessed') {
        return null
      }
    } catch (err) {
      console.warn(`Failed to fetch recommendation for '${workspaceId}':`, err)
    }

    if (workspaceId === 'dsa' && !recommendationsCache['dsa']) {
      return dsaRecommendation ? { ...dsaRecommendation } : null
    }

    return recommendationsCache[workspaceId] || null
  },

  async getRecommendation(workspaceId: string): Promise<AIRecommendation | null> {
    return this.getAIRecommendation(workspaceId)
  },

  async getRoadmap(workspaceId: string): Promise<Roadmap | null> {
    if (!workspaceId) return null

    try {
      const [topicsRes, profileRes] = await Promise.all([
        tutorApiClient.getTopicMasteryList(workspaceId).catch(() => null),
        tutorApiClient.getLearnerProfile(workspaceId).catch(() => null),
      ])

      if (topicsRes && topicsRes.topics && topicsRes.topics.length > 0) {
        const stages: RoadmapStage[] = topicsRes.topics.map((t: any, idx: number) => {
          const mPct =
            t.mastery_percentage !== undefined
              ? t.mastery_percentage
              : Math.round((t.mastery_probability || 0.3) * 100)

          const stageLevel: 'foundations' | 'core' | 'advanced' | 'mastery' =
            idx === 0 ? 'foundations' : idx === 1 ? 'core' : idx === 2 ? 'advanced' : 'mastery'

          const rawConcepts = t.concepts || []
          const nodes: RoadmapNode[] = rawConcepts.map((c: any, cIdx: number) => {
            const cMastery =
              c.mastery_percentage !== undefined
                ? c.mastery_percentage
                : Math.round((c.p_mastery || 0.3) * 100)
            const nodeStatus: RoadmapNodeStatus =
              cMastery >= 75 ? 'completed' : cMastery >= 40 ? 'in_progress' : 'upcoming'

            return {
              id: `node_${workspaceId}_${idx}_${cIdx}`,
              title: c.concept || c.name || 'Concept Node',
              description: `Mastery: ${cMastery}% (${(c.mastery_status || 'developing').replace(/_/g, ' ')})`,
              stage: stageLevel,
              status: nodeStatus,
              mastery: cMastery,
              estimatedHours: Math.max(2, Math.round((100 - cMastery) / 15)),
              prerequisiteIds: cIdx > 0 ? [`node_${workspaceId}_${idx}_${cIdx - 1}`] : [],
            }
          })

          if (nodes.length === 0) {
            const nodeStatus: RoadmapNodeStatus =
              mPct >= 75 ? 'completed' : mPct >= 40 ? 'in_progress' : 'upcoming'
            nodes.push({
              id: `node_${workspaceId}_${idx}_0`,
              title: t.topic,
              description: `Mastery: ${mPct}% (${(t.mastery_status || 'developing').replace(/_/g, ' ')})`,
              stage: stageLevel,
              status: nodeStatus,
              mastery: mPct,
              estimatedHours: Math.max(3, (t.concept_count || 1) * 2),
              prerequisiteIds: [],
            })
          }

          return {
            id: `stg_${workspaceId}_${idx}`,
            name: t.topic,
            description: `${nodes.length} curriculum node${nodes.length > 1 ? 's' : ''} • ${mPct}% mastery`,
            nodes,
          }
        })

        let adaptation: RoadmapAdaptation | undefined = undefined
        if (profileRes?.recommendations && profileRes.recommendations.length > 0) {
          const rec = profileRes.recommendations[0]
          adaptation = {
            hasAdaptation: true,
            title: `Curriculum Path Adapted: Focus on ${rec.concept}`,
            triggerReason: `Diagnostic assessment identified ${rec.concept} with ${Math.round((rec.gap_priority || 0.5) * 100)}% gap priority in ${rec.topic}.`,
            beforePath: stages.slice(0, 3).map((s) => s.name),
            nowPath: [rec.concept, ...stages.slice(0, 2).map((s) => s.name)],
            detailedExplanation: `Targeted review recommended for ${rec.concept} to reinforce prerequisites before progressing to advanced stages.`,
            updatedAt: 'Recently',
          }
        }

        const overallProgress =
          profileRes?.overall_mastery !== undefined
            ? profileRes.overall_mastery
            : topicsRes.overall_mastery !== undefined
            ? Math.round(topicsRes.overall_mastery)
            : Math.round(
                stages.reduce((acc, s) => acc + (s.nodes[0]?.mastery || 0), 0) / Math.max(stages.length, 1)
              )

        const dynamicRoadmap: Roadmap = {
          workspaceId,
          overallProgress,
          stages,
          adaptation,
        }

        roadmapsCache[workspaceId] = dynamicRoadmap
        return dynamicRoadmap
      }
    } catch (e) {
      console.warn('Failed to fetch dynamic roadmap:', e)
    }

    if (workspaceId === 'dsa' && !roadmapsCache['dsa']) {
      return dsaRoadmap ? { ...dsaRoadmap } : null
    }

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

    try {
      const res = await tutorApiClient.getFlashcards(workspaceId)
      if (res && res.flashcards && res.flashcards.length > 0) {
        const cards = res.flashcards.map((c: any) => ({
          id: c.id,
          deckId: `deck_${workspaceId}`,
          question: c.front,
          answer: c.back,
          sourceCitation: c.source_document ? `${c.source_document} (p. ${c.source_page || 1})` : undefined,
          difficulty: 'medium' as const,
          intervalDays: c.interval_days || 1,
          repetitions: 1,
          dueDate: 'Today',
        }))

        const deck: FlashcardDeck = {
          id: `deck_${workspaceId}`,
          workspaceId,
          title: 'Core Concepts & Definitions',
          topicName: 'Curriculum Review',
          totalCards: cards.length,
          dueTodayCount: cards.length,
          masteryPercentage: 65,
          cards: cards,
        }
        flashcardDecksCache[workspaceId] = [deck]
        return [deck]
      }
    } catch (err) {
      console.warn(`Failed to fetch backend flashcards for '${workspaceId}':`, err)
    }

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

    try {
      const res = await tutorApiClient.getStudyPlan(workspaceId)
      if (res && res.tasks && res.tasks.length > 0) {
        const mappedPlan: StudyPlan = {
          workspaceId: res.workspace_id || workspaceId,
          dailyTargetMinutes: res.daily_target_minutes || 45,
          todayCompletedMinutes: res.today_completed_minutes || 0,
          weeklyTargetMinutes: res.weekly_target_minutes || 225,
          weekCompletedMinutes: res.week_completed_minutes || 0,
          tasks: res.tasks.map((t: any) => ({
            id: t.id,
            workspaceId: res.workspace_id || workspaceId,
            title: t.title,
            topicName: t.tag || 'Core Topic',
            estimatedMinutes: t.estimatedMinutes || 20,
            priority: (t.priority || 'medium') as 'high' | 'medium' | 'low',
            type: (t.tag?.toLowerCase().includes('quiz')
              ? 'quiz'
              : t.tag?.toLowerCase().includes('flashcard')
              ? 'flashcard'
              : 'tutor') as any,
            completed: Boolean(t.completed),
            scheduledFor: (t.scheduledFor || 'today') as 'today' | 'this_week' | 'upcoming',
          })),
        }
        studyPlansCache[workspaceId] = mappedPlan
        return mappedPlan
      }
    } catch (err) {
      console.warn(`Failed to fetch live study plan for '${workspaceId}':`, err)
    }

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
    try {
      const res = await tutorApiClient.toggleStudyTask(workspaceId, taskId)
      if (res && res.tasks) {
        return this.getStudyPlan(workspaceId)
      }
    } catch (err) {
      console.warn(`Failed to toggle backend study task for '${workspaceId}':`, err)
    }
    return this.toggleTaskCompletion(workspaceId, taskId)
  },

  async getActivities(workspaceId?: string): Promise<LearningActivity[]> {
    try {
      const res = await tutorApiClient.getActivities(workspaceId)
      if (res && res.activities && res.activities.length > 0) {
        const mapped: LearningActivity[] = res.activities.map((a: any) => ({
          id: a.id,
          workspaceId: a.workspace_id,
          type: (a.event_type || 'tutor_session') as ActivityType,
          title: a.title,
          description: a.description,
          timestamp: formatActivityTimestamp(a.timestamp || a.created_at),
        }))
        if (workspaceId) {
          activitiesCache[workspaceId] = mapped
        }
        return mapped
      }
    } catch (err) {
      console.warn('Failed to fetch live activities:', err)
    }

    if (workspaceId && activitiesCache[workspaceId]) {
      return [...activitiesCache[workspaceId]]
    }
    const all = Object.values(activitiesCache).flat()
    return all.length > 0 ? all : []
  },

  // 6. TUTOR & RAG CHAT (Authoritative Source: FastAPI /api/v1/workspaces/{id}/tutor)
  async getTutorMessages(workspaceId: string): Promise<TutorMessage[]> {
    if (!workspaceId) return []

    if (tutorMessagesCache[workspaceId] && tutorMessagesCache[workspaceId].length > 0) {
      return [...tutorMessagesCache[workspaceId]]
    }

    try {
      const history = await tutorApiClient.getTutorHistory(workspaceId)
      if (history && history.messages.length > 0) {
        tutorMessagesCache[workspaceId] = history.messages
        return [...history.messages]
      }
    } catch (err) {
      console.warn(`Failed to fetch persisted tutor history for workspace '${workspaceId}':`, err)
    }

    return tutorMessagesCache[workspaceId] ? [...tutorMessagesCache[workspaceId]] : []
  },

  async getTutorHistory(
    workspaceId: string,
    conversationId?: string
  ): Promise<{ conversationId: string; messages: TutorMessage[] }> {
    if (!workspaceId) return { conversationId: '', messages: [] }
    const res = await tutorApiClient.getTutorHistory(workspaceId, conversationId)
    if (res && res.messages.length > 0) {
      tutorMessagesCache[workspaceId] = res.messages
    }
    return res
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
