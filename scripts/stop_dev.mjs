// Stops any LumoraAI development servers left running (`npm run stop`).
// Useful when a terminal was closed or Ctrl+C did not reach every process.
import { spawnSync } from 'child_process'
import { fileURLToPath } from 'url'

const PATTERNS = ['uvicorn backend.app.main', 'next dev', 'next-server', 'scripts/start_dev_all.mjs']

export async function stopDevServers() {
  if (process.platform === 'win32') {
    for (const port of [3000, 8000]) {
      const out = spawnSync('cmd', ['/c', `netstat -ano | findstr :${port} | findstr LISTENING`], { encoding: 'utf8' }).stdout || ''
      for (const pid of new Set(out.trim().split(/\s+/).filter((t, i, a) => i % 5 === 4 && /^\d+$/.test(t)))) {
        spawnSync('taskkill', ['/pid', pid, '/f', '/t'])
      }
    }
  } else {
    for (const pattern of PATTERNS) {
      // Never stop the process running this script
      const out = spawnSync('pgrep', ['-f', pattern], { encoding: 'utf8' }).stdout || ''
      for (const pid of out.split('\n').map((s) => s.trim()).filter(Boolean)) {
        if (Number(pid) !== process.pid && Number(pid) !== process.ppid) {
          try {
            process.kill(Number(pid), 'SIGKILL')
          } catch {
            // already gone
          }
        }
      }
    }
  }
  await new Promise((r) => setTimeout(r, 800))
  console.log('Stopped any running LumoraAI servers (ports 3000 and 8000 are free).')
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  stopDevServers()
}
