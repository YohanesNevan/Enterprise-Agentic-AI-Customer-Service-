import assert from 'node:assert/strict'
import test from 'node:test'
import {
  KNOWLEDGE_WORKSPACE_ROLES,
  canOpenKnowledgeWorkspace,
  staffNavigationFor,
} from '../src/workspace-access.js'

test('every Staff Workspace role has the shared Knowledge Base route and menu link', () => {
  assert.deepEqual(KNOWLEDGE_WORKSPACE_ROLES, [
    'cs_agent', 'supervisor', 'complaint_officer', 'knowledge_manager',
    'qa_analyst', 'management', 'admin',
  ])
  for (const role of KNOWLEDGE_WORKSPACE_ROLES) {
    assert.equal(canOpenKnowledgeWorkspace(role), true)
    assert.ok(staffNavigationFor(role).some(([path]) => path === '/knowledge'))
  }
})

test('customer, service, and unknown roles do not receive Staff Workspace access', () => {
  for (const role of ['customer', 'ai_agent', 'unknown']) {
    assert.equal(canOpenKnowledgeWorkspace(role), false)
    assert.deepEqual(staffNavigationFor(role), [])
  }
})
