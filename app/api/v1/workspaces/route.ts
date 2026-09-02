import { NextRequest, NextResponse } from 'next/server'
import { ragEngine } from '@/lib/server/rag-engine'

export async function GET() {
  const workspaces = ragEngine.getWorkspaces()
  return NextResponse.json({ workspaces, total_count: workspaces.length })
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const id = body.id || `ws_${Date.now()}`
    const created = ragEngine.createWorkspace({
      id,
      name: body.name,
      goal: body.goal,
      level: body.level || 'intermediate',
      targetDate: body.target_date || '2026-12-31',
      dailyTargetMinutes: body.daily_target_minutes || 45,
      description: body.description || '',
      iconName: body.icon_name || 'FolderKanban',
    })
    return NextResponse.json(created, { status: 201 })
  } catch (err: any) {
    return NextResponse.json({ detail: err.message || 'Failed to create workspace' }, { status: 400 })
  }
}
