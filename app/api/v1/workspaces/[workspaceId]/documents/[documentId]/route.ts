import { NextRequest, NextResponse } from 'next/server'
import { ragEngine } from '@/lib/server/rag-engine'

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ workspaceId: string; documentId: string }> }
) {
  const { documentId } = await params
  const success = ragEngine.deleteDocument(documentId)
  return NextResponse.json({ success })
}
