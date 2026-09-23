// Contract tests with a mocked SDK/React host. No claim of live Electron execution.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

function harness(request) {
  let cursor = 0
  const hooks = [], calls = [], notices = []
  let session = 'session-1'
  const host = { state: { activeSessionId: { get: () => session } }, notify: value => notices.push(value),
    request: async (name, args) => { calls.push({ name, args }); return request ? request(name, args) : { attached: true, path: args.path } } }
  const useState = initial => {
    const i = cursor++
    if (!(i in hooks)) hooks[i] = typeof initial === 'function' ? initial() : initial
    return [hooks[i], next => { hooks[i] = typeof next === 'function' ? next(hooks[i]) : next }]
  }
  const useRef = initial => { const i = cursor++; if (!(i in hooks)) hooks[i] = { current: initial }; return hooks[i] }
  const useEffect = fn => { const i = cursor++; if (!(i in hooks)) { hooks[i] = true; fn() } }
  const sdk = { host, useState, useRef, useEffect, jsx: (type, props) => ({ type, props }),
    Dialog: 'Dialog', DialogContent: 'DialogContent', DialogHeader: 'DialogHeader', DialogTitle: 'DialogTitle', DialogDescription: 'DialogDescription',
    COMPOSER_AREAS: { actions: 'actions', middleware: 'middleware' }, window: { hermesDesktop: { getPathForFile: f => f.path } } }
  let source = fs.readFileSync(path.join(__dirname, '../desktop/plugin.js'), 'utf8')
  source = source.replace(/^import .*\n/gm, '').replace('export default {', 'const plugin = {')
  source += '\nglobalThis.api = { plugin, ScannerDataDialog, scannerPrompt, localDate }'
  vm.runInNewContext(source, sdk)
  const render = () => { cursor = 0; return sdk.api.ScannerDataDialog() }
  const flatten = node => !node ? [] : Array.isArray(node) ? node.flatMap(flatten) : typeof node === 'object'
    ? [node, ...flatten(node.props?.children)] : []
  function inputs() { return flatten(render()).filter(n => n.type === 'input') }
  const set = (index, value) => inputs()[index].props.onChange({ target: { value, files: value, checked: value } })
  const file = name => ({ name, path: `C:\\Docs\\${name}`, size: 100 })
  function configure() { set(0, 'Paket Uji'); set(1, '2026-09-23'); set(2, '2'); set(3, [file('a.pdf'), file('b.pdf')]); set(4, [file('kak.pdf')]) }
  render()
  const registrations = []
  sdk.api.plugin.register({ register: entry => registrations.push(entry) })
  const command = registrations.find(e => e.area === 'middleware').data.handler
  assert.equal(command({ text: '/scanner-data' }), null)
  render()
  return { calls, notices, configure, set, file, api: sdk.api, command, changeSession: value => { session = value },
    start: () => flatten(render()).find(n => n.type === 'button').props.onClick() }
}

test('multiple inputs only start on explicit button and attach to bound session', async () => {
  const h = harness(); h.configure(); assert.equal(h.calls.length, 0)
  await h.start()
  assert.deepEqual(h.calls.map(c => c.name), ['file.attach', 'file.attach', 'file.attach', 'prompt.submit'])
  for (const call of h.calls) assert.equal(call.args.session_id, 'session-1')
  const prompt = h.calls.at(-1).args.text
  assert.match(prompt, /expected_person_count.*2/)
  assert.match(prompt, /read_document/); assert.match(prompt, /certificate_inventory/)
  assert.match(prompt, /chat_markdown/); assert.match(prompt, /XLSX dan PDF/)
  assert.match(prompt, /scanner_web_lookup/); assert.match(prompt, /save_person/)
})

test('KAK absence requires explicit acknowledgement', async () => {
  const h = harness(); h.configure(); h.set(4, [])
  await h.start(); assert.equal(h.calls.length, 0)
  h.set(7, true); await h.start()
  assert.equal(h.calls.at(-1).name, 'prompt.submit')
})

test('empty files and invalid expected count are rejected', async () => {
  const h = harness(); h.configure(); h.set(3, []); h.set(3, [{ ...h.file('bad.exe'), size: 0 }])
  await h.start(); assert.equal(h.calls.length, 0)
  h.configure(); h.set(2, '2.5'); await h.start(); assert.equal(h.calls.length, 0)
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

test('duplicate files do not reach prompt; disabling web is included in manifest', async () => {
  const h = harness(); h.configure(); h.set(4, [h.file('a.pdf')]); await h.start()
  assert.equal(h.calls.filter(c => c.name === 'prompt.submit').length, 0)
  const fresh = harness(); fresh.configure(); fresh.set(8, false); await fresh.start()
  assert.match(fresh.calls.at(-1).args.text, /"allow_web":false/)
})

test('non-scanner drafts are preserved and prompt treats source text as untrusted', () => {
  const h = harness(); const draft = { text: 'hello' }; assert.equal(h.command(draft), draft)
  const prompt = h.api.scannerPrompt({ project: 'Test', documents: [] })
  assert.match(prompt, /tidak tepercaya/); assert.match(prompt, /CAPTCHA/)
  assert.match(prompt, /Jangan mengklaim semua valid/)
  assert.match(h.api.localDate(), /^\d{4}-\d{2}-\d{2}$/)
})
