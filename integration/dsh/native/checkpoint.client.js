// Checkpoint decision card + Phase 3 panels — client half (dynamic Cordis).
// Validated in-session as plugin mmchk-4/pkg-5; see ../native/README.md.
//
// Design intent (2026-08-23): a precision instrument for the contest workflow
// axis — six Gates laid out as a progression rail that lights up in sequence,
// quiet surfaces, semantic color driven by Gate truth (pass/blocked/rejected),
// monospace for artifact identity. The composer takeover (P0) and the dock
// panels (P1 progress / P2 evidence) are presentations of CLI truth only.
return {
  inject: ['slots'],
  apply(ctx) {
    const slots = ctx.slots

    // ─── design tokens ──────────────────────────────────────────────────────
    const C = {
      surface: '#14161B',        // panel base (darker than the page)
      raised: '#1B1E26',         // expanded detail / row hover
      inset: '#101218',          // inner wells
      border: 'rgba(148,163,184,0.16)',
      borderStrong: 'rgba(148,163,184,0.30)',
      text: '#E8EBF2',
      muted: '#93A0B8',
      faint: '#5C667A',
      accent: '#6FA8FF',         // workflow accent (cool blue)
      accentDim: 'rgba(111,168,255,0.14)',
      pass: '#3ECF8E',           // gate truth: pass
      passDim: 'rgba(62,207,142,0.13)',
      warn: '#F0B35C',           // blocked / missing artifact
      warnDim: 'rgba(240,179,92,0.14)',
      danger: '#F07474',         // rejected evidence
      dangerDim: 'rgba(240,116,116,0.13)',
    }
    const F = {
      ui: "'Segoe UI Variable','Segoe UI',system-ui,-apple-system,sans-serif",
      mono: "'Cascadia Mono','Cascadia Code',Consolas,'SF Mono',monospace",
    }

    // shared primitives
    const eyebrow = (color = C.muted) => ({
      fontSize: 10.5, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase',
      color, fontFamily: F.ui, lineHeight: 1.4,
    })
    const mono = (extra = {}) => ({ fontFamily: F.mono, fontSize: 12, color: C.text, ...extra })

    const GATES = [
      ['m1', '题意/调研'],
      ['p1', '模型选型'],
      ['p2', '模型求解'],
      ['w1', '论文'],
      ['w2', '审查'],
      ['s1', '提交'],
    ]

    // ─── P0: checkpoint decision card ───────────────────────────────────────

    function CheckpointComposer(props) {
      const pending = props.matched
      const frame = pending && pending.payload ? pending.payload : null
      const questions = frame && Array.isArray(frame.questions) ? frame.questions : []
      const q = questions.length === 1 ? questions[0] : null
      const intent = q && q.intent ? q.intent : null
      const [busy, setBusy] = React.useState(false)
      if (!q || !intent || intent.kind !== 'contest-checkpoint') return null
      const decide = (labels) => {
        if (busy) return
        setBusy(true)
        try {
          pending.respond({
            ok: true,
            value: {
              sessionId: pending.sessionId,
              answer: { answers: [{ id: String(q.id), selected: labels }] },
            },
          })
        } catch (error) {
          setBusy(false)
        }
      }
      const others = Array.isArray(q.options) ? q.options.map((o) => o.label).filter((l) => l !== intent.approve) : []
      return React.createElement('div', {
        style: {
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 12,
          padding: '16px 18px',
          margin: '10px auto',
          maxWidth: 680,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
          boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
          fontFamily: F.ui,
        },
      },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
        React.createElement('span', {
          style: {
            fontSize: 10.5, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase',
            color: C.accent, border: `1px solid ${C.accent}`,
            padding: '3px 9px', borderRadius: 999, background: C.accentDim,
          },
        }, 'CHECKPOINT'),
        React.createElement('span', { style: { fontSize: 15, fontWeight: 650, color: C.text, letterSpacing: '0.01em' } },
          `阶段确认 · ${intent.stage}`)),
      React.createElement('div', { style: { display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' } },
        React.createElement('span', { style: { fontSize: 12, color: C.muted } }, '人类投影文档'),
        React.createElement('span', { style: mono({ fontSize: 12.5, color: C.text }) }, intent.doc)),
      React.createElement('div', {
        style: {
          fontSize: 13.5, lineHeight: 1.6, color: C.text,
          whiteSpace: 'pre-wrap',
          padding: '12px 14px', borderRadius: 10,
          background: C.inset, border: `1px solid ${C.border}`,
        },
      }, String(q.detail ?? '')),
      React.createElement('div', { style: { fontSize: 12, color: C.faint, fontFamily: F.mono } },
        `sha256=${intent.digest}${intent.evidence ? '  ·  ' + intent.evidence : ''}`),
      React.createElement('div', { style: { display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' } },
        React.createElement('button', {
          style: {
            padding: '8px 18px', borderRadius: 9, fontSize: 13.5, fontWeight: 650, cursor: 'pointer',
            color: '#0B1220', background: C.accent, border: 'none',
            opacity: busy ? 0.55 : 1,
          },
          disabled: busy,
          onClick: () => decide([intent.approve]),
        }, intent.approve),
        others.map((label) => React.createElement('button', {
          key: label,
          style: {
            padding: '8px 16px', borderRadius: 9, fontSize: 13.5, cursor: 'pointer',
            color: C.text, background: 'transparent', border: `1px solid ${C.borderStrong}`,
            opacity: busy ? 0.55 : 1,
          },
          disabled: busy,
          onClick: () => decide([label]),
        }, label)),
        React.createElement('button', {
          style: {
            background: 'none', border: 'none', color: C.muted, cursor: 'pointer',
            fontSize: 12, textDecoration: 'underline', textUnderlineOffset: 3,
            padding: 0, marginLeft: 'auto',
          },
          disabled: busy,
          onClick: () => {
            setBusy(true)
            try { pending.cancel() } catch (error) {}
          },
        }, '先在对话里讨论，不现在决定'))
      )
    }

    slots.inject('conversation.composer', () => ctx.slots.register({
      name: 'conversation.composer',
      priority: -100,
      locale: 'mm-checkpoint',
      select: (owner) => {
        const interactions = owner && owner.interactions ? owner.interactions : []
        for (const item of interactions) {
          if (item.kind !== 'question') continue
          const qs = item.payload && Array.isArray(item.payload.questions) ? item.payload.questions : []
          if (qs.length === 1 && qs[0].intent && qs[0].intent.kind === 'contest-checkpoint') return item
        }
        return null
      },
    }, (props) => React.createElement(CheckpointComposer, props)))

    // ─── P1 + P2: Phase 3 panel dock ────────────────────────────────────────

    const reduceMotion = typeof window !== 'undefined' && window.matchMedia
      ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
      : false

    function gateState(gate) {
      if (!gate) return { tone: 'unknown', label: 'unknown' }
      if (gate.ok || gate.status === 'pass') return { tone: 'pass', label: 'PASS' }
      if (gate.status === 'blocked') return { tone: 'blocked', label: 'BLOCKED' }
      return { tone: 'pending', label: String(gate.status || 'unknown').toUpperCase() }
    }
    const toneColor = (tone) => tone === 'pass' ? C.pass : tone === 'blocked' ? C.warn : C.faint

    function RailCell({ gateKey, label, status, isFirstBlocked, connected, pulseOn }) {
      const state = gateState(status)
      const color = state.tone === 'pass' ? C.pass : isFirstBlocked ? C.warn : C.faint
      const filled = state.tone === 'pass' || isFirstBlocked
      return React.createElement('div', { style: { display: 'flex', alignItems: 'center' } },
        React.createElement('div', {
          style: {
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
            padding: '5px 10px', borderRadius: 9, minWidth: 46,
            background: filled ? (state.tone === 'pass' ? C.passDim : C.warnDim) : 'transparent',
            border: `1px solid ${filled ? color : C.border}`,
            boxShadow: isFirstBlocked && pulseOn ? `0 0 0 3px ${C.warnDim}, 0 0 14px ${C.warn}55` : 'none',
            transition: reduceMotion ? 'none' : 'box-shadow 0.4s ease, background 0.2s ease',
          },
        },
        React.createElement('span', { style: { fontSize: 12.5, fontWeight: 750, color, fontFamily: F.mono, letterSpacing: '0.04em' } },
          state.tone === 'pass' ? '✓ ' + gateKey.toUpperCase() : isFirstBlocked ? '● ' + gateKey.toUpperCase() : gateKey.toUpperCase()),
        React.createElement('span', { style: { fontSize: 10, color: C.faint, letterSpacing: '0.02em', whiteSpace: 'nowrap' } }, label)),
        connected
          ? React.createElement('div', {
            style: {
              width: 16, height: 2, margin: '0 2px', alignSelf: 'flex-start', marginTop: 14,
              background: state.tone === 'pass' ? C.pass + '88' : C.border,
            },
          })
          : null)
    }

    function GateRow({ gateKey, label, gate, firstBlocked, pendingRow, staleCount, reviewFinding }) {
      const [open, setOpen] = React.useState(false)
      const [hover, setHover] = React.useState(false)
      const state = gateState(gate)
      const color = toneColor(state.tone)
      const issues = []
      if (gate && Array.isArray(gate.errors) && gate.errors.length > 0) issues.push(...gate.errors.map((item) => `error: ${item}`))
      if (gate && Array.isArray(gate.warnings) && gate.warnings.length > 0) issues.push(...gate.warnings.map((item) => `warning: ${item}`))
      if (pendingRow) issues.push(`待人工确认${pendingRow.scope ? ' · ' + pendingRow.scope : ''}${pendingRow.decision ? ' · decision=' + pendingRow.decision : ''}`)
      if (gateKey === firstBlocked && staleCount > 0) issues.push(`陈旧产物 ${staleCount} 项`)
      if (gateKey === 'w2' && reviewFinding) issues.push(`审查意见：${reviewFinding.finding_id} ${reviewFinding.summary}`)

      const row = React.createElement('div', {
        style: {
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '9px 12px', borderRadius: 10,
          background: hover ? C.raised : 'transparent',
          border: `1px solid ${hover ? C.borderStrong : C.border}`,
          cursor: 'pointer',
          transition: reduceMotion ? 'none' : 'background 0.15s ease, border-color 0.15s ease',
        },
        onMouseEnter: () => setHover(true),
        onMouseLeave: () => setHover(false),
        onClick: () => setOpen(!open),
      },
      React.createElement('span', {
        style: {
          width: 8, height: 8, borderRadius: 999, flex: '0 0 auto',
          background: state.tone === 'pass' ? C.pass : gateKey === firstBlocked ? C.warn : C.faint,
          boxShadow: state.tone === 'pass' ? `0 0 8px ${C.pass}66` : gateKey === firstBlocked ? `0 0 8px ${C.warn}88` : 'none',
        },
      }),
      React.createElement('span', { style: { fontSize: 12, fontWeight: 750, color: C.text, fontFamily: F.mono, letterSpacing: '0.05em', width: 34 } },
        gateKey.toUpperCase()),
      React.createElement('span', { style: { fontSize: 13, fontWeight: 550, color: C.text, flex: '0 0 auto' } }, label),
      React.createElement('span', {
        style: {
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
          color, padding: '2px 8px', borderRadius: 999,
          background: state.tone === 'pass' ? C.passDim : gateKey === firstBlocked ? C.warnDim : 'transparent',
          border: `1px solid ${state.tone === 'pass' || gateKey === firstBlocked ? color : C.border}`,
          fontFamily: F.ui,
        },
      }, state.label),
      gate && Array.isArray(gate.evidence_keys) && gate.evidence_keys.length > 0
        ? React.createElement('span', {
          style: { fontSize: 11, color: C.faint, fontFamily: F.mono, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: '1 1 auto', minWidth: 0 },
        }, gate.evidence_keys.join(' · '))
        : React.createElement('span', { style: { flex: '1 1 auto' } }),
      React.createElement('span', { style: { fontSize: 11, color: C.faint, flex: '0 0 auto' } }, open ? '▲' : '▼'))

      if (!open) return row

      const humanSection = React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 4 } },
        React.createElement('span', { style: eyebrow() }, 'Human artifact'),
        gate && gate.human_doc
          ? React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' } },
            React.createElement('span', { style: mono() }, gate.human_doc.path),
            React.createElement('span', {
              style: {
                fontSize: 10.5, fontWeight: 650, letterSpacing: '0.05em',
                color: gate.human_doc.exists ? C.pass : C.warn,
                padding: '1px 7px', borderRadius: 999,
                background: gate.human_doc.exists ? C.passDim : C.warnDim,
              },
            }, gate.human_doc.exists ? '在案' : '缺失'))
          : React.createElement('span', { style: { fontSize: 12.5, color: C.muted } },
            pendingRow ? '无固定模板 · 待人工确认' : '无固定模板'))

      const machineSection = React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 6 } },
        React.createElement('span', { style: eyebrow() }, 'Machine status'),
        React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' } },
          React.createElement('span', {
            style: {
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color,
              padding: '2px 8px', borderRadius: 6, background: C.inset, border: `1px solid ${color}66`,
              fontFamily: F.mono,
            },
          }, state.label),
          React.createElement('span', { style: { fontSize: 11.5, color: C.muted, fontFamily: F.ui } },
            gate && Array.isArray(gate.evidence_keys) && gate.evidence_keys.length > 0
              ? `证据键 ${gate.evidence_keys.length} 个` : '无证据键')))

      const issuesSection = React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 5 } },
        React.createElement('span', { style: eyebrow(issues.length > 0 ? C.warn : C.faint) }, 'Outstanding issues'),
        issues.length > 0
          ? issues.map((item, index) => React.createElement('div', {
            key: index,
            style: { fontSize: 12, lineHeight: 1.55, color: C.text, paddingLeft: 14, position: 'relative' },
          },
          React.createElement('span', { style: { position: 'absolute', left: 2, top: 0, color: C.faint } }, '·'),
          item))
          : React.createElement('span', { style: { fontSize: 12.5, color: C.faint } }, '无'))

      return React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 4 } },
        row,
        React.createElement('div', {
          style: {
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))',
            gap: 10, padding: '10px 12px', borderRadius: 10,
            background: C.inset, border: `1px solid ${C.border}`,
          },
        }, humanSection, machineSection, issuesSection))
    }

    function EvidenceRow({ row }) {
      const [open, setOpen] = React.useState(false)
      const [hover, setHover] = React.useState(false)
      const status = row.verification_status
      const color = status === 'verified' ? C.pass : status === 'rejected' ? C.danger : status === 'pending' ? C.warn : C.faint
      const dim = status === 'verified' ? C.passDim : status === 'rejected' ? C.dangerDim : status === 'pending' ? C.warnDim : 'transparent'
      const glyph = status === 'verified' ? '✓' : status === 'rejected' ? '✕' : status === 'pending' ? '○' : '–'

      const head = React.createElement('div', {
        style: {
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '9px 12px', borderRadius: 10,
          background: hover ? C.raised : 'transparent',
          border: `1px solid ${hover ? C.borderStrong : C.border}`,
          cursor: 'pointer',
          transition: reduceMotion ? 'none' : 'background 0.15s ease, border-color 0.15s ease',
        },
        onMouseEnter: () => setHover(true),
        onMouseLeave: () => setHover(false),
        onClick: () => setOpen(!open),
      },
      React.createElement('span', {
        style: {
          width: 8, height: 8, borderRadius: 999, flex: '0 0 auto', background: color,
          boxShadow: status === 'verified' ? `0 0 8px ${C.pass}66` : 'none',
        },
      }),
      React.createElement('span', { style: { fontSize: 12, fontWeight: 700, color: C.text, fontFamily: F.mono, flex: '0 0 auto' } }, row.evidence_id),
      React.createElement('span', {
        style: {
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          color: C.faint, padding: '2px 8px', borderRadius: 999,
          border: `1px solid ${C.border}`, fontFamily: F.ui,
        },
      }, row.type ?? 'unknown'),
      row.supports
        ? React.createElement('span', {
          style: { fontSize: 12, color: C.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: '1 1 auto', minWidth: 0 },
        }, String(row.supports))
        : React.createElement('span', { style: { flex: '1 1 auto' } }),
      React.createElement('span', {
        style: {
          fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', color,
          padding: '2px 8px', borderRadius: 999, background: dim, border: `1px solid ${color}55`,
        },
      }, `${glyph} ${status}`),
      React.createElement('span', { style: { fontSize: 11, color: C.faint, flex: '0 0 auto' } }, open ? '▲' : '▼'))

      if (!open) return head

      const kv = (label, valueNode) => React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 3 } },
        React.createElement('span', { style: eyebrow() }, label), valueNode)

      return React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 4 } },
        head,
        React.createElement('div', {
          style: {
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: 10, padding: '10px 12px', borderRadius: 10,
            background: C.inset, border: `1px solid ${C.border}`,
          },
        },
        kv('支持', React.createElement('span', { style: { fontSize: 12, color: C.text, lineHeight: 1.5 } }, String(row.supports ?? '—'))),
        kv('边界', React.createElement('span', { style: { fontSize: 12, color: C.muted, lineHeight: 1.5 } }, String(row.boundary ?? '—'))),
        kv('结果', row.result_ids && row.result_ids.length > 0
          ? React.createElement('div', { style: { display: 'flex', gap: 5, flexWrap: 'wrap' } },
            row.result_ids.map((id) => React.createElement('span', { key: id, style: { ...mono({ fontSize: 11 }), padding: '1px 7px', borderRadius: 6, background: C.surface, border: `1px solid ${C.border}` } }, id)))
          : React.createElement('span', { style: { fontSize: 12, color: C.faint } }, '—')),
        kv('产物', row.artifacts && row.artifacts.length > 0
          ? React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 4 } },
            row.artifacts.map((item) => React.createElement('span', { key: item.path, style: mono({ fontSize: 11.5, color: C.muted }) },
              `${item.path}${item.sha256 ? ' · ' + item.sha256.slice(0, 12) : ''}`)))
          : React.createElement('span', { style: { fontSize: 12, color: C.faint } }, '—')),
        row.citation
          ? kv('引用', React.createElement('span', { style: { fontSize: 12, color: C.text, lineHeight: 1.5 } },
            `${row.citation.bib_key} · ${row.citation.title ?? ''}${row.citation.source_tier ? ' · ' + row.citation.source_tier : ''}`))
          : null))
    }

    function PanelsDock() {
      const [progress, setProgress] = React.useState(null)
      const [evidence, setEvidence] = React.useState(null)
      const [tab, setTab] = React.useState('progress')
      const [pulseOn, setPulseOn] = React.useState(false)

      const refreshProgress = React.useCallback(() => {
        host.call('mm-progress', {}).then((value) => setProgress(value)).catch(() => setProgress({ ok: false, reason: '进度源不可用' }))
      }, [])
      const refreshEvidence = React.useCallback(() => {
        host.call('mm-evidence', {}).then((value) => setEvidence(value)).catch(() => setEvidence({ ok: false, reason: '证据源不可用' }))
      }, [])
      React.useEffect(() => {
        refreshProgress()
        const timerId = window.setInterval(refreshProgress, 20000)
        return () => window.clearInterval(timerId)
      }, [refreshProgress])
      React.useEffect(() => {
        if (tab !== 'evidence') return undefined
        refreshEvidence()
        const timerId = window.setInterval(refreshEvidence, 30000)
        return () => window.clearInterval(timerId)
      }, [tab, refreshEvidence])
      React.useEffect(() => {
        if (reduceMotion) return undefined
        const timerId = window.setInterval(() => setPulseOn((v) => !v), 1100)
        return () => window.clearInterval(timerId)
      }, [])

      const ok = progress && progress.ok
      const firstBlocked = ok ? progress.first_blocked_gate : null
      const evidenceOk = evidence && evidence.ok

      const tabBtn = (key, label, active) => React.createElement('button', {
        style: {
          padding: '5px 14px', borderRadius: 8, fontSize: 12.5, cursor: 'pointer', fontFamily: F.ui,
          color: active ? C.text : C.muted,
          background: active ? C.accentDim : 'transparent',
          border: `1px solid ${active ? C.accent : 'transparent'}`,
          fontWeight: active ? 650 : 500,
          transition: reduceMotion ? 'none' : 'background 0.15s ease, color 0.15s ease',
        },
        onClick: () => setTab(key),
      }, label)

      const rail = React.createElement('div', { style: { display: 'flex', alignItems: 'flex-start', flexWrap: 'wrap', gap: 0 } },
        GATES.map((pair, index) => {
          const gate = ok && progress.gates ? progress.gates[pair[0]] : null
          return React.createElement(RailCell, {
            key: pair[0],
            gateKey: pair[0],
            label: pair[1],
            status: gate,
            isFirstBlocked: pair[0] === firstBlocked,
            connected: index < GATES.length - 1,
            pulseOn,
          })
        }))

      const statusLine = ok
        ? React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', fontSize: 12 } },
          React.createElement('span', { style: { color: C.muted } }, '阻塞',
            React.createElement('span', { style: { color: firstBlocked ? C.warn : C.pass, fontWeight: 700, fontFamily: F.mono } },
              ` ${(firstBlocked ?? '无').toUpperCase()}`)),
          React.createElement('span', { style: { color: C.muted } }, '待确认',
            React.createElement('span', { style: { color: C.text, fontWeight: 650 } }, ` ${progress.pending_checkpoints_count ?? 0}`)),
          React.createElement('span', { style: { color: C.muted } }, '陈旧',
            React.createElement('span', { style: { color: C.text, fontWeight: 650 } }, ` ${progress.stale_artifacts_count ?? 0}`)),
          React.createElement('span', { style: { color: C.muted } }, '回执',
            React.createElement('span', { style: { color: C.text, fontWeight: 650 } }, ` ${progress.receipts ? progress.receipts.count : '?'}`)),
          React.createElement('span', { style: { color: C.faint, fontFamily: F.mono, fontSize: 11.5 } }, progress.project_root))
        : null

      const progressPanel = React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 6 } },
        GATES.map((pair) => {
          const gate = ok && progress.gates ? progress.gates[pair[0]] : null
          const pendingRow = ok && Array.isArray(progress.pending_checkpoints)
            ? progress.pending_checkpoints.find((r) => r.stage === pair[0]) : null
          const staleCount = ok && Array.isArray(progress.stale_artifacts) ? progress.stale_artifacts.length : 0
          const reviewFinding = ok && progress.review ? progress.review.next_finding : null
          return React.createElement(GateRow, {
            key: pair[0],
            gateKey: pair[0],
            label: pair[1],
            gate,
            firstBlocked,
            pendingRow,
            staleCount: pair[0] === firstBlocked ? staleCount : 0,
            reviewFinding,
          })
        }),
        ok && progress.next_action
          ? React.createElement('div', {
            style: {
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '8px 12px', borderRadius: 10,
              background: C.inset, border: `1px dashed ${C.borderStrong}`,
              fontSize: 12, color: C.muted,
            },
          },
          React.createElement('span', { style: { color: C.accent, fontWeight: 700 } }, '下一步'),
          React.createElement('span', { style: { color: C.text } }, progress.next_action))
          : null)

      const evidencePanel = React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: 6 } },
        !evidenceOk
          ? React.createElement('div', {
            style: {
              padding: '14px 16px', borderRadius: 10, border: `1px dashed ${C.borderStrong}`,
              background: C.inset, fontSize: 12.5, color: C.muted, lineHeight: 1.6,
            },
          }, evidence === null ? 'Evidence 载入中…' : String(evidence.reason ?? '证据源不可用'))
          : React.createElement(React.Fragment, null,
            React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' } },
              React.createElement('span', { style: { fontSize: 12, color: C.muted } }, '共',
                React.createElement('span', { style: { color: C.text, fontWeight: 700 } }, ` ${evidence.counts.total} 条`)),
              React.createElement('span', { style: { color: C.pass, fontWeight: 650, fontSize: 12 } }, `✓ verified ${evidence.counts.verified}`),
              React.createElement('span', { style: { color: C.warn, fontWeight: 650, fontSize: 12 } }, `○ pending ${evidence.counts.pending}`),
              React.createElement('span', { style: { color: C.danger, fontWeight: 650, fontSize: 12 } }, `✕ rejected ${evidence.counts.rejected}`),
              evidence.run_id
                ? React.createElement('span', { style: { color: C.faint, fontFamily: F.mono, fontSize: 11.5 } }, `run ${evidence.run_id}`)
                : null,
              React.createElement('button', {
                style: {
                  background: 'none', border: 'none', color: C.muted, cursor: 'pointer',
                  fontSize: 11.5, textDecoration: 'underline', textUnderlineOffset: 3, padding: 0, marginLeft: 'auto',
                },
                onClick: refreshEvidence,
              }, '刷新')),
            evidence.evidence.map((row) => React.createElement(EvidenceRow, { key: row.evidence_id, row }))))

      const emptyState = !ok
        ? React.createElement('div', {
          style: {
            padding: '12px 14px', borderRadius: 10, border: `1px dashed ${C.borderStrong}`,
            background: C.inset, fontSize: 12.5, color: C.muted, lineHeight: 1.6,
          },
        }, progress === null ? '数模进度载入中…'
          : `尚无项目根 — ${String(progress.reason ?? '')}。先运行一次 checkpoint 或 freeze 以绑定项目。`)
        : null

      return React.createElement('div', {
        style: {
          display: 'flex', flexDirection: 'column', gap: 10,
          padding: '12px 14px 14px',
          background: C.surface,
          border: `1px solid ${C.border}`,
          borderRadius: 12,
          fontFamily: F.ui,
          color: C.text,
        },
      },
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' } },
        React.createElement('span', { style: eyebrow(C.accent) }, '数模工作流'),
        rail),
      React.createElement('div', { style: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' } },
        tabBtn('progress', '进度', tab === 'progress'),
        tabBtn('evidence', 'Evidence', tab === 'evidence'),
        React.createElement('span', { style: { flex: '1 1 auto' } }),
        React.createElement('button', {
          style: {
            background: 'none', border: 'none', color: C.faint, cursor: 'pointer',
            fontSize: 11.5, textDecoration: 'underline', textUnderlineOffset: 3, padding: 0,
          },
          onClick: () => { refreshProgress(); if (tab === 'evidence') refreshEvidence() },
        }, '刷新'),
        statusLine),
      emptyState,
      tab === 'progress' ? progressPanel : evidencePanel)
    }

    slots.inject('conversation.input.dock', () => ctx.slots.register({
      name: 'conversation.input.dock',
      id: 'mm-phase3-panels',
      order: 1,
    }, () => React.createElement(PanelsDock)))
  },
}
