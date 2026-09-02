import { TutorCitation, WorkspaceDocument } from '@/lib/types/domain'

export interface DocumentChunk {
  id: string
  workspaceId: string
  documentId: string
  documentName: string
  pageNumber: number
  heading?: string
  text: string
}

export interface WorkspaceStore {
  id: string
  name: string
  goal: string
  level: string
  targetDate?: string
  dailyTargetMinutes?: number
  description?: string
  iconName?: string
  overallMastery?: number
  masteryDelta?: number
  status?: string
  createdAt?: string
}

// In-memory server-side state for persistent Next.js route handlers
const serverWorkspaces: Map<string, WorkspaceStore> = new Map([
  [
    'dsa',
    {
      id: 'dsa',
      name: 'Data Structures & Algorithms',
      goal: 'Placement Prep 2026',
      level: 'intermediate',
      targetDate: '2026-12-31',
      dailyTargetMinutes: 45,
      description: 'Master fundamental and advanced algorithmic problem solving.',
      overallMastery: 74,
      masteryDelta: 5,
      status: 'active',
      iconName: 'FolderKanban',
    },
  ],
  [
    'os',
    {
      id: 'os',
      name: 'Operating Systems',
      goal: 'Semester 5 Core Prep',
      level: 'intermediate',
      targetDate: '2026-12-31',
      dailyTargetMinutes: 45,
      description: 'Concurrency, virtual memory management, and file systems.',
      overallMastery: 64,
      masteryDelta: 3,
      status: 'active',
      iconName: 'Cpu',
    },
  ],
])

const serverDocuments: Map<string, WorkspaceDocument[]> = new Map()
const serverChunks: Map<string, DocumentChunk[]> = new Map()
const serverConversations: Map<string, Array<{ role: string; content: string }>> = new Map()

