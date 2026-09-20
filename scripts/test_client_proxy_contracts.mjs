import assert from 'assert'

console.log('====================================================')
console.log('   Running Client & Proxy Architecture Test Suite   ')
console.log('====================================================\n')

let passedTests = 0

function runTest(name, fn) {
  try {
    fn()
    console.log(`\x1b[32m[PASS]\x1b[0m ${name}`)
    passedTests++
  } catch (err) {
    console.error(`\x1b[31m[FAIL]\x1b[0m ${name}`)
    console.error(err)
    process.exit(1)
  }
}

async function runAsyncTest(name, fn) {
  try {
    await fn()
    console.log(`\x1b[32m[PASS]\x1b[0m ${name}`)
    passedTests++
  } catch (err) {
    console.error(`\x1b[31m[FAIL]\x1b[0m ${name}`)
    console.error(err)
    process.exit(1)
  }
}

// -------------------------------------------------------------
// Test 1: Verify Client Code Never Constructs 127.0.0.1:8000 URLs
// -------------------------------------------------------------
await runAsyncTest('Test 1: Browser client constructs strictly relative /api/v1 URLs', async () => {
  // Simulate browser environment
  global.window = {}
  
  // Track all fetch calls
  const interceptedUrls = []
  const originalFetch = global.fetch
  global.fetch = async (url, options) => {
    interceptedUrls.push({ url, method: options?.method || 'GET' })
    return {
      ok: true,
      status: 200,
      json: async () => ({ id: 'mock-session', status: 'active', current_question: { id: 'q1' } }),
      text: async () => JSON.stringify({ ok: true }),
    }
  }

  try {
    // Dynamic import to test client
    const { tutorApiClient } = await import('../lib/api/tutor-api-client.ts')

    // Test Quiz creation
    await tutorApiClient.createQuizSession('dsa', { targetQuestionCount: 5 })
    assert.strictEqual(interceptedUrls[0].url, '/api/v1/workspaces/dsa/quizzes')
    assert.strictEqual(interceptedUrls[0].method, 'POST')

    // Test Active quiz lookup
    await tutorApiClient.getActiveQuizSession('dsa')
    assert.strictEqual(interceptedUrls[1].url, '/api/v1/workspaces/dsa/quizzes/active')
    assert.strictEqual(interceptedUrls[1].method, 'GET')

    // Test Submit Attempt
    await tutorApiClient.submitAttempt('dsa', 'sess1', 'q1', { selectedOption: 'A', responseTimeMs: 1200 })
    assert.strictEqual(interceptedUrls[2].url, '/api/v1/workspaces/dsa/quizzes/sess1/questions/q1/attempt')
    assert.strictEqual(interceptedUrls[2].method, 'POST')

    // Test Complete Quiz Session
    await tutorApiClient.completeQuizSession('dsa', 'sess1')
    assert.strictEqual(interceptedUrls[3].url, '/api/v1/workspaces/dsa/quizzes/sess1/complete')
    assert.strictEqual(interceptedUrls[3].method, 'POST')

    // Test Tutor message
    await tutorApiClient.askTutor('dsa', 'Explain red-black trees', 'conv1')
    assert.strictEqual(interceptedUrls[4].url, '/api/v1/workspaces/dsa/tutor')
    assert.strictEqual(interceptedUrls[4].method, 'POST')

    // Test Document listing
    await tutorApiClient.getWorkspaceDocuments('dsa')
    assert.strictEqual(interceptedUrls[5].url, '/api/v1/workspaces/dsa/documents')
    assert.strictEqual(interceptedUrls[5].method, 'GET')

    // Test Health check
    await tutorApiClient.getHealth()
    assert.strictEqual(interceptedUrls[6].url, '/api/v1/health')
    assert.strictEqual(interceptedUrls[6].method, 'GET')

    // Verify ZERO calls contain 127.0.0.1:8000
    for (const call of interceptedUrls) {
      assert(
        !call.url.includes('127.0.0.1:8000'),
        `CRITICAL VIOLATION: Browser call constructed direct 127.0.0.1 URL: ${call.url}`
      )
      assert(
        call.url.startsWith('/api/v1'),
        `CRITICAL VIOLATION: Browser call did not use /api/v1 proxy: ${call.url}`
      )
    }
  } finally {
    global.fetch = originalFetch
    delete global.window
  }
})

// -------------------------------------------------------------
// Test 2: Error Sanitization (Zero Secret & Host Leakage)
// -------------------------------------------------------------
await runAsyncTest('Test 2: Client fetch errors sanitize internal host and never leak 127.0.0.1:8000', async () => {
  global.window = {}
  const originalFetch = global.fetch
  global.fetch = async () => {
    throw new TypeError('fetch failed')
  }

  try {
    const { tutorApiClient } = await import('../lib/api/tutor-api-client.ts')
    try {
      await tutorApiClient.getActiveQuizSession('dsa')
      // getActiveQuizSession returns null on catch
    } catch (e) {
      assert(!e.message.includes('127.0.0.1:8000'), 'Error message leaked 127.0.0.1:8000')
    }

    let errorThrown = false
    try {
      await tutorApiClient.createQuizSession('dsa')
    } catch (e) {
      errorThrown = true
      assert(!e.message.includes('127.0.0.1:8000'), 'Error message leaked 127.0.0.1:8000')
    }
    assert(errorThrown, 'Expected createQuizSession to throw error on network failure')
  } finally {
    global.fetch = originalFetch
    delete global.window
  }
})

// -------------------------------------------------------------
// Test 3: Proxy Route Forwards Requests to FastAPI
// -------------------------------------------------------------
await runAsyncTest('Test 3: Live Next.js proxy forwards GET /api/v1/health to FastAPI', async () => {
  const res = await fetch('http://localhost:3000/api/v1/health')
  assert.strictEqual(res.status, 200, `Expected 200, got ${res.status}`)
  const data = await res.json()
  assert.strictEqual(data.status, 'ok')
  assert.strictEqual(data.backend, 'healthy')
  assert(data.ai, 'Expected ai field in health response')
  assert.strictEqual(data.ai.fallback_available, true)
})

await runAsyncTest('Test 4: Live Next.js proxy forwards GET /api/v1/workspaces/dsa/quizzes/active', async () => {
  const res = await fetch('http://localhost:3000/api/v1/workspaces/dsa/quizzes/active')
  assert(res.status === 200 || res.status === 404, `Expected 200 or 404, got ${res.status}`)
  if (res.status === 200) {
    const data = await res.json()
    assert.strictEqual(data.workspace_id, 'dsa')
  }
})

await runAsyncTest('Test 5: Live Next.js proxy forwards POST /api/v1/workspaces/dsa/quizzes', async () => {
  const res = await fetch('http://localhost:3000/api/v1/workspaces/dsa/quizzes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target_question_count: 5, initial_difficulty: 2 }),
  })
  assert.strictEqual(res.status, 201, `Expected 201 Created, got ${res.status}`)
  const data = await res.json()
  assert.strictEqual(data.workspace_id, 'dsa')
  assert.strictEqual(data.status, 'active')
  assert(data.current_question, 'Expected current_question in quiz session')
})

console.log(`\n\x1b[32mAll ${passedTests} Client & Proxy Architecture tests PASSED!\x1b[0m\n`)
