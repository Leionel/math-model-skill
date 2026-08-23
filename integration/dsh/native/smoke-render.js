// smoke-render.js — render-path smoke test for checkpoint.client.js without a browser.
// Stubs React (mini hooks + createElement) and host.call with fixture-derived data,
// then walks the render tree to catch runtime errors and assert key content.
// Usage: node smoke-render.js
const fs = require('node:fs')
const path = require('node:path')

// ── mini React (instance-aware: runs effects, re-renders to land async state) ─
let currentInst = null
function useState(initial) {
  const i = currentInst.idx++
  if (currentInst.hooks[i] === undefined) currentInst.hooks[i] = { value: initial }
  const cell = currentInst.hooks[i]
  return [cell.value, (next) => { cell.value = typeof next === 'function' ? next(cell.value) : next }]
}
function useCallback(fn) { const i = currentInst.idx++; currentInst.hooks[i] = currentInst.hooks[i] || { fn }; return currentInst.hooks[i].fn }
function useEffect(fn) { currentInst.effects.push(fn) }
function createElement(type, props, ...children) {
  return { type, props: { ...(props || {}), children: children.length === 1 ? children[0] : children } }
}
const Fragment = Symbol('Fragment')
global.React = { createElement, useState, useCallback, useEffect, Fragment }
global.window = { setInterval: () => 1, clearInterval: () => {}, matchMedia: () => ({ matches: true }) }

// Synchronous promise-lite: .then fires immediately, so state lands before the
// next render pass.
const syncThen = (value) => ({ then: (cb) => { cb(value); return { catch: () => {} } } })

// ── canned host responses (mirror the v2 fixture status + seeded registry) ──
let progressMode = 'ok' // 'ok' | 'no-root' | 'error'
let evidenceMode = 'ok' // 'ok' | 'missing'
global.host = {
  call: (name) => {
    if (name === 'mm-progress') {
      if (progressMode === 'no-root') return syncThen({ ok: false, reason: 'no project root: pass project_root or run a checkpoint/freeze first' })
      if (progressMode === 'error') return syncThen({ ok: false, reason: 'status view failed: [WinError 267]' })
      return syncThen({
        ok: true, project_root: 'D:/contest/2026-demo', preset: 'research',
        first_blocked_gate: 'm1', next_action: 'produce the missing evidence for M1 and rerun `harness check M1`',
        gates: {
          m1: { stage: '题意/调研', status: 'blocked', ok: false, errors: ['missing model_contract'], warnings: [], evidence_keys: ['capabilities', 'checkers', 'manifest', 'profile'], human_doc: { path: '01_RESEARCH_NOTES.md', exists: true } },
          p1: { stage: '模型选型', status: 'blocked', ok: false, errors: [], warnings: [], evidence_keys: [], human_doc: { path: '02_MODEL_DECISION.md', exists: true } },
          p2: { stage: '模型求解', status: 'blocked', ok: false, errors: [], warnings: [], evidence_keys: [], human_doc: { path: '03_SOLUTION_REPORT.md', exists: false } },
          w1: { stage: '论文', status: 'blocked', ok: false, errors: [], warnings: [], evidence_keys: [], human_doc: { path: 'paper/00_PAPER_PLAN.md', exists: false } },
          w2: { stage: '审查', status: 'blocked', ok: false, errors: [], warnings: [], evidence_keys: [], human_doc: null },
          s1: { stage: '提交', status: 'blocked', ok: false, errors: [], warnings: [], evidence_keys: [], human_doc: null },
        },
        pending_checkpoints: [{ stage: 'm1', decision: null, scope: null, checkpoint_id: null }],
        stale_artifacts: [],
        receipts: { count: 3, successful_stages: ['model'], failed_receipt_ids: [] },
        review: { verdicts: {}, blocker: 0, high: 0, next_finding: null, requires_l1_review: false },
        pending_checkpoints_count: 1, stale_artifacts_count: 0,
      })
    }
    if (name === 'mm-evidence') {
      if (evidenceMode === 'missing') return syncThen({ ok: false, reason: 'evidence_registry.json is missing in this project' })
      return syncThen({
        ok: true, project_root: 'D:/contest/2026-demo', path: 'evidence_registry.json', run_id: 'demo-run',
        source_snapshots: [{ kind: 'frozen_results', path: 'frozen_results.json', sha256: 'a'.repeat(64) }],
        evidence: [
          { evidence_id: 'E-RES-1', type: 'result', verification_status: 'verified', supports: 'optimum cost is claimable from the frozen run', boundary: 'valid for the given demand scenario only', result_ids: ['R-OPT-1'], artifacts: [{ path: 'frozen_results.json', sha256: 'a'.repeat(64) }], citation: null },
          { evidence_id: 'E-CITE-1', type: 'citation', verification_status: 'pending', supports: 'literature context for the model family', boundary: 'reviewer-verified source only', result_ids: [], artifacts: [], citation: { bib_key: 'smith2026', title: 'A Study of X', source_tier: 'publisher', access_level: 'full_text' } },
          { evidence_id: 'E-REJ-1', type: 'derivation', verification_status: 'rejected', supports: 'failed derivation attempt', boundary: 'audit only', result_ids: [], artifacts: [], citation: null },
        ],
        counts: { total: 3, verified: 1, pending: 1, rejected: 1, not_applicable: 0 },
      })
    }
    return Promise.resolve({ ok: false, reason: 'unknown rpc' })
  },
}

