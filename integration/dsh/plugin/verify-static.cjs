// verify-static.cjs — validate the static mm-phase3 plugin without Cordis.
// Dynamic-imports integration/dsh/plugin/lib/index.js, applies it against a
// fake ctx (subprocess stub + userQuestions stub + tools.register capture),
// then executes both tools against a real fixture project.
// Usage: node verify-static.cjs <fixtureProject>
const { spawn } = require('node:child_process')
const path = require('node:path')
const { pathToFileURL } = require('node:url')

const root = path.resolve(process.argv[2])
if (!root) {
  console.error('usage: node verify-static.js <fixtureProject>')
  process.exit(2)
}

const subprocess = {
  async resolveExecutable() { return 'python' },
  spawn(opts) {
    const argv = opts.argv
    const cwd = opts.cwd || process.cwd()
    const maxOut = (opts.stdio && opts.stdio.stdout && opts.stdio.stdout.maxBytes) || 262144
    const maxErr = (opts.stdio && opts.stdio.stderr && opts.stdio.stderr.maxBytes) || 32768
    const env = { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', ...(opts.env || {}) }
    let out = ''
    let err = ''
    const handle = { done: null, collected: { stdout: { readFrom: () => ({ text: out }) }, stderr: { readFrom: () => ({ text: err }) } } }
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

const tools = new Map()
const fakeCtx = {
  subprocess,
  get(key) {
    if (key === 'userQuestions') return { ask: async () => ({ answers: [{ selected: ['ok'] }] }) }
    return undefined
  },
  tools: { register: (def) => { tools.set(def.name, def); return () => tools.delete(def.name) } },
}

const fakeExec = {
  agent: { session: { header: { cwd: root } } },
  callId: 'static-verify-1',
  signal: new AbortController().signal,
}

let failures = 0
function check(label, cond, extra) {
  if (cond) console.log(`  ✓ ${label}`)
  else { failures += 1; console.error(`  ✗ ${label}${extra ? ' — ' + extra : ''}`) }
}

async function main() {
  const mod = await import(pathToFileURL(path.join(__dirname, 'lib', 'index.js')).href)
  check('module exports name/inject/apply', mod.name === 'mm-phase3' && Array.isArray(mod.inject) && typeof mod.apply === 'function')
  check('inject declares subprocess', mod.inject.includes('subprocess'))

  mod.apply(fakeCtx)
  check('registers exactly two tools', tools.size === 2, [...tools.keys()].join(','))
  check('contest_checkpoint registered', tools.has('contest_checkpoint'))
  check('harness_freeze_results registered', tools.has('harness_freeze_results'))

  const checkpoint = tools.get('contest_checkpoint')
  check('parameters canonical (top-level required)', Array.isArray(checkpoint.parameters.required) && checkpoint.parameters.required.includes('project_root'))
  check('output carries schema + render', checkpoint.output && checkpoint.output.schema && typeof checkpoint.output.render === 'function')
  check('presentCall declared', typeof checkpoint.presentCall === 'function')

  console.log('== contest_checkpoint execute (real sha256 + ask) ==')
  const decision = await checkpoint.execute({
    project_root: root,
    stage: 'model',
    human_doc: '02_MODEL_DECISION.md',
    summary: 'fixture decision',
  }, fakeExec)
  check('returns structured decision', decision && typeof decision.approved === 'boolean' && decision.checkpoint_stage === 'model')
  check('approved rides the label (selected ok ≠ approve 接受并进入求解)', decision.approved === false, JSON.stringify(decision))
  check('doc_sha256 bound', typeof decision.doc_sha256 === 'string' && decision.doc_sha256.length === 64)

  console.log('== contest_checkpoint rejection ==')
  let threw = null
  try {
    await checkpoint.execute({ project_root: 'C:/Windows/System32', stage: 'model', human_doc: 'x.md', summary: 'x' }, fakeExec)
  } catch (error) {
    threw = String(error.message)
  }
  check('outside workspace rejected', threw !== null && /rejected/.test(threw), threw)

  console.log('== harness_freeze_results execute (fails loudly on incomplete project) ==')
  const freeze = tools.get('harness_freeze_results')
  let freezeError = null
  try {
    await freeze.execute({
      project_root: root,
      source: 'missing.json',
      output: 'out.json',
      run_id: 'r',
      model_contract: 'missing.json',
      code: ['model.py'],
      validation: ['missing.json'],
    }, fakeExec)
  } catch (error) {
    freezeError = String(error.message)
  }
  check('freeze failure surfaces the CLI error', freezeError !== null && /failed \(exit|exit/.test(freezeError), freezeError ? freezeError.slice(0, 200) : 'no error')

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`)
  process.exit(failures === 0 ? 0 : 1)
}

main().catch((e) => {
  console.error('verify-static crashed:', e)
  process.exit(1)
})
