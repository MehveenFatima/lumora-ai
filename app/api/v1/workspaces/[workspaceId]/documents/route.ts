import { NextRequest, NextResponse } from 'next/server'
import { ragEngine } from '@/lib/server/rag-engine'

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ workspaceId: string }> }
) {
  const { workspaceId } = await params
  const docs = ragEngine.getDocuments(workspaceId)
  return NextResponse.json({ documents: docs, total_count: docs.length })
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ workspaceId: string }> }
) {
  const { workspaceId } = await params

  try {
    const formData = await req.formData()
    const file = formData.get('file') as File | null
    const title = (formData.get('title') as string) || (file ? file.name.replace(/\.[^/.]+$/, '') : 'Document')

    if (!file) {
      return NextResponse.json({ detail: 'No file provided in form-data' }, { status: 400 })
    }

    const buffer = Buffer.from(await file.arrayBuffer())
    const filename = file.name
    const ext = filename.toLowerCase()
    const fileType: 'pdf' | 'docx' | 'pptx' = ext.endsWith('.docx')
      ? 'docx'
      : ext.endsWith('.pptx')
      ? 'pptx'
      : 'pdf'

    const doc = ragEngine.addDocument(workspaceId, title, filename, buffer, fileType)

    return NextResponse.json(
      {
        id: doc.id,
        workspace_id: doc.workspaceId,
        title: doc.title,
        filename: doc.filename,
        file_type: doc.type,
        file_size: doc.sizeBytes,
        page_count: doc.pagesCount,
        status: doc.status,
        chunk_count: doc.chunksCount,
        summary: doc.summary,
        created_at: new Date().toISOString(),
      },
      { status: 201 }
    )
  } catch (err: any) {
    console.error('Document upload error:', err)
    return NextResponse.json({ detail: err.message || 'Failed to upload document' }, { status: 500 })
  }
}
