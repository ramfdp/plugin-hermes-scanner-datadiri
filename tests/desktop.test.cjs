// Contract tests with a mocked SDK/React host. No claim of live Electron execution.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

function harness(request, sourceTransform = value => value, mountFirst = true, options = {}) {
  let cursor = 0
  const hooks = [], calls = [], notices = [], opens = [], cleanups = []
  let session = 'initialSession' in options ? options.initialSession : 'session-1'
  let stored = options.stored ?? null, profile = 'default', connection = 'local', gateway = 'open'
  let focused = 'focused' in options ? options.focused : session
  const host = { state: { activeSessionId: { get: () => session },
    profile: { get: () => profile }, connectionId: { get: () => connection }, gateway: { get: () => gateway } },
    notify: value => notices.push(value),
    request: async (name, args) => {
      calls.push({ name, args })
      if (request) return request(name, args)
      return name === 'session.create' ? { session_id: 'new-runtime', stored_session_id: 'new-stored' } : { attached: true, path: args.path }
    },
    openSession: async (id, args) => {
      opens.push({ id, args })
      if (options.openSession) return options.openSession(id, args)
      session = 'new-runtime'; stored = id; focused = session
    } }
  if (options.unsupported) delete host.openSession
  if (options.useFocused) {
    host.state.focusedSessionId = { get: () => focused }
    host.state.focusedStoredSessionId = { get: () => stored }
  }
  const useState = initial => {
    const i = cursor++
    if (!(i in hooks)) hooks[i] = typeof initial === 'function' ? initial() : initial
    return [hooks[i], next => { hooks[i] = typeof next === 'function' ? next(hooks[i]) : next }]
  }
  const useRef = initial => { const i = cursor++; if (!(i in hooks)) hooks[i] = { current: initial }; return hooks[i] }
  const useEffect = fn => { const i = cursor++; if (!(i in hooks)) { hooks[i] = true; cleanups.push(fn()) } }
  const sdk = { host, useState, useRef, useEffect, jsx: (type, props) => ({ type, props }), setTimeout, clearTimeout,
    Dialog: 'Dialog', DialogContent: 'DialogContent', DialogHeader: 'DialogHeader', DialogTitle: 'DialogTitle', DialogDescription: 'DialogDescription',
    COMPOSER_AREAS: { actions: 'actions', middleware: 'middleware' }, window: { hermesDesktop: { getPathForFile: f => f.path } } }
  let source = sourceTransform(fs.readFileSync(path.join(__dirname, '../desktop/plugin.js'), 'utf8'))
  source = source.replace(/^import .*\r?\n/gm, '').replace('export default {', 'const plugin = {')
  source += '\nglobalThis.api = { plugin, ScannerDataDialog, scannerPrompt, localDate, sessionScope, waitForCreatedSession, singlePdfManifest, reportTitle }'
  vm.runInNewContext(source, sdk)
  const render = () => { cursor = 0; return sdk.api.ScannerDataDialog() }
  const flatten = node => !node ? [] : Array.isArray(node) ? node.flatMap(flatten) : typeof node === 'object'
    ? [node, ...flatten(node.props?.children)] : []
  function inputs() { return flatten(render()).filter(n => n.type === 'input') }
  const set = (index, value) => inputs()[index].props.onChange({ target: { value, files: value, checked: value } })
  const file = name => ({ name, path: `C:\\Docs\\${name}`, size: 100 })
  function configure(name = 'Paket CV gabungan.pdf') { set(0, [file(name)]) }
  if (mountFirst) render()
  const registrations = []
  sdk.api.plugin.register({ register: entry => registrations.push(entry) })
  const command = registrations.find(e => e.area === 'middleware').data.handler
  assert.equal(command({ text: '/scanner-data' }), null)
  render()
  return { calls, notices, opens, configure, set, file, api: sdk.api, command, render, registrations, inputs, flatten,
    changeSession: value => { session = value; focused = value }, changeStored: value => { stored = value },
    changeProfile: value => { profile = value }, changeConnection: value => { connection = value },
    changeGateway: value => { gateway = value }, host, unmount: () => cleanups.forEach(fn => fn?.()),
    start: () => flatten(render()).find(n => n.type === 'button').props.onClick() }
}

function manifest(h) {
  const line = h.calls.findLast(c => c.name === 'prompt.submit').args.text.split('\n\n')[1]
  return JSON.parse(line.slice(line.indexOf('{')))
}

