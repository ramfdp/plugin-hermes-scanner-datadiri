// Real controller and UI functions, mocked host transport. No live Hermes claim.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const path = require('node:path')
const crypto = require('node:crypto').webcrypto

function harness({ rest, storage = new Map() } = {}) {
  let scope = { id: 'runtime-A', stored: 'stored-A', profile: 'default', connection: 'local' }
  let stopped = false, time = 100000, calls = 0
  const disposers = []
  const host = { state: {
    activeSessionId: { get: () => scope.id }, focusedStoredSessionId: { get: () => scope.stored },
    profile: { get: () => scope.profile }, connectionId: { get: () => scope.connection },
  }, request: () => { throw new Error('Progress must not invoke gateway tools or model') } }
  const sdk = { host, crypto, setTimeout, clearTimeout, jsx: (type, props) => ({ type, props }),
    useState: initial => [initial, () => {}], useEffect: () => {} }
  const source = fs.readFileSync(path.join(__dirname, '../desktop/plugin.js'), 'utf8')
    .replace(/^import .*\r?\n/gm, '').replace('export default {', 'const plugin = {') +
    '\nglobalThis.api = { createProgressMonitor, progressView, sessionScope, ScannerProgressPanel, setMonitor: m => { progressMonitor = m } }'
  vm.runInNewContext(source, sdk)
  const ctx = { rest: async (...args) => { calls++; return rest?.(...args) },
    setInterval: () => () => { stopped = true }, onDispose: fn => disposers.push(fn),
    storage: { get: (key, fallback) => storage.has(key) ? structuredClone(storage.get(key)) : fallback,
      set: (key, value) => storage.set(key, JSON.parse(JSON.stringify(value))) } }
  const monitor = sdk.api.createProgressMonitor(ctx, () => time)
  sdk.api.setMonitor(monitor)
  const begin = () => {
    const job = monitor.begin('Synthetic CV.pdf', sdk.api.sessionScope())
    monitor.update(job, { localStatus: 'submitted' }); return job
  }
  return { monitor, api: sdk.api, begin, storage, ctx, change: fields => { scope = { ...scope, ...fields } },
    dispose: () => disposers.forEach(fn => fn()), stopped: () => stopped, count: () => calls,
    time: value => { time = value }, view: job => sdk.api.progressView(job, time) }
}

function frame(job, values = {}) {
  return { success: true, found: true, protocol: 'scanner-progress-v1', snapshot: {
    protocol: 'scanner-progress-v1', progress_id: job.id, sequence: 1,
    stage: 'ocr', status: 'running', worker_active: true,
    heartbeat_at: 100, updated_at: 100, pages_done: 12, pages_total: 54,
    steps_done: [], ...values } }
}
const flatten = node => !node ? [] : Array.isArray(node) ? node.flatMap(flatten) : typeof node === 'object'
  ? [node, ...flatten(node.props?.children)] : [node]

test('polls real completed-page counters without invoking the model', async () => {
  let job
  const h = harness({ rest: async (url, options) => {
    assert.equal(url, `/progress/${job.id}`); assert.equal(options.timeoutMs, 5000); return frame(job)
  } }); job = h.begin()
  await h.monitor.tick()
  assert.match(job.id, /^[a-f0-9]{32}$/)
  assert.equal(h.view(job).percent, 22)
  assert.equal(job.snapshot.pages_done, 12)
  assert.ok(flatten(h.api.ScannerProgressPanel()).some(n => n === 'Scanner Data Diri · Progres pemrosesan'))
})

test('100 percent OCR is not complete and unknown totals have no invented percentage', async () => {
  const h = harness(); const job = h.begin()
  job.snapshot = frame(job, { pages_done: 54 }).snapshot
  assert.equal(h.view(job).percent, 100)
  assert.doesNotMatch(h.view(job).message, /Dua file selesai/)
  job.snapshot.pages_total = null
  assert.equal(h.view(job).percent, null)
  job.snapshot.stage = 'web'
  assert.equal(h.view(job).percent, null)
})

test('transport failure is explicit and reconnect recovers the same job', async () => {
  let fail = true, job
  const h = harness({ rest: async () => { if (fail) throw new Error('Network'); return frame(job) } }); job = h.begin()
  await h.monitor.tick(); assert.match(h.view(job).message, /terputus/)
  fail = false; await h.monitor.tick()
  assert.equal(job.transportError, null); assert.equal(job.snapshot.pages_done, 12)
})

