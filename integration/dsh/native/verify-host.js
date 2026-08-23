// verify-host.js — end-to-end verification of the Phase 3 host half without Cordis.
//
// Stubs the dynamic-package ctx (subprocess service + harness globals) with the
// REAL `python` subprocess, so the mm-progress / mm-evidence projection logic
// in checkpoint.host.js is exercised against the actual harness CLI and a real
// fixture project. Exit 0 = all assertions pass.
//
// Usage: node verify-host.js <fixtureProject> [--seed-evidence]
const { spawn } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(process.argv[2])
if (!root) {
  console.error('usage: node verify-host.js <fixtureProject> [--seed-evidence]')
  process.exit(2)
}
const seedEvidence = process.argv.includes('--seed-evidence')

const handlers = new Map()
const tools = []
global.harness = {
  handle: (name, fn) => handlers.set(name, fn),
  defineTool: (def) => def,
  registerTool: (_ctx, def) => tools.push(def),
}

const subprocess = {
  async resolveExecutable(name) {
    return name === 'python' ? 'python' : null
  },
  spawn(opts) {
    const argv = opts.argv
    const cwd = opts.cwd || process.cwd()
    const maxOut = (opts.stdio && opts.stdio.stdout && opts.stdio.stdout.maxBytes) || 262144
    const maxErr = (opts.stdio && opts.stdio.stderr && opts.stdio.stderr.maxBytes) || 32768
    const env = { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', ...(opts.env || {}) }
    // Real cordis subprocess.spawn returns a handle synchronously; `done` is the promise.
    let out = ''
    let err = ''
    const handle = {
      done: null,
      collected: {
        stdout: { readFrom: () => ({ text: out }) },
        stderr: { readFrom: () => ({ text: err }) },
      },
    }
    handle.done = new Promise((resolve) => {
      const child = spawn(argv[0], argv.slice(1), { cwd, env, windowsHide: true })
      child.stdout.on('data', (d) => { if (out.length < maxOut) out += d.toString('utf8') })
      child.stderr.on('data', (d) => { if (err.length < maxErr) err += d.toString('utf8') })
      child.on('error', (e) => { err = err || String(e.message); resolve({ exitCode: 1 }) })
      child.on('close', (code) => resolve({ exitCode: code }))
    })
    return handle
  },
}

const fakeCtx = {
  get(key) {
    if (key === 'userQuestions') return { ask: async () => ({ answers: [{ selected: ['ok'] }] }) }
    return undefined
  },
  subprocess,
}
const fakeExec = {
  agent: { session: { header: { cwd: root } } },
  callId: 'verify-1',
  signal: new AbortController().signal,
}

// Load checkpoint.host.js as a Cordis package (top-level `return` → function body).
const src = fs.readFileSync(path.join(__dirname, 'checkpoint.host.js'), 'utf8')
const plugin = new Function(src)()
plugin.apply(fakeCtx)

let failures = 0
function check(label, cond, extra) {
  if (cond) {
    console.log(`  ✓ ${label}`)
  } else {
    failures += 1
    console.error(`  ✗ ${label}${extra ? ' — ' + extra : ''}`)
  }
}

async function main() {
  console.log('== mm-progress no-root guard (before any tool binds a root) ==')
  const noRoot = await handlers.get('mm-progress')({})
  check('empty args reports no project root', noRoot.ok === false && /no project root/.test(noRoot.reason || ''), noRoot.reason)

  console.log('== prime lastRoots via a real contest_checkpoint execute ==')
  const checkpointDef = tools.find((t) => t.name === 'contest_checkpoint')
  const decision = await checkpointDef.execute({
    project_root: root,
    stage: 'model',
    human_doc: '02_MODEL_DECISION.md',
    summary: 'fixture decision',
  }, fakeExec)
  check('checkpoint execute binds root + returns decision', decision && decision.approved === false, JSON.stringify(decision))

  console.log('== mm-progress (real harness status --json) ==')
  const progress = await handlers.get('mm-progress')({ project_root: root })
  check('ok=true', progress.ok === true, JSON.stringify(progress).slice(0, 400))
  check('gates cover all six', ['m1', 'p1', 'p2', 'w1', 'w2', 's1'].every((g) => progress.gates && progress.gates[g]), Object.keys(progress.gates || {}).join(','))
  check('m1 status is blocked on fresh project', progress.gates.m1.status === 'blocked', progress.gates.m1.status)
  check('first_blocked_gate = m1', progress.first_blocked_gate === 'm1', progress.first_blocked_gate)
  check('m1 human_doc mapped', progress.gates.m1.human_doc && progress.gates.m1.human_doc.path === '01_RESEARCH_NOTES.md')
  check('m1 human_doc exists in fixture', progress.gates.m1.human_doc.exists === true)
  check('p1 human_doc exists in fixture', progress.gates.p1.human_doc && progress.gates.p1.human_doc.exists === true)
  check('w2 human_doc is null (no fixed template)', progress.gates.w2.human_doc === null)
  check('pending_checkpoints_count > 0', progress.pending_checkpoints_count > 0, String(progress.pending_checkpoints_count))
  check('next_action present', typeof progress.next_action === 'string' && progress.next_action.length > 0)
  check('receipts summary present', progress.receipts && typeof progress.receipts.count === 'number')

  console.log('== mm-progress unvalidated root rejected ==')
  const rejected = await handlers.get('mm-progress')({ project_root: 'C:/Windows/System32' })
  check('unvalidated project_root rejected', rejected.ok === false && /rejected/.test(rejected.reason || ''), rejected.reason)

  if (seedEvidence) {
    console.log('== mm-evidence (real evidence_registry.json) ==')
    const evidence = await handlers.get('mm-evidence')({ project_root: root })
    check('ok=true', evidence.ok === true, JSON.stringify(evidence).slice(0, 400))
    check('counts.total matches rows', evidence.counts.total === evidence.evidence.length)
    check('verified count >= 1', evidence.counts.verified >= 1, String(evidence.counts.verified))
    const row = evidence.evidence.find((e) => e.evidence_id === 'E-RES-1')
    check('E-RES-1 present', Boolean(row), JSON.stringify(evidence.evidence.map((e) => e.evidence_id)))
    check('E-RES-1 carries artifact binding', row && row.artifacts && row.artifacts.length > 0 && row.artifacts[0].sha256)
    check('supports/boundary carried', row && row.supports && row.boundary)
  } else {
    console.log('== mm-evidence (missing file) ==')
    const missing = await handlers.get('mm-evidence')({ project_root: root })
    check('missing registry reported', missing.ok === false && /missing/.test(missing.reason || ''), missing.reason)
  }

  console.log('== tools registered ==')
  check('contest_checkpoint registered', tools.some((t) => t.name === 'contest_checkpoint'))
  check('harness_freeze_results registered (consolidated)', tools.some((t) => t.name === 'harness_freeze_results'))

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`)
  process.exit(failures === 0 ? 0 : 1)
}

main().catch((e) => {
  console.error('verify-host crashed:', e)
  process.exit(1)
})