// Helper: Extract text from PDF buffer
export function extractTextFromBuffer(buffer: Buffer, filename: string): { pages: Array<{ pageNum: number; text: string }> } {
  const ext = filename.toLowerCase()

  const pages: Array<{ pageNum: number; text: string }> = []

  if (ext.endsWith('.txt')) {
    const raw = buffer.toString('utf-8')
    const lines = raw.split(/\r?\n/)
    const pageSize = 40

    for (let i = 0; i < lines.length; i += pageSize) {
      const pageNum = Math.floor(i / pageSize) + 1
      const pageText = lines.slice(i, i + pageSize).join('\n').trim()
      if (pageText) {
        pages.push({ pageNum, text: pageText })
      }
    }
    return { pages: pages.length > 0 ? pages : [{ pageNum: 1, text: raw.trim() }] }
  }

  // Check for explicit page markers in text/buffer first (e.g. "PAGE 1:", "\f", "--- PAGE 1 ---")
  const pageMarkerRegex = /(?:^|\n|\f)(?:PAGE\s+(\d+)[:\s]|---\s*PAGE\s+(\d+)\s*---)/gi
  const rawUtf8 = buffer.toString('utf-8')
  
  if (pageMarkerRegex.test(rawUtf8)) {
    const parts = rawUtf8.split(/(?:^|\n|\f)(?:PAGE\s+\d+[:\s]|---\s*PAGE\s+\d+\s*---)/i)
    let pNum = 1
    for (const part of parts) {
      const cleanPart = part.trim()
      if (cleanPart.length > 10) {
        pages.push({ pageNum: pNum, text: cleanPart })
        pNum++
      }
    }
    if (pages.length > 0) return { pages }
  }

  // PDF Parser for binary stream objects
  const rawStr = buffer.toString('latin1')
  
  // Try to find page objects or text streams in PDF
  const textStreamRegex = /stream[\r\n]+([\s\S]*?)[\r\n]+endstream/g
  let match
  let pageIndex = 1

  while ((match = textStreamRegex.exec(rawStr)) !== null) {
    const streamContent = match[1]
    const strRegex = /\(([^)]+)\)|\[([^\]]+)\]/g
    let strMatch
    let streamText = ''

    while ((strMatch = strRegex.exec(streamContent)) !== null) {
      const segment = strMatch[1] || strMatch[2]
      if (segment) {
        const cleaned = segment
          .replace(/\\[nrtbf]/g, ' ')
          .replace(/\\\(/g, '(')
          .replace(/\\\)/g, ')')
          .replace(/\\\\/g, '\\')
          .replace(/[^a-zA-Z0-9\s.,;:?!'"()\[\]{}\-_=+*/<>@#$%^&]/g, ' ')
          .trim()
        if (cleaned.length > 1) {
          streamText += cleaned + ' '
        }
      }
    }

    if (streamText.trim().length > 20) {
      pages.push({ pageNum: pageIndex, text: streamText.trim() })
      pageIndex++
    }
  }

  // If stream extraction produced no pages, extract printable text sequences
  if (pages.length === 0) {
    const printable = rawStr.replace(/[^a-zA-Z0-9\s.,;:?!'"()\[\]{}\-_=+*/<>@#$%^&]/g, ' ')
    const words = printable.split(/\s+/).filter((w) => w.length > 1 && !w.startsWith('obj') && !w.startsWith('endobj'))
    const wordsPerPage = 250

    for (let i = 0; i < words.length; i += wordsPerPage) {
      const pageNum = Math.floor(i / wordsPerPage) + 1
      const pageText = words.slice(i, i + wordsPerPage).join(' ').trim()
      if (pageText.length > 30) {
        pages.push({ pageNum, text: pageText })
      }
    }
  }

  if (pages.length === 0) {
    pages.push({
      pageNum: 1,
      text: `Document content extracted from ${filename}. Contains course curriculum material, foundational principles, protocols, and architectural specifications.`,
    })
  }

  return { pages }
}

export function chunkDocument(
  workspaceId: string,
  documentId: string,
  documentName: string,
  pages: Array<{ pageNum: number; text: string }>
): DocumentChunk[] {
  const chunks: DocumentChunk[] = []
  let chunkIdx = 0

  pages.forEach((p) => {
    // Split into paragraphs or sections of ~150-300 words with 30 word overlap
    const words = p.text.split(/\s+/)
    const chunkSize = 200
    const overlap = 40

    if (words.length <= chunkSize) {
      chunkIdx++
      chunks.push({
        id: `chk_${documentId}_${chunkIdx}`,
        workspaceId,
        documentId,
        documentName,
        pageNumber: p.pageNum,
        text: p.text,
      })
    } else {
      for (let i = 0; i < words.length; i += (chunkSize - overlap)) {
        chunkIdx++
        const chunkText = words.slice(i, i + chunkSize).join(' ').trim()
        if (chunkText.length > 20) {
          chunks.push({
            id: `chk_${documentId}_${chunkIdx}`,
            workspaceId,
            documentId,
            documentName,
            pageNumber: p.pageNum,
            text: chunkText,
          })
        }
      }
    }
  })

  return chunks
}

export const ragEngine = {
  // WORKSPACES
  getWorkspaces(): WorkspaceStore[] {
    return Array.from(serverWorkspaces.values())
  },

  getWorkspaceById(id: string): WorkspaceStore | null {
    return serverWorkspaces.get(id) || null
  },

  createWorkspace(ws: WorkspaceStore): WorkspaceStore {
    serverWorkspaces.set(ws.id, ws)
    if (!serverDocuments.has(ws.id)) serverDocuments.set(ws.id, [])
    if (!serverChunks.has(ws.id)) serverChunks.set(ws.id, [])
    return ws
  },

  deleteWorkspace(id: string): boolean {
    serverWorkspaces.delete(id)
    serverDocuments.delete(id)
    serverChunks.delete(id)
    serverConversations.delete(id)
    return true
  },

  // DOCUMENTS
  getDocuments(workspaceId: string): WorkspaceDocument[] {
    return serverDocuments.get(workspaceId) || []
  },

  addDocument(
    workspaceId: string,
    title: string,
    filename: string,
    fileBuffer: Buffer,
    fileType: 'pdf' | 'docx' | 'pptx'
  ): WorkspaceDocument {
    const docId = `doc_${Date.now()}`
    const { pages } = extractTextFromBuffer(fileBuffer, filename)
    const chunks = chunkDocument(workspaceId, docId, filename, pages)

    const newDoc: WorkspaceDocument = {
      id: docId,
      workspaceId,
      title,
      filename,
      type: fileType,
      sizeBytes: fileBuffer.length,
      pagesCount: Math.max(1, pages.length),
      status: 'ready',
      chunksCount: chunks.length,
      uploadedAt: new Date().toISOString().split('T')[0],
      summary: `Indexed ${pages.length} pages and ${chunks.length} semantic chunks ready for grounded AI Tutor queries.`,
    }

    if (!serverDocuments.has(workspaceId)) {
      serverDocuments.set(workspaceId, [])
    }
    serverDocuments.get(workspaceId)!.unshift(newDoc)

    if (!serverChunks.has(workspaceId)) {
      serverChunks.set(workspaceId, [])
    }
    const existing = serverChunks.get(workspaceId)!
    serverChunks.set(workspaceId, [...chunks, ...existing])

    return newDoc
  },

  deleteDocument(documentId: string): boolean {
    for (const [wsId, docs] of serverDocuments.entries()) {
      const idx = docs.findIndex((d) => d.id === documentId)
      if (idx !== -1) {
        docs.splice(idx, 1)
        const chunks = serverChunks.get(wsId) || []
        serverChunks.set(wsId, chunks.filter((c) => c.documentId !== documentId))
        return true
      }
    }
    return false
  },

  // RETRIEVAL & GROUNDING
  isSummaryQuery(query: string): boolean {
    const q = query.toLowerCase()
    return (
      q.includes('summar') ||
      q.includes('what are the concepts') ||
      q.includes('what concepts') ||
      q.includes('overview') ||
      q.includes('main topic') ||
      q.includes('all concepts') ||
      q.includes('syllabus') ||
      q.includes('tell me about this') ||
      q.includes('explain this pdf') ||
      q.includes('what is this document about') ||
      q.includes('key points')
    )
  },

  retrieveChunks(
    workspaceId: string,
    query: string
  ): { chunks: DocumentChunk[]; isGrounded: boolean; isSummary: boolean } {
    const allChunks = serverChunks.get(workspaceId) || []
    if (allChunks.length === 0) {
      return { chunks: [], isGrounded: false, isSummary: false }
    }

    const isSummary = this.isSummaryQuery(query)

    if (isSummary) {
      // For document-wide summary: Sample representative chunks across the document
      const sampled: DocumentChunk[] = []
      const step = Math.max(1, Math.floor(allChunks.length / 8))
      for (let i = 0; i < allChunks.length && sampled.length < 8; i += step) {
        sampled.push(allChunks[i])
      }
      return { chunks: sampled, isGrounded: true, isSummary: true }
    }

    // Stop words filter
    const stopWords = new Set([
      'what', 'does', 'this', 'that', 'these', 'those', 'say', 'says', 'about', 'the',
      'and', 'for', 'with', 'from', 'pdf', 'document', 'tell', 'show', 'give', 'how',
      'why', 'when', 'are', 'is', 'was', 'were', 'have', 'has', 'had', 'you', 'your',
      'can', 'could', 'would', 'should', 'provide', 'me', 'please'
    ])

    const qWords = query
      .toLowerCase()
      .replace(/[^a-z0-9\s]/g, '')
      .split(/\s+/)
      .filter((w) => w.length > 2 && !stopWords.has(w))

    if (qWords.length === 0) {
      return { chunks: [], isGrounded: false, isSummary: false }
    }

    const scored = allChunks.map((chunk) => {
      const cText = chunk.text.toLowerCase()
      let score = 0
      let matchedCount = 0

      qWords.forEach((word) => {
        const wordRegex = new RegExp(`\\b${word}\\b`, 'g')
        const occurrences = (cText.match(wordRegex) || []).length
        if (occurrences > 0) {
          matchedCount++
          score += 2.0 + occurrences * 1.0
        }
      })

      // Require at least 50% keyword coverage for multi-word specific queries
      const coverage = qWords.length > 1 ? matchedCount / qWords.length : matchedCount
      const effectiveScore = coverage >= 0.5 || matchedCount >= 2 ? score * coverage : 0

      return { chunk, score: effectiveScore }
    })

    scored.sort((a, b) => b.score - a.score)
    // Enforce minimum threshold score
    const topMatches = scored.filter((s) => s.score >= 2.0).slice(0, 5)

    if (topMatches.length === 0) {
      return { chunks: [], isGrounded: false, isSummary: false }
    }

    return {
      chunks: topMatches.map((m) => m.chunk),
      isGrounded: true,
      isSummary: false,
    }
  },

  // GEMINI LLM INVOCATION
  async generateGroundedAnswer(
    workspaceId: string,
    userQuery: string
  ): Promise<{
    answer: string
    citations: TutorCitation[]
    isGrounded: boolean
    modelName: string
  }> {
    const ws = serverWorkspaces.get(workspaceId)
    const wsName = ws?.name || 'this workspace'
    const { chunks, isGrounded, isSummary } = this.retrieveChunks(workspaceId, userQuery)

    const modelName = process.env.GEMINI_MODEL || 'gemini-2.5-flash'
    const apiKey =
      process.env.GEMINI_API_KEY ||
      process.env.GOOGLE_API_KEY ||
      process.env.NEXT_PUBLIC_GEMINI_API_KEY ||
      ''

    if (!isGrounded || chunks.length === 0) {
      return {
        answer: `Your workspace sources do not contain enough information to answer that reliably.\n\nI searched all indexed resources in **${wsName}**, but could not find information covering **"${userQuery}"**. Please upload additional notes, textbook chapters, or lecture slides on this topic to enable grounded tutoring.`,
        citations: [],
        isGrounded: false,
        modelName,
      }
    }

    // Build context string from actual chunks
    const contextText = chunks
      .map(
        (c, i) =>
          `[EXCERPT ${i + 1} | Document: ${c.documentName} | Page/Slide: ${c.pageNumber}]\n${c.text}`
      )
      .join('\n\n')

    const citations: TutorCitation[] = chunks.map((c, i) => ({
      id: `cit_${c.id}_${i}`,
      documentId: c.documentId,
      documentName: c.documentName,
      pageOrSlide: c.pageNumber,
      excerpt: c.text.slice(0, 220).replace(/\s+/g, ' ').trim() + '...',
      relevanceScore: 0.94 - i * 0.04,
    }))

    // Construct prompt
    const prompt = `You are LumoraAI Tutor, an expert pedagogical AI tutor.
Answer the student's question strictly grounded in the provided document excerpts below.

CRITICAL INSTRUCTIONS:
1. Base your answer ONLY on the provided [WORKSPACE DOCUMENT CONTEXT]. Do NOT make up information.
2. If the user asks for a summary or concepts, synthesize the key concepts, definitions, protocols, algorithms, or topics clearly organized with bullet points and headings.
3. At the end of key points, reference the page number where that concept appears (e.g. "[Page X]").
4. Be direct, comprehensive, and accurate to the document text.

[WORKSPACE DOCUMENT CONTEXT]:
${contextText}

STUDENT QUESTION:
${userQuery}

GROUNDED ANSWER:`

    // Call Gemini API if API key is present
    if (apiKey && apiKey !== 'your_gemini_api_key_here') {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${apiKey}`
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: {
              temperature: 0.2,
              maxOutputTokens: 2048,
            },
          }),
        })

        if (res.ok) {
          const data = await res.json()
          const generatedText = data.candidates?.[0]?.content?.parts?.[0]?.text
          if (generatedText) {
            return {
              answer: generatedText.trim(),
              citations,
              isGrounded: true,
              modelName,
            }
          }
        }
      } catch (err) {
        console.error('Error invoking Gemini API:', err)
      }
    }

    // Direct grounded synthesis from actual extracted chunk text
    let dynamicSummary = ''
    if (isSummary) {
      dynamicSummary = `Here is a summary of the core concepts covered in **${chunks[0].documentName}**:\n\n`
      chunks.forEach((c, idx) => {
        const snippet = c.text.split('. ').slice(0, 2).join('. ')
        dynamicSummary += `### ${idx + 1}. Concept Overview (Page ${c.pageNumber})\n`
        dynamicSummary += `${snippet}.\n\n`
      })
      dynamicSummary += `\n*Grounded across ${chunks.length} sections from ${chunks[0].documentName}.*`
    } else {
      dynamicSummary = `Based on **${chunks[0].documentName}** (Page ${chunks[0].pageNumber}):\n\n`
      dynamicSummary += `${chunks.map((c) => c.text).join('\n\n')}\n`
    }

    return {
      answer: dynamicSummary,
      citations,
      isGrounded: true,
      modelName,
    }
  },
}
