export type WorkspaceLevel = 'beginner' | 'intermediate' | 'advanced'

export type MasteryStatus = 'critical_gap' | 'needs_review' | 'developing' | 'strong'

export interface User {
  id: string
  name: string
  email: string
  avatarUrl?: string
  streakDays: number
  totalStudyMinutes: number
  joinedAt: string
}

export interface Workspace {
  id: string
  name: string
  description: string
  goal: string
  level: WorkspaceLevel
  targetDate: string
  dailyTargetMinutes: number
  overallMastery: number
  masteryDelta: number
  status: 'active' | 'on_track' | 'needs_review'
  iconName: string
  documentCount: number
  topicsCount: number
  flashcardsDueCount: number
  lastActive: string
  createdAt: string
}

export type DocumentType = 'pdf' | 'pptx' | 'docx' | 'notes'
export type DocumentStatus = 'uploading' | 'processing' | 'extracting' | 'indexing' | 'ready' | 'failed'

export interface DocumentChunk {
  id: string
  pageOrSlideNumber?: number
  content: string
  relevanceScore?: number
}

export interface WorkspaceDocument {
  id: string
  workspaceId: string
  title: string
  filename: string
  type: DocumentType
  sizeBytes: number
  pagesCount: number
  status: DocumentStatus
  chunksCount: number
  uploadedAt: string
  summary?: string
  errorMessage?: string
  chunks?: DocumentChunk[]
}

export interface Concept {
  id: string
  name: string
  mastery: number
  status: MasteryStatus
  whyWeak?: string
  lastAssessed?: string
}

export interface Topic {
  id: string
  workspaceId: string
  name: string
  description: string
  mastery: number
  trend: 'up' | 'down' | 'steady'
  status: MasteryStatus
  conceptsCount: number
  weakConceptsCount: number
  concepts: Concept[]
  lastReviewDate: string
  nextReviewDate: string
  estimatedStudyMinutes: number
}

export interface KnowledgeGap {
  id: string
  workspaceId: string
  topicId: string
  topicName: string
  conceptName: string
  mastery: number
  reason: string
  severity: 'critical' | 'moderate' | 'mild'
  recommendedAction: 'quiz' | 'tutor' | 'flashcard' | 'source_review'
}

export interface LearningReadiness {
  id: string
  conceptName: string
  topicName: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  status: 'ready' | 'not_ready' | 'in_progress'
  reason: string
  prerequisites: Array<{
    name: string
    requiredMastery: number
    currentMastery: number
    met: boolean
  }>
}

export interface AIRecommendation {
  id: string
  workspaceId: string
  title: string
  targetConcept: string
  topicName: string
  priority: 'high' | 'medium' | 'low'
  estimatedMinutes: number
  summary: string
  rationale: string
  dataPoints: string[]
  suggestedAction: 'quiz' | 'tutor' | 'flashcard' | 'study'
}

export type RoadmapNodeStatus = 'completed' | 'in_progress' | 'upcoming' | 'adapted'

export interface RoadmapNode {
  id: string
  title: string
  description: string
  stage: 'foundations' | 'core' | 'advanced' | 'mastery'
  status: RoadmapNodeStatus
  mastery: number
  estimatedHours: number
  prerequisiteIds: string[]
  isAdaptiveAddition?: boolean
  adaptedReason?: string
}

export interface RoadmapStage {
  id: string
  name: string
  description: string
  nodes: RoadmapNode[]
}

export interface RoadmapAdaptation {
  hasAdaptation: boolean
  title: string
  triggerReason: string
  beforePath: string[]
  nowPath: string[]
  detailedExplanation: string
  updatedAt: string
}

export interface Roadmap {
  workspaceId: string
  overallProgress: number
  stages: RoadmapStage[]
  adaptation?: RoadmapAdaptation
}

export type QuizDifficulty = 'easy' | 'medium' | 'hard'

export interface QuizOption {
  key: string
  text: string
}

export interface QuizQuestion {
  id: string
  topicId: string
  topicName: string
  conceptTested: string
  difficulty: QuizDifficulty
  adaptiveHint?: string
  question: string
  codeSnippet?: string
  options: QuizOption[]
  correctKey: string
  explanation: string
  sourceCitation?: {
    documentName: string
    pageOrSlide: number
  }
}

export interface QuizResult {
  attemptId: string
  score: number
  totalQuestions: number
  accuracyPercentage: number
  averageResponseTimeSeconds: number
  conceptPerformance: Array<{
    conceptName: string
    accuracyPercentage: number
    status: MasteryStatus
  }>
  knowledgeGapsIdentified: string[]
  recommendation: string
}

