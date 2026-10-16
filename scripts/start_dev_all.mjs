// Starts FastAPI (:8000) and Next.js (:3000) together for local development: `npm run dev:all`.
// Ctrl+C stops both, including every process they started. If an older copy is still running
// (for example after a closed terminal), this script says so instead of starting a second one;
// `npm run stop` clears it.
import { spawn } from 'child_process'
import net from 'net'
import { stopDevServers } from './stop_dev.mjs'

const isWindows = process.platform === 'win32'
const pythonCmd = isWindows ? 'python' : 'python3'
const nextBin = isWindows ? 'node_modules\\.bin\\next.cmd' : 'node_modules/.bin/next'

const color = (code, label) => `\x1b[${code}m${label}\x1b[0m`
const children = []
let stopping = false

function portInUse(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ port, host: '127.0.0.1' })
    socket.once('connect', () => {
      socket.destroy()
      resolve(true)
    })
    socket.once('error', () => resolve(false))
    socket.setTimeout(1000, () => {
      socket.destroy()
      resolve(false)
    })
  })
}

function run(label, labelColor, command, args) {
  // detached: each server gets its own process group, so the whole group can be stopped at once
  const child = spawn(command, args, {
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: isWindows,
    detached: !isWindows,
    env: process.env,
  })
  const print = (data, errColor) => {
    for (const line of data.toString().split('\n')) {
      if (line.trim()) console.log(`${color(errColor || labelColor, `[${label}]`)} ${line.trimEnd()}`)
    }
  }
  child.stdout?.on('data', (d) => print(d))
  child.stderr?.on('data', (d) => print(d, label === 'Next.js' ? 31 : 33))
  child.on('exit', (code, signal) => {
    if (!stopping) {
      console.log(color(31, `\n[${label}] stopped unexpectedly (${signal || `exit code ${code}`}). Shutting down.`))
      shutdown(1)
    }
  })
  children.push(child)
  return child
}

function killTree(child, signal) {
  if (!child?.pid || child.exitCode !== null) return
  try {
    if (isWindows) spawn('taskkill', ['/pid', String(child.pid), '/f', '/t'], { stdio: 'ignore' })
    else process.kill(-child.pid, signal)
  } catch {
    // already gone
  }
}

function shutdown(code = 0) {
  if (stopping) return
  stopping = true
  console.log('\nStopping LumoraAI servers...')
  children.forEach((c) => killTree(c, 'SIGTERM'))
  // Anything that ignores SIGTERM is force-stopped after 3 seconds
  setTimeout(() => {
    children.forEach((c) => killTree(c, 'SIGKILL'))
    console.log('Stopped.')
    process.exit(code)
  }, 3000).unref()
  Promise.all(children.map((c) => (c.exitCode !== null ? null : new Promise((r) => c.once('exit', r))))).then(() => {
    console.log('Stopped.')
    process.exit(code)
  })
}

async function waitForBackend(url, attempts = 60) {
  for (let i = 0; i < attempts; i++) {
    try {
      if ((await fetch(url)).ok) return true
    } catch {
      // still starting
    }
    await new Promise((r) => setTimeout(r, 500))
  }
  return false
}

async function main() {
  const busy = [(await portInUse(8000)) && 8000, (await portInUse(3000)) && 3000].filter(Boolean)
  if (busy.length) {
    if (process.argv.includes('--restart')) {
      await stopDevServers()
    } else {
      const which = busy.length > 1 ? `Ports ${busy.join(' and ')} are` : `Port ${busy[0]} is`
      console.log(color(33, `${which} already in use: an earlier LumoraAI server is still running.`))
      console.log(`Stop it with ${color(36, 'npm run stop')} and then run ${color(36, 'npm run dev:all')} again`)
      console.log(`(or use ${color(36, 'npm run dev:restart')} to do both).`)
      process.exit(1)
    }
  }

  console.log('====================================================')
  console.log('   Starting LumoraAI: FastAPI (:8000) + Next.js (:3000)')
  console.log('   Press Ctrl+C to stop both.')
  console.log('====================================================\n')

  // Reload only on backend code changes (not node_modules, .next or uploaded files)
  run('FastAPI', 34, pythonCmd, [
    '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000',
    '--reload', '--reload-dir', 'backend/app',
  ])

  console.log(color(36, '[Startup]') + ' Waiting for FastAPI...')
  const healthy = await waitForBackend('http://127.0.0.1:8000/api/v1/health')
  console.log(
    color(36, '[Startup]') + (healthy ? ' FastAPI is ready on :8000.' : ' FastAPI is still starting; launching Next.js anyway.'),
  )
  if (stopping) return
  run('Next.js', 32, nextBin, ['dev', '-p', '3000'])
}

process.on('SIGINT', () => shutdown(0))
process.on('SIGTERM', () => shutdown(0))
process.on('SIGHUP', () => shutdown(0))

main()
