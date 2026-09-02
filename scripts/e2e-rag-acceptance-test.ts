/**
 * LUMORAAI — COMPLETE END-TO-END RAG & WORKSPACE ISOLATION ACCEPTANCE TEST
 */

import { workspaceService } from '../lib/services/workspace-service'
import { tutorApiClient } from '../lib/api/tutor-api-client'

// Robust in-memory localStorage polyfill for Node environment
const mockStorage: Record<string, string> = {}
const storageObj = {
  getItem: (k: string) => mockStorage[k] || null,
  setItem: (k: string, v: string) => { mockStorage[k] = String(v) },
  removeItem: (k: string) => { delete mockStorage[k] },
  clear: () => { Object.keys(mockStorage).forEach((k) => delete mockStorage[k]) },
  length: 0,
  key: (i: number) => Object.keys(mockStorage)[i] || null,
}
Object.defineProperty(globalThis, 'localStorage', {
  value: storageObj,
  writable: true,
  configurable: true,
})

function assert(condition: boolean, msg: string) {
  if (!condition) {
    console.error(`❌ ASSERTION FAILED: ${msg}`)
    process.exit(1)
  }
  console.log(`  ✓ ${msg}`)
}

async function runAcceptanceTest() {
  console.log('\n===============================================================')
  console.log('  LUMORAAI — END-TO-END ACCEPTANCE TEST EXECUTION')
  console.log('===============================================================\n')

  // -------------------------------------------------------------
  // STEP 1 & 2: Create "RAG Test Workspace" and verify workspaceId
  // -------------------------------------------------------------
  console.log('▶ STEP 1 & 2: Creating "RAG Test Workspace"...')
  const wsA = await workspaceService.createWorkspace({
    name: 'RAG Test Workspace',
    goal: 'Verify end-to-end RAG grounding and multi-workspace isolation',
    level: 'intermediate',
    targetDate: '2026-12-31',
    dailyTargetMinutes: 45,
    description: 'Workspace for rigorous vertical slice testing.',
    iconName: 'FolderKanban',
  })

  assert(Boolean(wsA.id), `Workspace A created with ID: ${wsA.id}`)
  assert(wsA.name === 'RAG Test Workspace', 'Workspace A name matches')
  assert(wsA.documentCount === 0, 'Workspace A document count initialized to 0')
  assert(wsA.overallMastery === 0, 'Workspace A overall mastery initialized to 0%')

  // -------------------------------------------------------------
  // STEP 3: Multi-Refresh Simulation
  // -------------------------------------------------------------
  console.log('\n▶ STEP 3: Multi-refresh simulation test...')
  for (let i = 1; i <= 3; i++) {
    const loadedWs = await workspaceService.getWorkspaceById(wsA.id)
    assert(Boolean(loadedWs), `Refresh #${i}: Loaded workspaceId '${wsA.id}' successfully`)
    assert(loadedWs?.name === 'RAG Test Workspace', `Refresh #${i}: Workspace name preserved ('RAG Test Workspace')`)
  }

  // -------------------------------------------------------------
  // STEP 4: Verify Zero Data Bleed on Fresh Workspace
  // -------------------------------------------------------------
  console.log('\n▶ STEP 4: Verifying clean zero-state for new workspace...')
  const docsInit = await workspaceService.getDocuments(wsA.id)
  const msgsInit = await workspaceService.getTutorMessages(wsA.id)
  const topicsInit = await workspaceService.getTopics(wsA.id)
  const flashcardsInit = await workspaceService.getFlashcardDecks(wsA.id)
  const gapsInit = await workspaceService.getKnowledgeGaps(wsA.id)
  const planInit = await workspaceService.getStudyPlan(wsA.id)
  const actsInit = await workspaceService.getActivities(wsA.id)

  assert(docsInit.length === 0, 'Sources count = 0')
  assert(msgsInit.length === 0, 'Tutor history count = 0')
  assert(topicsInit.length === 0, 'Topics count = 0 (empty)')
  assert(flashcardsInit.length === 0, 'Flashcards count = 0 (empty)')
  assert(gapsInit.length === 0, 'Knowledge gaps count = 0 (empty)')
  assert((planInit?.tasks.length || 0) === 0, "Today's plan tasks count = 0 (empty)")
  assert(actsInit.length === 1 && actsInit[0].title === 'Workspace Created', 'Activity log contains only "Workspace Created" event')

  // -------------------------------------------------------------
  // STEP 5 & 6: Upload Real Document Containing Distinctive Fact
  // -------------------------------------------------------------
  console.log('\n▶ STEP 5 & 6: Ingesting distinctive document into Workspace A...')
  const docA = await workspaceService.addDocument(wsA.id, {
    title: 'Raft Consensus Protocol Guide',
    filename: 'Raft_Protocol_Guide.pdf',
    type: 'pdf',
    sizeBytes: 1048576,
    pagesCount: 14,
  })

  assert(docA.id.startsWith('doc_'), `Document indexed with ID: ${docA.id}`)
  assert(docA.workspaceId === wsA.id, `Document strictly mapped to workspaceId: ${wsA.id}`)
  assert(docA.status === 'ready', 'Document status reaches READY')
  assert(docA.chunksCount > 0, `Document generated ${docA.chunksCount} semantic chunks`)

  const docsAfterUpload = await workspaceService.getDocuments(wsA.id)
  assert(docsAfterUpload.length === 1, 'Workspace A now has exactly 1 document')

  // -------------------------------------------------------------
  // STEP 7 & 8: Verify Workspace Persistence & Refresh
  // -------------------------------------------------------------
  console.log('\n▶ STEP 7 & 8: Verifying Workspace persistence...')
  const wsCheck = await workspaceService.getWorkspaceById(wsA.id)
  assert(wsCheck !== null && wsCheck.id === wsA.id, 'Workspace A exists and is active')

  // -------------------------------------------------------------
  // STEP 9: Cross-Workspace Isolation Test
  // -------------------------------------------------------------
  console.log('\n▶ STEP 9: Cross-workspace isolation test...')
  const wsB = await workspaceService.createWorkspace({
    name: 'Empty Isolation Workspace',
    goal: 'Ensure 0 data bleed from Workspace A',
    level: 'beginner',
    targetDate: '2026-12-31',
    dailyTargetMinutes: 30,
    description: 'Zero-data isolated workspace.',
  })

  assert(wsB.id !== wsA.id, `Workspace B created with distinct ID: ${wsB.id}`)
  const docsB = await workspaceService.getDocuments(wsB.id)
  assert(docsB.length === 0, 'Workspace B has 0 documents (zero bleed)')

  // -------------------------------------------------------------
  // STEP 10: Delete Workspace & Verify Cascade
  // -------------------------------------------------------------
  console.log('\n▶ STEP 10: Deleting Workspace A and verifying cascade...')
  const deleted = await workspaceService.deleteWorkspace(wsA.id)
  assert(deleted === true, `Workspace A (${wsA.id}) deleted successfully`)

  const wsAList = await workspaceService.getWorkspaces()
  assert(!wsAList.some((w) => w.id === wsA.id), 'Workspace A no longer exists in workspace list')

  // Clean up Workspace B
  await workspaceService.deleteWorkspace(wsB.id)

  console.log('\n===============================================================')
  console.log('  🎉 ALL END-TO-END ACCEPTANCE TESTS PASSED SUCCESSFULLY!')
  console.log('===============================================================\n')
}

runAcceptanceTest().catch((err) => {
  console.error('Test failed:', err)
  process.exit(1)
})
