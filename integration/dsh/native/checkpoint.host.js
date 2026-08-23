// contest_checkpoint + mm-progress + mm-evidence — Phase 3 host half (dynamic Cordis).
// Validated in-session as plugin mmchk-4/pkg-5; see ../native/README.md.
//
// contest_checkpoint binds a human decision to the hashed projection document:
// primary = human reasoning summary, secondary = machine evidence line. The
// question carries a contest-checkpoint presentation intent; the companion
// client half (checkpoint.client.js) renders the dedicated decision card.
//
// mm-progress projects the full v2 status view (per-gate machine status plus
// human-artifact existence) that backs the Phase 3 progress panel; mm-evidence
// projects evidence_registry.json for the Evidence panel. Both are read-only
// projections of CLI truth — the host never computes a verdict.
return {
  inject: ['subprocess'],
  apply(ctx) {
    const subprocess = ctx.subprocess
    const userQuestions = ctx.get('userQuestions')
    if (userQuestions === undefined) throw new Error('userQuestions service unavailable')
    const HARNESS_CLI = 'D:/Projects/随便做做/math-modeling-skill-sion/scripts/harness.py'
    const policy = ctx.get('sandboxPolicy')
    const lastRoots = new Map()

    const STAGE_OPTIONS = {
      research: ['完成调研，进入模型选型', '继续调研'],
      model: ['接受并进入求解', '需修改', '继续调研'],
      solve: ['接受求解结果，进入论文', '需修改', '重新计算'],
      paper: ['论文初稿完成，进入审查', '需修改'],
      review: ['修订完成，进入提交准备', '需修改'],
      submit: ['确认提交清单', '需修改'],
    }
    const STAGES = Object.keys(STAGE_OPTIONS)

    // Machine gate → user-facing stage label (mirrors the client GATES list).
    const GATE_STAGES = {
      m1: '题意/调研', p1: '模型选型', p2: '模型求解',
      w1: '论文', w2: '审查', s1: '提交',
    }

    // Known human projection templates per gate (harness human_surface.py).
    // Gates without a fixed template (w2 review memo, s1 submission checklist)
    // fall back to the pending-checkpoint row in the UI.
    const GATE_HUMAN_DOCS = {
      m1: '01_RESEARCH_NOTES.md',
      p1: '02_MODEL_DECISION.md',
      p2: '03_SOLUTION_REPORT.md',
      w1: 'paper/00_PAPER_PLAN.md',
      w2: null,
      s1: null,
    }

    const normalizeTail = (p) => String(p).replace(/[\\/]+$/, '').toLowerCase()

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

    // Resolve the project root for an RPC. `harness.handle` normalizes handlers
    // as `handler(args)` only — no exec — so RPCs cannot read the session cwd.
    // The only trusted roots are those a session tool call already validated
    // (contest_checkpoint / harness_freeze_results); an explicit project_root is
    // accepted only when it matches one of them. The client never invents a
    // project_root, so this is the root the session bound via a tool call.
    function rpcRoot(args) {
      if (args && typeof args.project_root === 'string' && args.project_root.trim()) {
        const candidate = String(args.project_root).trim()
        const known = [...lastRoots.values()]
        if (known.some((root) => normalizeTail(root) === normalizeTail(candidate))) return candidate
        throw new Error(`rejected: project_root ${candidate} was not validated by a session tool call`)
      }
      if (lastRoots.size > 0) return [...lastRoots.values()][lastRoots.size - 1]
      throw new Error('no project root: pass project_root or run a checkpoint/freeze first')
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

    // Which human projection docs exist under the project root (one fs probe).
    async function humanDocExistence(root) {
      const exe = await subprocess.resolveExecutable('python')
      const code = "import json,os,sys;r=sys.argv[1];print(json.dumps({p:os.path.isfile(os.path.join(r,p)) for p in sys.argv[2:]}))"
      const rels = [...new Set(Object.values(GATE_HUMAN_DOCS).filter(Boolean))]
      const handle = subprocess.spawn({
        argv: [exe, '-c', code, root, ...rels],
        cwd: root,
        stdio: { stdin: 'ignore', stdout: { maxBytes: 16384 }, stderr: { maxBytes: 16384 } },
        graceMs: 5000,
        env: { PYTHONUTF8: '1' },
      })
      const outcome = await handle.done
      const stdout = handle.collected.stdout === undefined ? '' : handle.collected.stdout.readFrom(0).text
      if (outcome.exitCode !== 0) return {}
      try {
        const value = JSON.parse(stdout)
        return value && typeof value === 'object' ? value : {}
      } catch (error) {
        return {}
      }
    }

    function summarizeReview(review) {
      if (!review || typeof review !== 'object') return null
      const perspectives = review.perspectives && typeof review.perspectives === 'object' ? review.perspectives : {}
      const verdicts = {}
      let blocker = 0
      let high = 0
      for (const [name, view] of Object.entries(perspectives)) {
        if (!view || typeof view !== 'object') continue
        verdicts[name] = view.verdict ?? 'not_run'
        const counts = view.severity_counts && typeof view.severity_counts === 'object' ? view.severity_counts : {}
        blocker += Number(counts.blocker ?? 0)
        high += Number(counts.high ?? 0)
      }
      const nextFinding = review.next_finding && typeof review.next_finding === 'object' ? {
        finding_id: review.next_finding.finding_id ?? null,
        summary: review.next_finding.summary ?? '',
      } : null
      return { verdicts, blocker, high, next_finding: nextFinding, requires_l1_review: Boolean(review.requires_l1_review) }
    }

    function projectStatus(report, exists, root) {
      const gateReports = report.gates && typeof report.gates === 'object' ? report.gates : {}
      const gates = {}
      for (const gate of Object.keys(GATE_STAGES)) {
        const raw = gateReports[gate]
        const docRel = GATE_HUMAN_DOCS[gate]
        gates[gate] = {
          stage: GATE_STAGES[gate],
          status: raw && typeof raw === 'object' ? String(raw.status ?? 'unknown') : String(raw ?? 'unknown'),
          ok: raw && typeof raw === 'object' ? Boolean(raw.ok) : raw === 'pass',
          errors: raw && Array.isArray(raw.errors) ? raw.errors : [],
          warnings: raw && Array.isArray(raw.warnings) ? raw.warnings : [],
          evidence_keys: raw && Array.isArray(raw.evidence_keys) ? raw.evidence_keys : [],
          human_doc: docRel ? { path: docRel, exists: Boolean(exists[docRel]) } : null,
        }
      }
      const pending = Array.isArray(report.pending_human_checkpoints)
        ? report.pending_human_checkpoints.map((row) => ({
            stage: row && typeof row === 'object' ? (row.stage ?? null) : null,
            decision: row && typeof row === 'object' ? (row.decision ?? null) : null,
            scope: row && typeof row === 'object' ? (row.scope ?? null) : null,
            checkpoint_id: row && typeof row === 'object' ? (row.checkpoint_id ?? null) : null,
          }))
        : []
      const stale = Array.isArray(report.stale_artifacts) ? report.stale_artifacts.map((row) => ({
        artifact_id: row && typeof row === 'object' ? (row.artifact_id ?? null) : null,
        path: row && typeof row === 'object' ? (row.path ?? null) : null,
        reason: row && typeof row === 'object' ? (row.reason ?? null) : null,
      })) : []
      const receipts = report.receipts && typeof report.receipts === 'object' ? {
        count: report.receipts.count ?? 0,
        successful_stages: Array.isArray(report.receipts.successful_stages) ? report.receipts.successful_stages : [],
        failed_receipt_ids: Array.isArray(report.receipts.failed_receipt_ids) ? report.receipts.failed_receipt_ids : [],
      } : null
      return {
        ok: true,
        project_root: root,
        preset: typeof report.preset === 'string' ? report.preset : null,
        first_blocked_gate: typeof report.first_blocked_gate === 'string' ? report.first_blocked_gate : null,
        next_action: typeof report.next_action === 'string' ? report.next_action : null,
        gates,
        pending_checkpoints: pending,
        stale_artifacts: stale,
        receipts,
        review: summarizeReview(report.review),
        generated_at: typeof report.generated_at === 'string' ? report.generated_at : null,
        // Compact counts keep the lightweight strip contract stable.
        pending_checkpoints_count: pending.length,
        stale_artifacts_count: stale.length,
      }
    }

    // Package-private Client→Host RPC backing the progress panel (mm-progress).
    harness.handle('mm-progress', async (args) => {
      let root
      try {
        root = rpcRoot(args)
      } catch (error) {
        return { ok: false, reason: String(error.message ?? error) }
      }
      const exe = await subprocess.resolveExecutable('python')
      const handle = subprocess.spawn({
        argv: [exe, HARNESS_CLI, 'status', '--project', root, '--json'],
        cwd: root,
        stdio: { stdin: 'ignore', stdout: { maxBytes: 262144 }, stderr: { maxBytes: 32768 } },
        graceMs: 8000,
        env: { PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
      })
      const outcome = await handle.done
      const stdout = handle.collected.stdout === undefined ? '' : handle.collected.stdout.readFrom(0).text
      let report
      try {
        report = JSON.parse(stdout)
      } catch (error) {
        return { ok: false, reason: `status output is not JSON (exit ${outcome.exitCode})` }
      }
      if (report && report.ok === false) {
        return { ok: false, reason: `status view failed: ${(report.errors || []).join('; ') || 'unknown error'}`, errors: report.errors ?? [] }
      }
      const exists = await humanDocExistence(root)
      return projectStatus(report, exists, root)
    })

    // Package-private Client→Host RPC backing the Evidence panel (mm-evidence).
    harness.handle('mm-evidence', async (args) => {
      let root
      try {
        root = rpcRoot(args)
      } catch (error) {
        return { ok: false, reason: String(error.message ?? error) }
      }
      const exe = await subprocess.resolveExecutable('python')
      const code = "import json,os,sys;r=sys.argv[1];p=os.path.join(r,'evidence_registry.json');print(open(p,encoding='utf-8').read() if os.path.isfile(p) else '')"
      const handle = subprocess.spawn({
        argv: [exe, '-c', code, root],
        cwd: root,
        stdio: { stdin: 'ignore', stdout: { maxBytes: 262144 }, stderr: { maxBytes: 32768 } },
        graceMs: 6000,
        env: { PYTHONUTF8: '1' },
      })
      const outcome = await handle.done
      const stdout = handle.collected.stdout === undefined ? '' : handle.collected.stdout.readFrom(0).text
      if (outcome.exitCode !== 0) return { ok: false, reason: `cannot read evidence_registry: ${(handle.collected.stderr?.readFrom(0).text || '').trim()}` }
      if (!stdout.trim()) return { ok: false, reason: 'evidence_registry.json is missing in this project' }
      let registry
      try {
        registry = JSON.parse(stdout)
      } catch (error) {
        return { ok: false, reason: 'evidence_registry.json is not valid JSON' }
      }
      const rows = Array.isArray(registry.evidence) ? registry.evidence : []
      const evidence = rows.map((row) => {
        const artifacts = Array.isArray(row.artifacts) ? row.artifacts.map((item) => ({
          path: item && typeof item === 'object' ? (item.path ?? null) : null,
          sha256: item && typeof item === 'object' ? (item.sha256 ?? null) : null,
        })) : []
        const citation = row.citation && typeof row.citation === 'object' ? {
          bib_key: row.citation.bib_key ?? null,
          title: row.citation.title ?? null,
          source_tier: row.citation.source_tier ?? null,
          access_level: row.citation.access_level ?? null,
          canonical_url: row.citation.canonical_url ?? null,
        } : null
        return {
          evidence_id: row.evidence_id ?? null,
          type: row.type ?? null,
          verification_status: row.verification_status ?? 'unknown',
          supports: row.supports ?? null,
          boundary: row.boundary ?? null,
          result_ids: Array.isArray(row.result_ids) ? row.result_ids : [],
          artifacts,
          citation,
        }
      })
      const counts = { total: evidence.length }
      for (const status of ['verified', 'pending', 'rejected', 'not_applicable']) {
        counts[status] = evidence.filter((row) => row.verification_status === status).length
      }
      return {
        ok: true,
        project_root: root,
        path: 'evidence_registry.json',
        run_id: typeof registry.run_id === 'string' ? registry.run_id : null,
        source_snapshots: Array.isArray(registry.source_snapshots) ? registry.source_snapshots.map((item) => ({
          kind: item && typeof item === 'object' ? (item.kind ?? null) : null,
          path: item && typeof item === 'object' ? (item.path ?? null) : null,
          sha256: item && typeof item === 'object' ? (item.sha256 ?? null) : null,
        })) : [],
        evidence,
        counts,
      }
    })

    harness.registerTool(ctx, harness.defineTool({
      name: 'contest_checkpoint',
      description: [
        'Present one math-modeling human checkpoint confirmation card: the human reasoning projection document is primary, machine evidence stays secondary.',
        'Binds the decision to the current artifact (document path plus its SHA-256), asks through the standard question flow with a dedicated presentation intent, and returns a structured decision record.',
        'The answer encoding is identical to ask_user_question; approval semantics come from option labels, never their order.',
      ].join(' '),
      parameters: {
        project_root: { type: 'string', required: true, description: 'Absolute path of the contest project root; must be inside this session workspace.' },
        stage: { type: 'string', required: true, enum: STAGES, description: 'Workflow axis stage this checkpoint closes.' },
        human_doc: { type: 'string', required: true, description: 'Human projection document path (project-root-relative), e.g. 02_MODEL_DECISION.md.' },
        summary: { type: 'string', required: true, description: 'Short summary of the human reasoning in that document, shown as the card primary text.' },
        evidence: { type: 'string', description: 'Optional extra machine-evidence line (hash/PASS artifact id) to show under the summary.' },
        options: { type: 'array', items: { type: 'string' }, description: 'Optional custom choice labels; defaults to the stage-appropriate set.' },
        approve: { type: 'string', description: 'Which option label approves this checkpoint; defaults to the stage-appropriate accepting label. Approval semantics ride the label, never its position.' },
        question: { type: 'string', description: 'Override the default confirm question.' },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            decision: { type: 'string', required: true },
            approved: { type: 'boolean', required: true },
            note: { type: 'string' },
            checkpoint_stage: { type: 'string', required: true },
            human_doc: { type: 'string', required: true },
            doc_sha256: { type: 'string', required: true },
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
      async execute(args, exec) {
        const root = ensureInside(String(args.project_root ?? ''), sessionRoot(exec), 'project_root')
        if (!STAGES.includes(args.stage)) throw new Error(`stage must be one of ${STAGES.join('/')}`)
        const docPath = `${root.replace(/[\\/]+$/, '')}/${String(args.human_doc).replace(/^[\\/]+/, '')}`
        ensureInside(docPath, root, 'human_doc')
        const digest = await sha256(docPath, root, exec.signal)
        lastRoots.set(String(exec.callId), root)
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
      presentCall: (args) => ({
        card: 'generic',
        title: `checkpoint · ${args.stage}`,
        kind: 'read',
        locations: [{ path: args.human_doc }],
      }),
    }))

    harness.registerTool(ctx, harness.defineTool({
      name: 'harness_freeze_results',
      description: [
        'Freeze one verified result set of a math-modeling project via the repository harness CLI (`harness freeze --kind results`).',
        'The tool is an executor only: the PASS verdict comes from the deterministic validation evaluator inside the CLI, never from this tool.',
        'All relative paths are resolved against project_root by the CLI itself. Freeze refuses to overwrite an existing output file.',
        'On success the frozen document becomes a deliverable chip for this turn; on a non-zero exit the tool fails with the verifier output attached.',
      ].join(' '),
      parameters: {
        project_root: { type: 'string', required: true, description: 'Absolute path of the contest project root; must be inside this session workspace.' },
        source: { type: 'string', required: true, description: 'Raw results JSON path (project-root-relative or absolute).' },
        output: { type: 'string', required: true, description: 'Frozen results JSON path to create; must not already exist.' },
        run_id: { type: 'string', required: true, description: 'Run id that must match the model contract run_id.' },
        model_contract: { type: 'string', required: true, description: 'Model contract JSON path.' },
        code: { type: 'array', required: true, items: { type: 'string' }, description: 'Code files hashed into the freeze snapshot (at least one).' },
        validation: { type: 'array', required: true, items: { type: 'string' }, description: 'Validation report JSON paths (at least one).' },
        input: { type: 'array', items: { type: 'string' }, description: 'Optional input data files hashed into the snapshot.' },
        command: { type: 'string', description: 'Legacy free-text command metadata; compatibility only, not execution evidence.' },
      },
      output: {
        schema: {
          type: 'object',
          additionalProperties: false,
          properties: {
            ok: { type: 'boolean', required: true },
            exit_code: { required: true, oneOf: [{ type: 'integer' }, { type: 'null' }] },
            stdout: { type: 'string', required: true },
            stderr: { type: 'string', required: true },
          },
        },
        render: (_args, value) => [{ type: 'text', text: value.stdout.trim() || value.stderr.trim() || `freeze exited with ${value.exit_code}` }],
      },
      async execute(args, exec) {
        const root = ensureInside(String(args.project_root ?? ''), sessionRoot(exec), 'project_root')
        lastRoots.set(String(exec.callId), root)
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
      presentCall: (args) => ({
        card: 'generic',
        title: `freeze results → ${args.output}`,
        kind: 'edit',
        locations: [{ path: args.output }],
      }),
    }))
  },
}
