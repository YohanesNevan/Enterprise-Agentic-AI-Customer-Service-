// Staff roles are the human roles with an entry in the Staff Workspace navigation.
// The backend independently enforces the permissions attached to each verified role.
export const STAFF_ROUTES = Object.freeze({
  cs_agent: [
    ['/agent/queue', 'Queue & Handoff'],
    ['/agent/conversations', 'Customer Conversations'],
    ['/agent/cases', 'Tickets & Cases'],
  ],
  supervisor: [
    ['/supervisor', 'Dashboard Operasional'],
    ['/supervisor/queue', 'Queue & Handoff'],
    ['/supervisor/cases', 'Tickets & Cases'],
    ['/supervisor/approvals', 'Approval Requests'],
    ['/supervisor/sla', 'SLA Monitoring'],
    ['/supervisor/audit', 'Audit Trail'],
  ],
  complaint_officer: [['/complaints', 'Complaint Officer']],
  knowledge_manager: [],
  qa_analyst: [['/qa', 'QA Review & Scoring']],
  management: [['/management', 'Analytics & Reports']],
  admin: [['/admin', 'System Administration']],
})

export const KNOWLEDGE_WORKSPACE_ROLES = Object.freeze(Object.keys(STAFF_ROUTES))

export function staffNavigationFor(role) {
  const links = STAFF_ROUTES[role]
  if (!links) return []
  return [...links, ['/knowledge', 'Knowledge Base']]
}

export function canOpenKnowledgeWorkspace(role) {
  return KNOWLEDGE_WORKSPACE_ROLES.includes(role)
}
