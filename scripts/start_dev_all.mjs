import { spawn } from 'child_process'

console.log('====================================================')
console.log('   Starting LumoraAI Full-Stack Development Mode     ')
console.log('   FastAPI (:8000) + Next.js (:3000)                ')
console.log('====================================================\n')

const isWindows = process.platform === 'win32'
const npmCmd = isWindows ? 'npm.cmd' : 'npm'
const pythonCmd = isWindows ? 'python' : 'python3'

const backendProc = spawn(pythonCmd, ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload'], {
  stdio: ['inherit', 'pipe', 'pipe'],
  shell: isWindows,
})

backendProc.stdout?.on('data', (data) => {
  const lines = data.toString().trim().split('\n')
  for (const line of lines) {
    if (line.trim()) console.log(`\x1b[34m[FastAPI]\x1b[0m ${line.trim()}`)
  }
})

backendProc.stderr?.on('data', (data) => {
  const lines = data.toString().trim().split('\n')
  for (const line of lines) {
    if (line.trim()) console.log(`\x1b[33m[FastAPI]\x1b[0m ${line.trim()}`)
  }
})

const frontendProc = spawn(npmCmd, ['run', 'dev'], {
  stdio: ['inherit', 'pipe', 'pipe'],
  shell: isWindows,
})

frontendProc.stdout?.on('data', (data) => {
  const lines = data.toString().trim().split('\n')
  for (const line of lines) {
    if (line.trim()) console.log(`\x1b[32m[Next.js]\x1b[0m ${line.trim()}`)
  }
})

frontendProc.stderr?.on('data', (data) => {
  const lines = data.toString().trim().split('\n')
  for (const line of lines) {
    if (line.trim()) console.log(`\x1b[31m[Next.js]\x1b[0m ${line.trim()}`)
  }
})

function cleanup() {
  console.log('\nStopping LumoraAI servers...')
  if (isWindows) {
    if (backendProc.pid) spawn('taskkill', ['/pid', backendProc.pid.toString(), '/f', '/t'], { stdio: 'ignore' })
    if (frontendProc.pid) spawn('taskkill', ['/pid', frontendProc.pid.toString(), '/f', '/t'], { stdio: 'ignore' })
  } else {
    backendProc.kill('SIGTERM')
    frontendProc.kill('SIGTERM')
  }
  process.exit(0)
}

process.on('SIGINT', cleanup)
process.on('SIGTERM', cleanup)
process.on('exit', cleanup)