// ── mini renderer ───────────────────────────────────────────────────────────
function renderNode(node, out = []) {
  if (node === null || node === undefined || typeof node === 'boolean') return out
  if (typeof node === 'string' || typeof node === 'number') { out.push(String(node)); return out }
  if (Array.isArray(node)) { for (const item of node) renderNode(item, out); return out }
  const { type, props } = node
  if (type === Fragment) return renderNode(props.children, out)
  if (typeof type === 'function') {
    const inst = { hooks: [], effects: [], idx: 0 }
    const prev = currentInst
    currentInst = inst
    let child
    try { child = type(props) } finally { currentInst = prev }
    for (const fn of inst.effects) { try { fn() } catch (error) {} }
    return renderNode(child, out)
  }
  if (typeof type === 'string') return renderNode(props.children, out)
  return out
}

// Top-level render with instance reuse: pass 1 renders loading state and runs
// effects (which land the async RPC data synchronously); pass 2 renders the
// settled state. Only the top-level function component reuses its instance;
// nested components (rows etc.) render fresh each pass.
let rootInst = null
function renderRoot(componentFn, passes = 2) {
  let out = []
  for (let pass = 0; pass < passes; pass += 1) {
    const inst = rootInst || { hooks: [], effects: [], idx: 0 }
    rootInst = inst
    inst.idx = 0
    inst.effects = []
    const node = componentFn()
    const prev = currentInst
    currentInst = inst
    let child
    try { child = node.type(node.props) } finally { currentInst = prev }
    for (const fn of inst.effects) { try { fn() } catch (error) {} }
    out = renderNode(child, [])
  }
  return out
}

function loadPlugin(source) {
  rootInst = null
  const plugin = new Function(source)()
  const registered = {}
  const slots = {
    inject: (name, fn) => { registered[name] = fn() },
    register: (def, component) => ({ def, component }),
  }
  plugin.apply({ slots })
  return registered
}

const src = fs.readFileSync(path.join(__dirname, 'checkpoint.client.js'), 'utf8')
let failures = 0
const check = (label, cond, extra) => {
  if (cond) console.log(`  ✓ ${label}`)
  else { failures += 1; console.error(`  ✗ ${label}${extra ? ' — ' + extra : ''}`) }
}

const dockComp = (registered) => registered['conversation.input.dock'].component
const registered = loadPlugin(src)