export type SpacedRating = 'again' | 'hard' | 'good' | 'easy'

export interface Flashcard {
  id: string
  deckId: string
  question: string
  answer: string
  keyPoints?: string[]
  codeSnippet?: string
  sourceCitation?: string
  // Concept of the topic map the card tests
  concept?: string
  difficulty: 'easy' | 'medium' | 'hard'
  intervalDays: number
  repetitions: number
  lastReviewed?: string
  dueDate: string
}

export interface FlashcardDeck {
  id: string
  workspaceId: string
  title: string
  topicName: string
  totalCards: number
  dueTodayCount: number
  masteryPercentage: number
  cards: Flashcard[]
}

export type StudyTaskKind = 'learn' | 'practice' | 'review' | 'flashcards' | 'final' | 'setup'

export interface StudyTask {
  id: string
  workspaceId: string
  title: string
  description: string
  /** Concept the task is about (or a label such as "Flashcards") */
  topicName: string
  /** Topic-map topic the concept belongs to */
  topic?: string | null
  estimatedMinutes: number
  priority: 'high' | 'medium' | 'low'
  kind: StudyTaskKind
  type: 'quiz' | 'tutor' | 'flashcard' | 'reading' | 'study'
  /** Page that opens the task (tutor with a ready question, quiz, flashcards, sources) */
  href: string
  completed: boolean
  scheduledFor: 'today' | 'this_week' | 'upcoming'
  /** YYYY-MM-DD */
  scheduledDate: string
  /** Planned for an earlier day and not done then */
  carriedOver?: boolean
  /** Done before the day it was planned for */
  doneAhead?: boolean
}

export interface StudyPlanCoverage {
  totalConcepts: number
  mastered: number
  inProgress: number
  notStarted: number
}

export interface StudyPlan {
  workspaceId: string
  /** The learner's date the plan was built for (YYYY-MM-DD) */
  date: string
  dailyTargetMinutes: number
  todayCompletedMinutes: number
  todayPlannedMinutes: number
  weeklyTargetMinutes: number
  weekCompletedMinutes: number
  /** Minutes a day needed to cover everything by the target date */
  neededDailyMinutes: number
  onTrack: boolean
  /** Day the last concept task is planned for */
  expectedFinishDate?: string | null
  coverage: StudyPlanCoverage
  tasks: StudyTask[]
  /** Target completion date (YYYY-MM-DD) */
  targetDate?: string | null
  /** Days left until the target date (negative once it has passed) */
  daysRemaining?: number | null
  /** True when the target date is before today: no plan is generated until it is moved */
  targetPassed?: boolean
}

export interface TodayPlanTask extends StudyTask {
  workspaceName: string
}

export interface TodayPlanWorkspace {
  workspaceId: string
  workspaceName: string
  targetDate?: string | null
  daysRemaining?: number | null
  targetPassed: boolean
  dailyTargetMinutes: number
  todayCompletedMinutes: number
  todayPlannedMinutes: number
  openTasks: number
  onTrack: boolean
  neededDailyMinutes: number
}

export interface TodayPlan {
  date: string
  plannedMinutes: number
  completedMinutes: number
  dailyTargetMinutes: number
  openTasks: number
  tasks: TodayPlanTask[]
  workspaces: TodayPlanWorkspace[]
}

export type ActivityType =
  | 'quiz_completed'
  | 'flashcard_review'
  | 'mastery_change'
  | 'roadmap_adapted'
  | 'source_added'
  | 'tutor_session'
  | 'study_task_completed'

export interface LearningActivity {
  id: string
  workspaceId: string
  workspaceName?: string
  type: ActivityType
  title: string
  description: string
  scoreBadge?: string
  /** Display label for the event time (e.g. "10:14 AM") */
  timestamp: string
  /** Raw ISO-8601 time the event occurred, as returned by the backend */
  occurredAt?: string
  metadata?: Record<string, string | number>
}

export interface TutorCitation {
  id: string
  documentId: string
  documentName: string
  pageOrSlide: number
  excerpt: string
  relevanceScore: number
}

export interface TutorMessage {
  id: string
  workspaceId: string
  conversationId?: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  citations?: TutorCitation[]
  suggestedFollowUps?: string[]
  feedback?: 'like' | 'dislike'
}

export interface NotificationItem {
  id: string
  title: string
  message: string
  type: 'recommendation' | 'roadmap' | 'quiz' | 'streak'
  timestamp: string
  read: boolean
  link?: string
}
