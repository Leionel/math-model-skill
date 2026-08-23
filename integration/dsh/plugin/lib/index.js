// mm-phase3 — static host plugin (restart-persistent) for the math-modeling
// harness. Registers the two Phase 3 tools through the host-plane tools
// service (`ctx.tools.register`), which survives DSH restarts, unlike the
// dynamic sandbox (`harness.*` is only handed into dynamic packages).
//
// Hybrid split (2026-08-23): tools live here; the Phase 3 panels
// (progress / Evidence) live in ../native/checkpoint.client.js as a dynamic
// package because their client↔host RPC channel (host.call ↔ harness.handle)
// exists only inside the dynamic sandbox — the static api-remotes gateway
// fixes its capability set at build time, so a static panel RPC would require
// editing shipped DSH code (against the plan's "no shipped-file changes" rule).
//
// Zero runtime dependencies: definitions are hand-built canonical
// ToolDefinitions (JSON-Schema `required` arrays), so the profile install
// needs no registry fetch.
//
// Safety contract (unchanged from the dynamic version):
// - project_root / human_doc must sit inside exec.agent.session.header.cwd;
// - tools are executors only: PASS verdicts come from the harness CLI
//   evaluator, never from here;
// - failed calls throw (isError) and produce no Deliverables chip.
export const name = 'mm-phase3'
export const inject = ['subprocess']

const HARNESS_CLI = 'D:/Projects/随便做做/math-modeling-skill-sion/scripts/harness.py'

const STAGE_OPTIONS = {
  research: ['完成调研，进入模型选型', '继续调研'],
  model: ['接受并进入求解', '需修改', '继续调研'],
  solve: ['接受求解结果，进入论文', '需修改', '重新计算'],
  paper: ['论文初稿完成，进入审查', '需修改'],
  review: ['修订完成，进入提交准备', '需修改'],
  submit: ['确认提交清单', '需修改'],
}
const STAGES = Object.keys(STAGE_OPTIONS)

const normalizeTail = (p) => String(p).replace(/[\\/]+$/, '').toLowerCase()

