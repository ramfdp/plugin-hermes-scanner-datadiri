// SDK contract test; run with node desktop/plugin.test.cjs.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')

async function check() {
  const slots = [], contributions = [], calls = [], notices = []
  let cursor = 0, mounted = false, sessionId = 'chat-1', failAttach = false, switchChat = false
  const host = {
    state: { activeSessionId: { get: () => sessionId } },
    notify: notice => notices.push(notice),
    request: async (method, params) => {
      calls.push({ method, params })
      if (method === 'file.attach') {
        if (failAttach) throw new Error('Attach failed')
        if (switchChat) sessionId = 'chat-2'
        return { attached: true, name: 'cv.pdf', path: 'C:\\staged\\cv.pdf' }
      }
      return { accepted: true }
    },
  }
  const context = {
    host, COMPOSER_AREAS: { actions: 'actions', middleware: 'middleware' },
    Dialog: 'Dialog', DialogContent: 'DialogContent', DialogHeader: 'DialogHeader',
    DialogTitle: 'DialogTitle', DialogDescription: 'DialogDescription',
    window: { hermesDesktop: { getPathForFile: () => 'C:\\source\\cv.pdf' } },
    jsx: (type, props) => ({ type, props }),
    useState: initial => {
      const index = cursor++
      if (!(index in slots)) slots[index] = initial
      return [slots[index], value => { slots[index] = value }]
    },
    useRef: initial => {
      const index = cursor++
      if (!(index in slots)) slots[index] = { current: initial }
      return slots[index]
    },
    useEffect: fn => { if (!mounted) fn() },
  }
  const code = fs.readFileSync(`${__dirname}/plugin.js`, 'utf8')
    .replace(/^import .*\r?\n/gm, '').replace('export default {', 'globalThis.plugin = {')
  vm.runInNewContext(code, context)
  context.plugin.register({ register: value => contributions.push(value) })
  const Component = contributions.find(c => c.area === 'actions').render().type
  const middleware = contributions.find(c => c.area === 'middleware').data.handler
  const render = () => { cursor = 0; const tree = Component(); mounted = true; return tree }
  const input = tree => tree.props.children.props.children.find(child => child.type === 'input')
  const select = file => input(render()).props.onChange({ target: { files: [file], value: 'cv.pdf' } })
  render()
  const draft = { text: 'ordinary chat' }
  assert.equal(middleware(draft), draft)
  assert.equal(middleware({ text: ' /scanner-data ' }), null)
  assert.equal(render().props.open, true)
  await select({ name: 'bad.txt', size: 10 })
  assert.equal(calls.length, 0)
  const pending = select({ name: 'CV.PDF', size: 10 })
  await select({ name: 'CV.PDF', size: 10 })
  await pending
  assert.equal(calls.length, 2, 'Only one attach and one prompt')
  assert.equal(calls[1].params.session_id, 'chat-1')
  const prompt = calls[1].params.text
  assert.ok(prompt.includes(JSON.stringify('C:\\staged\\cv.pdf')), 'Use gateway path')
  for (const step of ['scan_document_ocr', 'export_document', 'workbook_data', 'web_search', 'web_extract', 'export_cv_report', 'employer_validation']) {
    assert.ok(prompt.includes(step), `Missing workflow step: ${step}`)
  }
  assert.ok(prompt.indexOf('export_document') < prompt.indexOf('web_search'))
  assert.ok(prompt.indexOf('web_extract') < prompt.indexOf('export_cv_report'))
  assert.equal(render().props.open, false)
  for (const failure of ['attach', 'chat-switch']) {
    middleware({ text: '/scanner-data' })
    failAttach = failure === 'attach'
    switchChat = failure === 'chat-switch'
    const before = calls.length
    await select({ name: 'cv.pdf', size: 10 })
    assert.equal(calls.length, before + 1, 'Failure must not submit a prompt')
    assert.equal(render().props.open, true)
    assert.equal(input(render()).props.disabled, false, 'Allow retry')
  }
  assert.ok(notices.some(n => n.kind === 'error'))
  console.log('Desktop workflow contract passed: command, PDF, ordering, duplicate guard, failures, session switch')
}
check().catch(error => { console.error(error); process.exitCode = 1 })
