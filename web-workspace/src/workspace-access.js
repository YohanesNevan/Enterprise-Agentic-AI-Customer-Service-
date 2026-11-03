// Staff roles are the human roles with an entry in the Staff Workspace navigation.
// The backend independently enforces the permissions attached to each verified role.
export const STAFF_ROUTES = Object.freeze({
  cs_agent: [['/agent/queue', 'Antrean'], ['/agent/conversations', 'Percakapan'], ['/agent/cases', 'Kasus & tiket']],
  supervisor: [['/supervisor', 'Operasional'], ['/supervisor/queue', 'Antrean'], ['/supervisor/cases', 'Kasus'], ['/supervisor/approvals', 'Persetujuan'], ['/supervisor/sla', 'SLA'], ['/supervisor/audit', 'Audit']],
  complaint_officer: [['/complaints', 'Penanganan keluhan']],
  knowledge_manager: [],
  qa_analyst: [['/qa', 'Quality review']],
  management: [['/management', 'Ringkasan kinerja']],
  admin: [['/admin', 'Administrasi sistem']],
})

export const KNOWLEDGE_WORKSPACE_ROLES = Object.freeze(Object.keys(STAFF_ROUTES))

export function staffNavigationFor(role) {
  const links = STAFF_ROUTES[role]
  if (!links) return []
  return [...links, ['/knowledge', 'Basis pengetahuan']]
}

export function canOpenKnowledgeWorkspace(role) {
  return KNOWLEDGE_WORKSPACE_ROLES.includes(role)
}
