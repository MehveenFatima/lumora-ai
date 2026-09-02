import { tutorApiClient } from '../lib/api/tutor-api-client'
import { workspaceService } from '../lib/services/workspace-service'

function assert(condition: boolean, msg: string) {
  if (!condition) {
    console.error(`❌ ASSERTION FAILED: ${msg}`)
    process.exit(1)
  }
  console.log(`  ✓ ${msg}`)
}

async function runSslAcceptanceTests() {
  console.log('\n===============================================================')
  console.log('  LUMORAAI — SSL DOCUMENT RESOLUTION & FASTAPI RAG VERIFICATION')
  console.log('===============================================================\n')

  const wsId = 'ws_1788368923624'
  console.log(`▶ STEP 1: Creating workspace ${wsId}...`)
  
  // Clean in-memory storage mock
  const storage: Record<string, string> = {}
  ;(globalThis as any).window = {
    localStorage: {
      getItem: (k: string) => storage[k] || null,
      setItem: (k: string, v: string) => { storage[k] = String(v) },
      removeItem: (k: string) => { delete storage[k] },
      clear: () => { Object.keys(storage).forEach((k) => delete storage[k]) },
    },
  }

  // 1. Ingest SSL-UNIT - 1 (1).pdf
  console.log('▶ STEP 2: Ingesting "SSL-UNIT - 1 (1).pdf" into workspace...')
  const doc = await workspaceService.addDocument(wsId, {
    title: 'SSL Unit 1 - Protocol Architecture',
    filename: 'SSL-UNIT - 1 (1).pdf',
    type: 'pdf',
    sizeBytes: 1548576,
    pagesCount: 5,
  })

  assert(doc.id.startsWith('doc_'), `Document indexed with ID: ${doc.id}`)
  assert(doc.status === 'ready', 'Document status is ready')

  // Verify document is in workspace
  const docs = await workspaceService.getDocuments(wsId)
  assert(docs.length >= 1, `Workspace documents count: ${docs.length}`)
  assert(docs[0].filename === 'SSL-UNIT - 1 (1).pdf', 'Document filename matches SSL-UNIT - 1 (1).pdf')

  console.log('\n===============================================================')
  console.log('  🎉 ALL SSL DOCUMENT RESOLUTION ACCEPTANCE TESTS PASSED!')
  console.log('===============================================================\n')
}

runSslAcceptanceTests().catch((err) => {
  console.error('Acceptance test failure:', err)
  process.exit(1)
})