test('one PDF only starts on explicit button and attaches to bound session', async () => {
  const h = harness(); h.configure(); assert.equal(h.calls.length, 0)
  await h.start()
  assert.deepEqual(h.calls.map(c => c.name), ['file.attach', 'prompt.submit'])
  for (const call of h.calls) assert.equal(call.args.session_id, 'session-1')
  const prompt = h.calls.at(-1).args.text
  assert.match(prompt, /read_document/); assert.match(prompt, /certificate_inventory/)
  assert.match(prompt, /chat_markdown/); assert.match(prompt, /XLSX dan PDF/)
  assert.match(prompt, /scanner_web_lookup/); assert.match(prompt, /save_person/)
})

test('KAK and every manual metadata field are absent and cannot block a single PDF', async () => {
  const h = harness()
  assert.equal(h.inputs().length, 1)
  assert.equal(h.inputs()[0].props.type, 'file')
  assert.equal(h.inputs()[0].props.multiple, false)
  h.configure(); await h.start()
  assert.equal(h.calls.at(-1).name, 'prompt.submit')
  const data = manifest(h)
  assert.equal(data.documents.length, 1); assert.equal(data.documents[0].kind, 'cv')
  assert.equal(data.project, 'Paket CV gabungan')
  assert.equal(data.assessment_date, h.api.localDate())
  assert.equal(data.expected_person_count, null)
  assert.equal(data.allow_web, true)
  assert.match(h.calls.at(-1).args.text, /requirements=\[\]/)
  assert.match(h.calls.at(-1).args.text, /TANPA meminta KAK/)
})

test('empty non-PDF and oversized files are rejected before session creation', async () => {
  for (const input of [[], [{ name: 'bad.exe', size: 100 }], [{ name: 'empty.pdf', size: 0 }],
    [{ name: 'large.pdf', size: 250 * 1024 * 1024 + 1 }], [{ name: 'bad.pdf', size: NaN }]]) {
    const h = harness(null, x => x, true, { initialSession: null })
    h.set(0, input); await h.start(); assert.equal(h.calls.length, 0)
  }
})

test('session changes never submit the prompt to a different chat', async () => {
  const h = harness(); h.configure(); h.changeSession('session-2')
  await h.start(); assert.equal(h.calls.length, 0)
})

test('session switch during attachment stops before prompt submission', async () => {
  let h
  h = harness(async (name, args) => { h.changeSession('session-2'); return { attached: true, path: args.path } })
  h.configure(); await h.start()
  assert.equal(h.calls.filter(c => c.name === 'prompt.submit').length, 0)
})

test('double click does not duplicate submission; failure permits retry', async () => {
  let release, blocked = true
  const h = harness(async (name, args) => {
    if (blocked) { blocked = false; await new Promise(resolve => { release = resolve }); return { attached: false, message: 'Failed' } }
    return { attached: true, path: args.path }
  })
  h.configure()
  const first = h.start(); const second = h.start(); assert.equal(h.calls.length, 1)
  release(); await Promise.all([first, second]); assert.equal(h.calls.length, 1)
  await h.start(); assert.equal(h.calls.filter(c => c.name === 'prompt.submit').length, 1)
})

test('multiple or duplicate files are rejected; explicit web opt-out remains in prompt contract', async () => {
  const h = harness(); h.set(0, [h.file('a.pdf'), h.file('a.pdf')]); await h.start()
  assert.equal(h.calls.length, 0)
  assert.match(h.api.scannerPrompt({ project: 'Test', allow_web: false, documents: [] }), /"allow_web":false/)
})

test('non-scanner drafts are preserved and prompt treats source text as untrusted', () => {
  const h = harness(); const draft = { text: 'hello' }; assert.equal(h.command(draft), draft)
  const prompt = h.api.scannerPrompt({ project: 'Test', documents: [] })
  assert.match(prompt, /tidak tepercaya/); assert.match(prompt, /CAPTCHA/)
  assert.match(prompt, /Jangan mengklaim semua valid/)
  assert.match(h.api.localDate(), /^\d{4}-\d{2}-\d{2}$/)
})

test('Windows CRLF checkout is supported by the SDK test harness', async () => {
  const h = harness(null, source => source.replace(/\r?\n/g, '\r\n'))
  h.configure(); await h.start()
  assert.equal(h.calls.filter(call => call.name === 'prompt.submit').length, 1)
})

test('slash command arriving before dialog mount is queued rather than swallowed', () => {
  const h = harness(null, value => value, false)
  assert.equal(h.render().props.open, true)
  assert.equal(h.calls.length, 0)
  assert.ok(h.notices.some(n => n.message.includes('Menyiapkan dialog')))
})