export function apply(ctx) {
  const subprocess = ctx.subprocess
  const userQuestions = ctx.get('userQuestions')
  if (userQuestions === undefined) throw new Error('userQuestions service unavailable')
  const policy = ctx.get('sandboxPolicy')

  function sessionRoot(exec) {
    const headerCwd = exec.agent === undefined || exec.agent === null ? undefined : exec.agent.session.header.cwd
    if (typeof headerCwd === 'string' && headerCwd.length > 0) return headerCwd
    return policy === undefined ? undefined : policy.workspaceRoot
  }

  function ensureInside(raw, base, label) {
    const candidate = String(raw ?? '').trim()
    if (!candidate || base === undefined) throw new Error(`${label} is required`)
    const c = normalizeTail(candidate)
    const w = normalizeTail(base)
    if (c !== w && !c.startsWith(w + '/') && !c.startsWith(w + '\\')) {
      throw new Error(`rejected: ${label} ${candidate} is outside this session workspace ${base}`)
    }
    return candidate
  }

  async function sha256(path, cwd, signal) {
    const exe = await subprocess.resolveExecutable('python')
    const handle = subprocess.spawn({
      argv: [exe, '-c', "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())", path],
      cwd,
      stdio: { stdin: 'ignore', stdout: { maxBytes: 8192 }, stderr: { maxBytes: 8192 } },
      graceMs: 3000,
      signal,
      env: { PYTHONUTF8: '1' },
    })
    const outcome = await handle.done
    if (outcome.exitCode !== 0) throw new Error(`cannot hash ${path}: ${(handle.collected.stderr?.readFrom(0).text || '').trim()}`)
    return handle.collected.stdout.readFrom(0).text.trim()
  }

  ctx.tools.register({
    name: 'contest_checkpoint',
    description: [
      'Present one math-modeling human checkpoint confirmation card: the human reasoning projection document is primary, machine evidence stays secondary.',
      'Binds the decision to the current artifact (document path plus its SHA-256), asks through the standard question flow with a dedicated presentation intent, and returns a structured decision record.',
      'The answer encoding is identical to ask_user_question; approval semantics come from option labels, never their order.',
    ].join(' '),
    parameters: {
      type: 'object',
      required: ['project_root', 'stage', 'human_doc', 'summary'],
      properties: {
        project_root: { type: 'string', description: 'Absolute path of the contest project root; must be inside this session workspace.' },
        stage: { type: 'string', enum: STAGES, description: 'Workflow axis stage this checkpoint closes.' },
        human_doc: { type: 'string', description: 'Human projection document path (project-root-relative), e.g. 02_MODEL_DECISION.md.' },
        summary: { type: 'string', description: 'Short summary of the human reasoning in that document, shown as the card primary text.' },
        evidence: { type: 'string', description: 'Optional extra machine-evidence line (hash/PASS artifact id) to show under the summary.' },
        options: { type: 'array', items: { type: 'string' }, description: 'Optional custom choice labels; defaults to the stage-appropriate set.' },
        approve: { type: 'string', description: 'Which option label approves this checkpoint; defaults to the stage-appropriate accepting label. Approval semantics ride the label, never its position.' },
        question: { type: 'string', description: 'Override the default confirm question.' },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['decision', 'approved', 'checkpoint_stage', 'human_doc', 'doc_sha256'],
        properties: {
          decision: { type: 'string' },
          approved: { type: 'boolean' },
          note: { type: 'string' },
          checkpoint_stage: { type: 'string' },
          human_doc: { type: 'string' },
          doc_sha256: { type: 'string' },
        },
      },
      render: (_args, value) => [{
        type: 'text',
        text: [
          `checkpoint[${value.checkpoint_stage}] decision: ${value.decision} (${value.approved ? 'approved' : 'not approved'})${value.note ? ` · note: ${value.note}` : ''}`,
          `artifact: ${value.human_doc} sha256=${value.doc_sha256.slice(0, 12)}`,
        ].join('\n'),
      }],
    },
    presentCall: (args) => ({
      card: 'generic',
      title: `checkpoint · ${args.stage}`,
      kind: 'read',
      locations: [{ path: args.human_doc }],
    }),
    async execute(args, exec) {
      const root = ensureInside(String(args.project_root ?? ''), sessionRoot(exec), 'project_root')
      if (!STAGES.includes(args.stage)) throw new Error(`stage must be one of ${STAGES.join('/')}`)
      const docPath = `${root.replace(/[\\/]+$/, '')}/${String(args.human_doc).replace(/^[\\/]+/, '')}`
      ensureInside(docPath, root, 'human_doc')
      const digest = await sha256(docPath, root, exec.signal)
      const labels = Array.isArray(args.options) && args.options.length > 0 ? args.options.map(String) : [...STAGE_OPTIONS[args.stage]]
      const approve = String(args.approve ?? STAGE_OPTIONS[args.stage][0])
      if (!labels.includes(approve)) throw new Error(`approve label ${approve} is not among options [${labels.join(', ')}]`)
      const answer = await userQuestions.ask({
        questions: [{
          id: 'checkpoint',
          header: `Checkpoint · ${args.stage}`,
          question: String(args.question ?? '是否接受本阶段成果并继续？'),
          detail: args.summary,
          options: labels.map((label) => ({ label })),
          intent: {
            kind: 'contest-checkpoint',
            approve,
            stage: args.stage,
            doc: String(args.human_doc),
            digest: digest.slice(0, 12),
            ...(args.evidence !== undefined ? { evidence: String(args.evidence) } : {}),
          },
        }],
        agent: exec.agent,
        signal: exec.signal,
      })
      const row = answer.answers[0]
      const decision = row.selected[0] ?? '(empty)'
      return {
        decision,
        approved: decision === approve,
        ...(row.custom !== undefined && row.custom !== null && row.custom !== '' ? { note: String(row.custom) } : {}),
        checkpoint_stage: args.stage,
        human_doc: String(args.human_doc),
        doc_sha256: digest,
      }
    },
  })

  ctx.tools.register({
    name: 'harness_freeze_results',
    description: [
      'Freeze one verified result set of a math-modeling project via the repository harness CLI (`harness freeze --kind results`).',
      'The tool is an executor only: the PASS verdict comes from the deterministic validation evaluator inside the CLI, never from this tool.',
      'All relative paths are resolved against project_root by the CLI itself. Freeze refuses to overwrite an existing output file.',
      'On success the frozen document becomes a deliverable chip for this turn; on a non-zero exit the tool fails with the verifier output attached.',
    ].join(' '),
    parameters: {
      type: 'object',
      required: ['project_root', 'source', 'output', 'run_id', 'model_contract', 'code', 'validation'],
      properties: {
        project_root: { type: 'string', description: 'Absolute path of the contest project root; must be inside this session workspace.' },
        source: { type: 'string', description: 'Raw results JSON path (project-root-relative or absolute).' },
        output: { type: 'string', description: 'Frozen results JSON path to create; must not already exist.' },
        run_id: { type: 'string', description: 'Run id that must match the model contract run_id.' },
        model_contract: { type: 'string', description: 'Model contract JSON path.' },
        code: { type: 'array', items: { type: 'string' }, description: 'Code files hashed into the freeze snapshot (at least one).' },
        validation: { type: 'array', items: { type: 'string' }, description: 'Validation report JSON paths (at least one).' },
        input: { type: 'array', items: { type: 'string' }, description: 'Optional input data files hashed into the snapshot.' },
        command: { type: 'string', description: 'Legacy free-text command metadata; compatibility only, not execution evidence.' },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['ok', 'exit_code', 'stdout', 'stderr'],
        properties: {
          ok: { type: 'boolean' },
          exit_code: { oneOf: [{ type: 'integer' }, { type: 'null' }] },
          stdout: { type: 'string' },
          stderr: { type: 'string' },
        },
      },
      render: (_args, value) => [{ type: 'text', text: value.stdout.trim() || value.stderr.trim() || `freeze exited with ${value.exit_code}` }],
    },
    presentCall: (args) => ({
      card: 'generic',
      title: `freeze results → ${args.output}`,
      kind: 'edit',
      locations: [{ path: args.output }],
    }),
    async execute(args, exec) {
      const root = ensureInside(String(args.project_root ?? ''), sessionRoot(exec), 'project_root')
      const exe = await subprocess.resolveExecutable('python')
      const argv = [exe, HARNESS_CLI, 'freeze', '--kind', 'results', '--project', root,
        '--source', args.source, '--output', args.output, '--run-id', args.run_id,
        '--model-contract', args.model_contract]
      for (const item of args.code) argv.push('--code', item)
      for (const item of args.validation) argv.push('--validation', item)
      for (const item of args.input ?? []) argv.push('--input', item)
      if (args.command !== undefined) argv.push('--command', args.command)
      const handle = subprocess.spawn({
        argv,
        cwd: root,
        stdio: { stdin: 'ignore', stdout: { maxBytes: 262144 }, stderr: { maxBytes: 131072 } },
        graceMs: 5000,
        signal: exec.signal,
        env: { PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
      })
      const outcome = await handle.done
      const stdout = handle.collected.stdout === undefined ? '' : handle.collected.stdout.readFrom(0).text
      const stderr = handle.collected.stderr === undefined ? '' : handle.collected.stderr.readFrom(0).text
      const value = { ok: outcome.exitCode === 0, exit_code: outcome.exitCode, stdout, stderr }
      if (outcome.exitCode !== 0) {
        throw new Error(`harness_freeze_results failed (exit ${outcome.exitCode}):\n${(stderr || stdout).slice(-2000)}`)
      }
      return value
    },
  })
}