test('late responses never display data in another chat or profile', async () => {
  let release, job
  const h = harness({ rest: async () => { await new Promise(r => { release = r }); return frame(job) } }); job = h.begin()
  const request = h.monitor.tick()
  h.change({ profile: 'other' }); release(); await request
  assert.equal(h.monitor.current(), null); assert.equal(job.snapshot, null)
  await h.monitor.tick(); assert.equal(h.count(), 1)
})

test('polls do not overlap; dispose ignores responses and stops timer', async () => {
  let release, job
  const h = harness({ rest: async () => { await new Promise(r => { release = r }); return frame(job) } }); job = h.begin()
  const first = h.monitor.tick(); await h.monitor.tick(); assert.equal(h.count(), 1)
  h.dispose(); release(); await first
  assert.equal(h.stopped(), true); assert.equal(job.snapshot, null)
})

test('sequence regression and foreign tracking IDs cannot replace current counters', async () => {
  let answer, job
  const h = harness({ rest: async () => answer }); job = h.begin()
  answer = frame(job, { sequence: 5 }); await h.monitor.tick()
  answer = frame(job, { sequence: 4, pages_done: 1 }); await h.monitor.tick()
  assert.equal(job.snapshot.pages_done, 12)
  answer = frame(job, { sequence: 6, progress_id: 'f'.repeat(32) }); await h.monitor.tick()
  assert.equal(job.snapshot.sequence, 5); assert.match(h.view(job).message, /terputus/)
})

test('missing backend snapshots remain waiting, not a false success', async () => {
  const h = harness({ rest: async () => ({ success: true, found: false, protocol: 'scanner-progress-v1' }) })
  const job = h.begin(); await h.monitor.tick(); h.time(150000)
  assert.equal(job.snapshot, null); assert.match(h.view(job).message, /Belum ada pembaruan/)
})

test('stale worker heartbeat is different from an HTTP connection failure', async () => {
  let job
  const h = harness({ rest: async () => frame(job) }); job = h.begin()
  await h.monitor.tick(); h.time(130000)
  assert.equal(job.transportError, null); assert.match(h.view(job).message, /Worker tidak memperbarui/)
})

test('partial export or error is never displayed as two-file completion', async () => {
  const h = harness(); const job = h.begin()
  job.snapshot = frame(job, { status: 'partial', stage: 'reports', worker_active: false, artifact_count: 1 }).snapshot
  assert.match(h.view(job).message, /belum lengkap/)
  job.snapshot.status = 'error'; assert.match(h.view(job).message, /gagal/)
})

test('completed export requires two artifacts and freezes elapsed time', async () => {
  let answer, job
  const h = harness({ rest: async () => answer }); job = h.begin()
  answer = frame(job, { status: 'complete', stage: 'complete', artifact_count: 1 })
  await h.monitor.tick(); assert.equal(job.snapshot, null)
  answer = frame(job, { status: 'complete', stage: 'complete', artifact_count: 2, updated_at: 110 })
  await h.monitor.tick(); h.time(150000)
  assert.equal(h.view(job).elapsed, '00:10')
  assert.match(h.view(job).message, /Dua file selesai/)
  await h.monitor.tick(); assert.equal(h.count(), 2)
})

test('reload restores the session binding but re-reads completion from the backend', async () => {
  const h = harness(); const job = h.begin(); h.dispose()
  const next = harness({ storage: h.storage, rest: async () => frame(job) })
  assert.equal(next.monitor.current().id, job.id)
  assert.equal(next.monitor.current().snapshot, null)
  await next.monitor.tick(); assert.equal(next.monitor.current().snapshot.pages_done, 12)
  next.change({ id: 'different', stored: 'different' }); assert.equal(next.monitor.current(), null)
})

test('panel is a chat composer contribution, not part of the closed upload dialog', () => {
  const text = fs.readFileSync(path.join(__dirname, '../desktop/plugin.js'), 'utf8')
  assert.match(text, /id: 'scanner-progress', area: COMPOSER_AREAS.top/)
  assert.match(text, /PDF siap diproses/)
  assert.match(text, /progress_id: monitorJob.id/)
})
