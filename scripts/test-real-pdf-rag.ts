import { ragEngine } from '../lib/server/rag-engine'

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

  const wsId = `ws_test_real_rag_${Date.now()}`
  ragEngine.createWorkspace({
    id: wsId,
    name: 'SSL & Secure Systems Track',
    goal: 'Master Secure Sockets Layer and Network Security',
    level: 'advanced',
  })

  // 1. Ingest a multi-page PDF/Document text representing SSL-UNIT - 1
  const sslDocContent = `
PAGE 1: Unit 1 - Introduction to Secure Sockets Layer (SSL) and Transport Layer Security (TLS).
SSL provides end-to-end security, data integrity, and authentication for TCP connections.
The core architecture consists of the Handshake Protocol, Change Cipher Spec Protocol, Alert Protocol, and Record Protocol.

PAGE 2: SSL Handshake Protocol Sequence:
Phase 1: Client Hello and Server Hello. The client sends supported cipher suites and a 32-byte client_random nonce.
The server responds with selected cipher suite, server_random nonce, and session_id.
Phase 2: Server Certificate exchange, Server Key Exchange (for ECDHE / DHE), and Server Hello Done.

PAGE 3: Cryptographic Key Derivation and Premaster Secret:
The client generates a 48-byte Premaster Secret, encrypts it with the server's public key (or derives it via Diffie-Hellman),
and sends Client Key Exchange. Both parties compute the Master Secret = PRF(Premaster Secret, "master secret", client_random + server_random).

PAGE 4: Symmetric Encryption and Message Authentication Codes (MAC):
Once Handshake is complete, Change Cipher Spec is activated. The Record Layer fragments application data,
computes HMAC-SHA256 integrity tag, and encrypts with AES-GCM (Galois/Counter Mode) authenticated encryption.

PAGE 5: Alert Protocol and Error Handling:
Alert messages are classified into Warning (level 1) and Fatal (level 2).
Fatal alerts immediately terminate the secure connection and invalidate the session ID in the session cache.
`

  console.log('▶ STEP 1: Ingesting multi-page document into workspace...')
  const doc = ragEngine.addDocument(
    wsId,
    'SSL Unit 1 - Security Protocols',
    'SSL-UNIT - 1 (1).pdf',
    Buffer.from(sslDocContent, 'utf-8'),
    'pdf'
  )

  assert(doc.pagesCount >= 5, `Document parsed with ${doc.pagesCount} pages`)
  assert(doc.chunksCount >= 5, `Generated ${doc.chunksCount} chunks across pages`)

  // 2. Test Document-Wide Summary
  console.log('\n▶ STEP 2: Testing Document-Wide Summary Intent ("summarize the concepts in this pdf")...')
  const summaryRes = await ragEngine.generateGroundedAnswer(
    wsId,
    'provide me what are the concepts provide in this pdf summarize it'
  )

  assert(summaryRes.isGrounded === true, 'Summary query recognized as grounded')
  assert(summaryRes.citations.length >= 2, `Citations include multiple pages (${summaryRes.citations.length} citations)`)
  assert(summaryRes.answer.includes('Handshake') || summaryRes.answer.includes('Record Protocol') || summaryRes.answer.includes('SSL'), 'Answer contains real SSL concepts')
  assert(!summaryRes.answer.includes('Follow the sequential steps and review domain constraints'), 'Generic 3-bullet template is NOT present')

  console.log('\n  [Generated Summary Snippet]:')
  console.log('  ' + summaryRes.answer.slice(0, 300).replace(/\n/g, '\n  ') + '...\n')

  // 3. Test Specific Distinctive Fact
  console.log('▶ STEP 3: Testing Specific Distinctive Fact ("How is the Master Secret computed?")...')
  const factRes = await ragEngine.generateGroundedAnswer(
    wsId,
    'How is the Master Secret computed from the Premaster Secret?'
  )

  assert(factRes.isGrounded === true, 'Fact query is grounded')
  assert(factRes.citations.length >= 1, 'Citation generated for specific fact')
  assert(factRes.citations[0].pageOrSlide === 3, 'Citation accurately points to Page 3 (where Master Secret is defined)')
  assert(factRes.answer.includes('Premaster') || factRes.answer.includes('PRF') || factRes.answer.includes('Master Secret'), 'Answer explains Master Secret calculation')

  // 4. Test Missing Information Refusal
  console.log('\n▶ STEP 4: Testing Missing Information Refusal ("What does this PDF say about the Roman Colosseum?")...')
  const missingRes = await ragEngine.generateGroundedAnswer(
    wsId,
    'What does this PDF say about the architecture of the Roman Colosseum?'
  )

  assert(missingRes.isGrounded === false, 'Missing info query marked as ungrounded')
  assert(missingRes.citations.length === 0, 'Refusal returns 0 citations')
  assert(missingRes.answer.includes('do not contain enough information'), 'Refusal uses standard grounded refusal response')

  // 5. Test Cross-Workspace Isolation
  console.log('\n▶ STEP 5: Testing Cross-Workspace Isolation on Workspace B (Empty)...')
  const wsBId = `ws_empty_isolation_${Date.now()}`
  ragEngine.createWorkspace({
    id: wsBId,
    name: 'Empty Workspace B',
    goal: 'Testing isolation',
    level: 'beginner',
  })

  const wsBRes = await ragEngine.generateGroundedAnswer(
    wsBId,
    'How is the Master Secret computed from the Premaster Secret?'
  )

  assert(wsBRes.isGrounded === false, 'Workspace B query is ungrounded')
  assert(wsBRes.citations.length === 0, 'Workspace B returns 0 citations')
  assert(wsBRes.answer.includes('do not contain enough information'), 'Workspace B cannot see SSL document')

  // Clean up
  ragEngine.deleteWorkspace(wsId)
  ragEngine.deleteWorkspace(wsBId)

  console.log('\n===============================================================')
  console.log('  🎉 ALL REAL RAG AND GROUNDING TESTS PASSED!')
  console.log('===============================================================\n')
}

runRealRagTests().catch((err) => {
  console.error('Test failed:', err)
  process.exit(1)
})