// 1) progress tab with full data
let text = renderRoot(dockComp(registered)).join(' ')
check('dock renders workflow eyebrow', text.includes('数模工作流'), text.slice(0, 200))
check('rail shows all six gates', ['M1', 'P1', 'P2', 'W1', 'W2', 'S1'].every((g) => text.includes(g)), text.slice(0, 300))
check('gate rows render stage labels', ['题意/调研', '模型选型', '模型求解', '论文', '审查', '提交'].every((l) => text.includes(l)))
check('first blocked highlighted', text.includes('● M1'))
check('next action line', text.includes('下一步'))
check('receipt count', text.includes('回执') && text.includes('3'))

// 1b) expanded rows reveal the per-gate detail (Human artifact / Machine status / Outstanding issues)
const srcOpen = src.replace(/React\.useState\(false\)/g, 'React.useState(true)')
text = renderRoot(dockComp(loadPlugin(srcOpen))).join(' ')
check('expanded: eyebrow labels present', ['Human artifact', 'Machine status', 'Outstanding issues'].every((l) => text.includes(l)))
check('expanded: m1 human_doc 在案', text.includes('01_RESEARCH_NOTES.md') && text.includes('在案'))
check('expanded: p2 human_doc 缺失', text.includes('03_SOLUTION_REPORT.md') && text.includes('缺失'))
check('expanded: pending checkpoint surfaced', text.includes('待人工确认'))
check('expanded: m1 error surfaced', text.includes('missing model_contract'))

// 2) evidence tab (initial tab patched to 'evidence')
const srcEvidence = src.replace("useState('progress')", "useState('evidence')")
text = renderRoot(dockComp(loadPlugin(srcEvidence))).join(' ')
check('evidence counts', text.includes('verified 1') && text.includes('pending 1') && text.includes('rejected 1'))
check('evidence rows', ['E-RES-1', 'E-CITE-1', 'E-REJ-1'].every((id) => text.includes(id)))
check('evidence supports preview', text.includes('claimable'))
// 2b) expanded evidence rows reveal citation + artifact binding
const srcEvidenceOpen = srcOpen.replace("useState('progress')", "useState('evidence')")
text = renderRoot(dockComp(loadPlugin(srcEvidenceOpen))).join(' ')
check('expanded: citation shown', text.includes('smith2026'))
check('expanded: artifact sha256 shown', text.includes('frozen_results.json') && text.includes('aaaaaaaaaaaa'))

// 3) composer card (P0)
const composer = registered['conversation.composer']
check('composer declines non-checkpoint waits', renderNode(composer.component({ matched: null })).length === 0)
const matched = {
  sessionId: 's1',
  respond: () => {}, cancel: () => {},
  payload: { questions: [{ id: 'checkpoint', detail: '主模型：XGBoost；选择原因：…', options: [{ label: '接受并进入求解' }, { label: '需修改' }], intent: { kind: 'contest-checkpoint', approve: '接受并进入求解', stage: 'model', doc: '02_MODEL_DECISION.md', digest: 'a829bc1f2e34' } }] },
}
text = renderNode(composer.component({ matched })).join(' ')
check('checkpoint card renders', text.includes('CHECKPOINT') && text.includes('阶段确认 · model'))
check('approve label present', text.includes('接受并进入求解'))
check('doc path + digest', text.includes('02_MODEL_DECISION.md') && text.includes('sha256=a829bc1f2e34'))

// 4) empty / error states
progressMode = 'no-root'
text = renderRoot(dockComp(registered)).join(' ')
check('no-root guidance shown', text.includes('尚无项目根') && text.includes('checkpoint 或 freeze'))
progressMode = 'error'
text = renderRoot(dockComp(registered)).join(' ')
check('status error surfaced', text.includes('status view failed'))
progressMode = 'ok'
evidenceMode = 'missing'
text = renderRoot(dockComp(loadPlugin(srcEvidence))).join(' ')
check('missing evidence reported', text.includes('evidence_registry.json is missing'))

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`)
process.exit(failures === 0 ? 0 : 1)