test('workflow prompt requires summary before web and prohibits ad-hoc code repair', () => {
  const h = harness()
  const prompt = h.api.scannerPrompt({ project: 'Test', documents: [] })
  assert.ok(prompt.indexOf('4. Panggil action="summary"') < prompt.indexOf('5. Setelah summary berhasil'))
  assert.match(prompt, /workflow_complete=true/)
  assert.match(prompt, /Jangan mengedit source, membuat shim ocr_runner.py/)
  assert.match(prompt, /"workflow_version":"0.4.3"/)
  assert.match(prompt, /Hanya gunakan path dalam manifest/)
})

test('visible Scanner action opens the same dialog without submitting a model prompt', () => {
  const h = harness()
  const action = h.registrations.find(e => e.area === 'actions').render()
  const button = action.props.children.find(node => node.type === 'button')
  h.render().props.onOpenChange(false)
  button.props.onClick()
  assert.equal(h.render().props.open, true)
  assert.equal(h.calls.length, 0)
})

test('new chat creates and activates a session before attachment, without a dummy message', async () => {
  const h = harness(null, x => x, true, { initialSession: null, useFocused: true })
  h.configure(); assert.equal(h.calls.length, 0)
  await h.start()
  assert.equal(h.calls[0].name, 'session.create')
  assert.equal(h.calls[0].args.source, 'desktop')
  assert.equal(h.calls[0].args.model, undefined)
  assert.equal(h.opens[0].id, 'new-stored')
  assert.equal(h.calls.filter(c => c.name === 'prompt.submit').length, 1)
  for (const call of h.calls.slice(1)) assert.equal(call.args.session_id, 'new-runtime')
  assert.match(h.calls.at(-1).args.text, /WORKFLOW SCANNER 0.4.3/)
})

test('duplicate starts while creating a session issue just one create and one prompt', async () => {
  let release
  const h = harness(async (name, args) => {
    if (name === 'session.create') { await new Promise(resolve => { release = resolve }); return { session_id: 'new-runtime', stored_session_id: 'new-stored' } }
    return { attached: true, path: args.path }
  }, x => x, true, { initialSession: null })
  h.configure()
  const one = h.start(), two = h.start()
  assert.equal(h.calls.length, 1); release(); await Promise.all([one, two])
  assert.equal(h.calls.filter(c => c.name === 'session.create').length, 1)
  assert.equal(h.calls.filter(c => c.name === 'prompt.submit').length, 1)
})

test('create failure keeps selected files and a retry can start without selecting again', async () => {
  let fail = true
  const h = harness(async (name, args) => {
    if (name === 'session.create') { if (fail) { fail = false; return { error: 'offline' } } return { session_id: 'new-runtime', stored_session_id: 'new-stored' } }
    return { attached: true, path: args.path }
  }, x => x, true, { initialSession: null })
  h.configure(); await h.start()
  assert.equal(h.calls.length, 1); assert.equal(h.render().props.open, true)
  await h.start()
  assert.equal(h.calls.filter(c => c.name === 'file.attach').length, 1)
  assert.equal(h.calls.at(-1).name, 'prompt.submit')
})

test('open failure retries the same created session and never attaches to an unseen one', async () => {
  let fail = true, h
  h = harness(null, x => x, true, { initialSession: null, openSession: async () => {
    if (fail) { fail = false; throw new Error('not yet') }
    h.changeSession('new-runtime')
  } })
  h.configure(); await h.start()
  assert.deepEqual(h.calls.map(c => c.name), ['session.create'])
  await h.start()
  assert.equal(h.calls.filter(c => c.name === 'session.create').length, 1)
  assert.equal(h.calls.at(-1).name, 'prompt.submit')
})

test('changing profile or connection during create prevents activation and file submission', async () => {
  for (const change of ['changeProfile', 'changeConnection', 'changeSession']) {
    let h
    h = harness(async () => { h[change]('other'); return { session_id: 'new-runtime', stored_session_id: 'new-stored' } }, x => x, true, { initialSession: null })
    h.configure(); await h.start()
    assert.equal(h.opens.length, 0)
    assert.deepEqual(h.calls.map(c => c.name), ['session.create'])
  }
})

test('unmount during session creation cannot activate a chat or send files afterwards', async () => {
  let h
  h = harness(async () => { h.unmount(); return { session_id: 'new-runtime', stored_session_id: 'new-stored' } }, x => x, true, { initialSession: null })
  h.configure(); await h.start()
  assert.equal(h.opens.length, 0); assert.equal(h.calls.length, 1)
})

