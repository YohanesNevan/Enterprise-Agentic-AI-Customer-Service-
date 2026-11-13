import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const appSource = readFileSync(
  new URL('../src/pages/workspace/ConversationWorkbench.jsx', import.meta.url),
  'utf8',
)

test('agent reply validates, posts through the workspace endpoint, and refreshes the transcript', () => {
  assert.match(appSource, /const content = reply\.trim\(\)/)
  assert.match(appSource, /Balasan tidak boleh kosong/)
  assert.match(appSource, /\/messages`, \{ method: 'POST', body: \{ content \} \}/)
  assert.match(appSource, /await onRefresh\(d\.conversation_id, true\)/)
  assert.match(appSource, /busy === 'reply' \? 'Menyimpan\.\.\.' : 'Kirim balasan'/)
  assert.match(appSource, /role="alert"/)
})

test('agent controls use accepted-owner state and existing conversation transitions', () => {
  assert.match(appSource, /d\.handoff\?\.state === 'ACCEPTED' && d\.handoff\.accepted_by === actorId/)
  assert.match(appSource, /\/workspace\/handoffs\/\$\{encodeURIComponent\(d\.handoff\.handoff_id\)\}\/accept/)
  assert.match(appSource, /\/resolve`, \{ method: 'POST', body: \{\} \}/)
  assert.match(appSource, /RESOLVED_PENDING_CONFIRMATION/)
  assert.match(appSource, /m\.author_type === 'HUMAN_AGENT' \? 'Petugas CS'/)
})

test('existing case and ticket APIs are linked to the currently opened conversation', () => {
  assert.match(appSource, /req\('\/v1\/cases', \{ method: 'POST'/)
  assert.match(appSource, /req\('\/v1\/tickets', \{ method: 'POST'/)
  assert.match(appSource, /conversation_id: d\.conversation_id/)
  assert.match(appSource, /Kasus dibuat dan ditautkan ke percakapan/)
  assert.match(appSource, /Tiket dibuat dan ditautkan ke percakapan/)
})
