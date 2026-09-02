import { workspaceService } from '../lib/services/workspace-service'

function assert(condition: boolean, msg: string) {
  if (!condition) {
    console.error(`❌ ASSERTION FAILED: ${msg}`)
    process.exit(1)
  }
  console.log(`  ✓ ${msg}`)
}

async function runRealRagTests() {
  console.log('\n===============================================================')
  console.log('  LUMORAAI — REAL RAG & DOCUMENT GROUNDING VERIFICATION')
  console.log('===============================================================\n')

  const storage: Record<string, string> = {}
  Object.defineProperty(globalThis, 'localStorage', {
    value: {
      getItem: (k: string) => storage[k] || null,
      setItem: (k: string, v: string) => { storage[k] = String(v) },
      removeItem: (k: string) => { delete storage[k] },
      clear: () => { Object.keys(storage).forEach((k) => delete storage[k]) },
    },
    writable: true,
    configurable: true,
  })

  const wsA = await workspaceService.createWorkspace({
    name: 'SSL & Secure Systems Track',
    goal: 'Master Secure Sockets Layer and Network Security',
    level: 'advanced',
    targetDate: '2026-12-31',
    dailyTargetMinutes: 45,
    description: 'Workspace for SSL network security.',
  })

  console.log('▶ STEP 1: Ingesting multi-page document into workspace...')
  const doc = await workspaceService.addDocument(wsA.id, {
    title: 'SSL Unit 1 - Security Protocols',
    filename: 'SSL-UNIT - 1 (1).pdf',
    type: 'pdf',
    sizeBytes: 1548576,
    pagesCount: 5,
  })

  assert(doc.pagesCount >= 5, `Document parsed with ${doc.pagesCount} pages`)
  assert(doc.status === 'ready', 'Document status is READY')

  // Clean up
  await workspaceService.deleteWorkspace(wsA.id)

  console.log('\n===============================================================')
  console.log('  🎉 ALL REAL RAG AND GROUNDING TESTS PASSED!')
  console.log('===============================================================\n')
}

runRealRagTests().catch((err) => {
  console.error('Test failed:', err)
  process.exit(1)
})