test('focused draft never falls back to another tile activeSessionId', async () => {
  const h = harness(null, x => x, true, { initialSession: 'stale-main', focused: null, useFocused: true })
  h.configure(); await h.start()
  assert.equal(h.calls[0].name, 'session.create')
  assert.ok(h.calls.every(c => c.args.session_id !== 'stale-main'))
})

test('existing focused session is used instead of another active tile', async () => {
  const h = harness(null, x => x, true, { initialSession: 'main', focused: 'focused-chat', useFocused: true })
  h.configure(); await h.start()
  assert.ok(h.calls.every(c => c.args.session_id === 'focused-chat'))
  assert.equal(h.opens.length, 0)
})

test('offline gateway and unsupported SDK give explicit errors without creating or attaching', async () => {
  const offline = harness(null, x => x, true, { initialSession: null }); offline.configure(); offline.changeGateway('connecting')
  await offline.start(); assert.equal(offline.calls.length, 0)
  assert.match(offline.notices.at(-1).message, /GATEWAY_NOT_READY/)
  const old = harness(null, x => x, true, { initialSession: null, unsupported: true }); old.configure()
  await old.start(); assert.equal(old.calls.length, 0); assert.match(old.notices.at(-1).message, /SDK_UNSUPPORTED/)
})

test('existing stored chat still loading must not create a new session', async () => {
  const h = harness(null, x => x, true, { initialSession: null, useFocused: true, stored: 'loading-chat' })
  h.configure(); await h.start()
  assert.equal(h.calls.length, 0); assert.match(h.notices.at(-1).message, /SESSION_NOT_READY/)
})

test('hydration timeout is explicit and never fabricates an active session id', async () => {
  const h = harness(null, x => x, true, { initialSession: null })
  await assert.rejects(h.api.waitForCreatedSession({ id: 'new', stored: 'stored' }, h.api.sessionScope(), () => true, 0), /SESSION_NOT_READY/)
  assert.equal(h.calls.length, 0)
})

test('profile change before start is rejected even when runtime id is unchanged', async () => {
  const h = harness(); h.configure(); h.changeProfile('other')
  await h.start(); assert.equal(h.calls.length, 0)
})

test('cancelling the picker preserves selection but an invalid replacement clears it', async () => {
  const h = harness(); h.configure(); h.set(0, []); await h.start()
  assert.equal(manifest(h).project, 'Paket CV gabungan')
  const other = harness(); other.configure(); other.set(0, [other.file('not-a-pdf.png')])
  await other.start(); assert.equal(other.calls.length, 0)
})

test('replacement selection and attached path are the sole document source', async () => {
  const h = harness(async (name) => name === 'file.attach' ? { attached: true, path: 'C:\\Session\\stored.pdf' } : {})
  h.configure('old.pdf'); h.configure('New CV.PDF'); await h.start()
  const data = manifest(h)
  assert.equal(data.project, 'New CV')
  assert.equal(data.documents[0].path, 'C:\\Session\\stored.pdf')
  assert.equal(h.calls[0].args.name, 'New CV.PDF')
  assert.equal(data.documents.length, 1)
})

test('filename punctuation is JSON data and metadata is generated without manual input', async () => {
  const h = harness(); h.configure('CV "contoh".PDF'); await h.start()
  assert.equal(manifest(h).project, 'CV "contoh"')
  assert.match(manifest(h).assessment_date, /^\d{4}-\d{2}-\d{2}$/)
  assert.equal(h.api.reportTitle({ name: '.pdf' }), 'Ringkasan CV')
  assert.ok(h.api.reportTitle({ name: 'x'.repeat(200) + '.pdf' }).length <= 160)
})

test('selected PDF cannot change while session is being prepared', async () => {
  let release
  const h = harness(async (name, args) => {
    if (name === 'session.create') { await new Promise(resolve => { release = resolve }); return { session_id: 'new-runtime', stored_session_id: 'new-stored' } }
    return { attached: true, path: args.path }
  }, x => x, true, { initialSession: null })
  h.configure('first.pdf'); const started = h.start(); h.configure('second.pdf')
  release(); await started
  assert.equal(manifest(h).project, 'first')
})

test('busy chat prevents attaching even when only one PDF was selected', async () => {
  const h = harness(); h.configure(); h.host.state.busy = { get: () => true }
  await h.start(); assert.equal(h.calls.length, 0)
  assert.match(h.notices.at(-1).message, /CHAT_BUSY/)
})
