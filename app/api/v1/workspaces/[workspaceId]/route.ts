import { NextRequest, NextResponse } from 'next/server'
import { ragEngine } from '@/lib/server/rag-engine'

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ workspaceId: string }> }
) {
  const { workspaceId } = await params
  const ws = ragEngine.getWorkspaceById(workspaceId)
  if (!ws) {
    return NextResponse.json({ detail: `Workspace '${workspaceId}' not found` }, { status: 404 })
  }
  return NextResponse.json(ws)
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ workspaceId: string }> }
) {
  const { workspaceId } = await params
  ragEngine.deleteWorkspace(workspaceId)
  return NextResponse.json({ success: true, message: `Workspace '${workspaceId}' deleted` })
}
