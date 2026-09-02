import { NextRequest, NextResponse } from 'next/server'
import { ragEngine } from '@/lib/server/rag-engine'

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ workspaceId: string }> }
) {
  const { workspaceId } = await params

  try {
    const body = await req.json()
    const userMessage = body.message || ''
    const conversationId = body.conversation_id || `conv_${Date.now()}`

    if (!userMessage.trim()) {
      return NextResponse.json({ detail: 'Message cannot be empty' }, { status: 400 })
    }

    const { answer, citations, isGrounded, modelName } = await ragEngine.generateGroundedAnswer(
      workspaceId,
      userMessage
    )

    const nowStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    const responsePayload = {
      conversation_id: conversationId,
      message: {
        id: `tm_a_${Date.now()}`,
        role: 'assistant',
        content: answer,
        timestamp: nowStr,
      },
      citations: citations.map((c) => ({
        id: c.id,
        document_id: c.documentId,
        document_name: c.documentName,
        page_or_slide: c.pageOrSlide,
        excerpt: c.excerpt,
        relevance_score: c.relevanceScore,
      })),
      retrieval: {
        chunks_considered: citations.length,
        grounded: isGrounded,
        top_similarity_score: citations.length > 0 ? citations[0].relevanceScore : 0,
        model_name: modelName,
      },
      suggested_follow_ups: isGrounded
        ? [
            'Can you explain this concept in more depth?',
            'What are common edge cases or practical examples?',
            'Quiz me on this concept',
          ]
        : [
            'How do I upload learning materials?',
            'What file formats are supported?',
          ],
    }

    return NextResponse.json(responsePayload)
  } catch (err: any) {
    console.error('Tutor route error:', err)
    return NextResponse.json({ detail: err.message || 'Tutor generation failed' }, { status: 500 })
  }
}
