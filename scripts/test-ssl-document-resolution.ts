import { ragEngine } from '../lib/server/rag-engine'

function assert(condition: boolean, msg: string) {
  if (!condition) {
    console.error(`❌ ASSERTION FAILED: ${msg}`)
    process.exit(1)
  }
  console.log(`  ✓ ${msg}`)
}

async function runSslAcceptanceTests() {
  console.log('\n===============================================================')
  console.log('  LUMORAAI — SSL DOCUMENT RESOLUTION & RAG VERIFICATION')
  console.log('===============================================================\n')

  const wsId = 'ws_1788368923624'
  ragEngine.createWorkspace({
    id: wsId,
    name: 'SSL Track',
    goal: 'Master Secure Sockets Layer and TLS Protocols',
    level: 'advanced',
  })

  // 1. Ingest SSL-UNIT - 1 (1).pdf with 5 distinct pages of authentic course text
  const sslDocContent = `
PAGE 1: Unit 1 - Introduction to Secure Sockets Layer (SSL) and Transport Layer Security (TLS).
SSL provides end-to-end transport layer security, data confidentiality, data integrity, and server/client authentication for TCP applications.
The core SSL/TLS architecture consists of four sub-protocols: Handshake Protocol, Change Cipher Spec Protocol, Alert Protocol, and Record Layer Protocol.

PAGE 2: SSL Handshake Protocol Sequence & Exchange:
Phase 1: Client Hello and Server Hello. The client transmits supported cipher suites and a 32-byte client_random nonce.
The server responds with selected cipher suite, server_random nonce, and session_id.
Phase 2: Server Certificate exchange, Server Key Exchange (ECDHE parameters), and Server Hello Done.

PAGE 3: Cryptographic Key Derivation and Master Secret Computation:
The client generates a 48-byte Premaster Secret, encrypts it with the server's public key (RSA) or derives it via Diffie-Hellman.
Both client and server independently compute Master Secret = PRF(Premaster Secret, "master secret", client_random + server_random).
From the 48-byte Master Secret, six session keys are generated: client write MAC key, server write MAC key, client write encryption key, server write encryption key, client write IV, and server write IV.

PAGE 4: SSL Record Protocol and Authenticated Encryption:
The Record Layer fragments application data, optionally compresses it, computes an HMAC-SHA256 integrity tag, and encrypts with AES-GCM (Galois/Counter Mode).
It prepends the record header (Type, Major/Minor Version, Length) before transmitting over TCP.

PAGE 5: Alert Protocol and Connection Termination:
Alert messages consist of two bytes: AlertLevel (1=Warning, 2=Fatal) and AlertDescription (e.g. bad_record_mac, handshake_failure, unexpected_message).
Fatal alerts immediately terminate the secure connection and invalidate the session ID in the session cache to prevent replay attacks.
`

  console.log('▶ STEP 1: Ingesting "SSL-UNIT - 1 (1).pdf" into workspace ws_1788368923624...')
  const doc = ragEngine.addDocument(
    wsId,
    'SSL Unit 1 - Protocol Architecture',
    'SSL-UNIT - 1 (1).pdf',
    Buffer.from(sslDocContent, 'utf-8'),
    'pdf'
  )

  assert(doc.pagesCount >= 5, `Document parsed with ${doc.pagesCount} pages`)
  assert(doc.chunksCount >= 5, `Document indexed with ${doc.chunksCount} chunks`)

  // -------------------------------------------------------------
  // TEST 1: User's exact failing query: "SSL-UNIT - 1 (1).pdf summarize it"
  // -------------------------------------------------------------
  console.log('\n▶ TEST 1: Exact failing query: "SSL-UNIT - 1 (1).pdf summarize it"')
  const res1 = await ragEngine.generateGroundedAnswer(wsId, 'SSL-UNIT - 1 (1).pdf summarize it')
  assert(res1.isGrounded === true, 'Query recognized as grounded')
  assert(res1.intent === 'DOCUMENT_SUMMARY', 'Intent classified as DOCUMENT_SUMMARY')
  assert(res1.documentName === 'SSL-UNIT - 1 (1).pdf', 'Resolved target document: SSL-UNIT - 1 (1).pdf')
  assert(res1.retrievedCount >= 3, `Retrieved ${res1.retrievedCount} chunks across pages`)
  assert(res1.retrievedPages.length >= 3, `Retrieved pages: [${res1.retrievedPages.join(', ')}]`)
  assert(res1.citations.length >= 3, `Generated ${res1.citations.length} citations`)
  assert(res1.answer.includes('SSL') || res1.answer.includes('Handshake'), 'Answer contains real SSL concepts')
  assert(!res1.answer.includes('do not contain enough information'), 'Did NOT falsely refuse')

  // -------------------------------------------------------------
  // TEST 2: "Summarize this PDF"
  // -------------------------------------------------------------
  console.log('\n▶ TEST 2: "Summarize this PDF"')
  const res2 = await ragEngine.generateGroundedAnswer(wsId, 'Summarize this PDF')
  assert(res2.isGrounded === true, 'Recognized as grounded')
  assert(res2.intent === 'DOCUMENT_SUMMARY', 'Intent = DOCUMENT_SUMMARY')
  assert(res2.citations.length >= 3, 'Generated multi-page citations')
  assert(!res2.answer.includes('do not contain enough information'), 'Did NOT falsely refuse')

  // -------------------------------------------------------------
  // TEST 3: "What are the main concepts covered in this document?"
  // -------------------------------------------------------------
  console.log('\n▶ TEST 3: "What are the main concepts covered in this document?"')
  const res3 = await ragEngine.generateGroundedAnswer(
    wsId,
    'What are the main concepts covered in this document?'
  )
  assert(res3.isGrounded === true, 'Recognized as grounded')
  assert(res3.intent === 'DOCUMENT_SUMMARY', 'Intent = DOCUMENT_SUMMARY')
  assert(res3.answer.includes('Handshake') || res3.answer.includes('Record Layer') || res3.answer.includes('Alert'), 'Answer covers main SSL concepts')

  // -------------------------------------------------------------
  // TEST 4: "What is SSL?"
  // -------------------------------------------------------------
  console.log('\n▶ TEST 4: "What is SSL?"')
  const res4 = await ragEngine.generateGroundedAnswer(wsId, 'What is SSL?')
  assert(res4.isGrounded === true, 'Recognized as grounded')
  assert(res4.citations.length >= 1, 'Citation generated')
  assert(res4.answer.includes('transport layer security') || res4.answer.includes('TCP'), 'Answer defines SSL accurately')

  // -------------------------------------------------------------
  // TEST 5: "Explain the SSL handshake"
  // -------------------------------------------------------------
  console.log('\n▶ TEST 5: "Explain the SSL handshake"')
  const res5 = await ragEngine.generateGroundedAnswer(wsId, 'Explain the SSL handshake')
  assert(res5.isGrounded === true, 'Recognized as grounded')
  assert(res5.citations.length >= 1, 'Citation generated')
  assert(res5.retrievedPages.includes(2), 'Citation targets Page 2 (where Handshake is detailed)')
  assert(res5.answer.includes('Client Hello') || res5.answer.includes('Server Hello'), 'Answer explains handshake phases')

  // -------------------------------------------------------------
  // TEST 6: Distinctive fact from page 3 ("How is the Master Secret computed?")
  // -------------------------------------------------------------
  console.log('\n▶ TEST 6: Distinctive fact: "How is the Master Secret computed from Premaster Secret?"')
  const res6 = await ragEngine.generateGroundedAnswer(
    wsId,
    'How is the Master Secret computed from Premaster Secret?'
  )
  assert(res6.isGrounded === true, 'Recognized as grounded')
  assert(res6.retrievedPages.includes(3), 'Citation accurately points to Page 3')
  assert(res6.answer.includes('Premaster') || res6.answer.includes('PRF') || res6.answer.includes('Master Secret'), 'Answer explains PRF computation')

  // -------------------------------------------------------------
  // TEST 7: Missing information refusal ("Roman Colosseum")
  // -------------------------------------------------------------
  console.log('\n▶ TEST 7: Missing info refusal: "What does this PDF say about the architecture of the Roman Colosseum?"')
  const res7 = await ragEngine.generateGroundedAnswer(
    wsId,
    'What does this PDF say about the architecture of the Roman Colosseum?'
  )
  assert(res7.isGrounded === false, 'Recognized as ungrounded')
  assert(res7.citations.length === 0, 'Returns 0 citations')
  assert(res7.answer.includes('do not contain enough information'), 'Refusal uses standard grounded refusal response')

  // -------------------------------------------------------------
  // TEST 8: Cross-workspace isolation on Workspace B (Empty)
  // -------------------------------------------------------------
  console.log('\n▶ TEST 8: Cross-workspace isolation on Workspace B (Empty)...')
  const wsBId = 'ws_empty_isolation_test_b'
  ragEngine.createWorkspace({
    id: wsBId,
    name: 'Empty Workspace B',
    goal: 'Isolation test',
    level: 'beginner',
  })
  const res8 = await ragEngine.generateGroundedAnswer(wsBId, 'Explain the SSL handshake')
  assert(res8.isGrounded === false, 'Workspace B is ungrounded')
  assert(res8.citations.length === 0, 'Workspace B returns 0 citations')
  assert(res8.answer.includes('do not contain enough information'), 'Workspace B cannot see Workspace A documents')

  // -------------------------------------------------------------
  // TEST 9: Multi-turn document reference ("it")
  // -------------------------------------------------------------
  console.log('\n▶ TEST 9: Multi-turn reference: "Give me the important exam concepts from it"')
  const res9 = await ragEngine.generateGroundedAnswer(
    wsId,
    'Give me the important exam concepts from it'
  )
  assert(res9.isGrounded === true, 'Resolved "it" to the workspace document')
  assert(res9.intent === 'DOCUMENT_SUMMARY', 'Classified as summary intent')
  assert(res9.citations.length >= 3, 'Generated multi-page citations')

  // Clean up
  ragEngine.deleteWorkspace(wsId)
  ragEngine.deleteWorkspace(wsBId)

  console.log('\n===============================================================')
  console.log('  🎉 ALL SSL DOCUMENT RESOLUTION ACCEPTANCE TESTS PASSED!')
  console.log('===============================================================\n')
}

runSslAcceptanceTests().catch((err) => {
  console.error('Acceptance test failure:', err)
  process.exit(1)
})
