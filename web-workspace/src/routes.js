import { KNOWLEDGE_WORKSPACE_ROLES } from './workspace-access.js'

export const CUSTOMER_LINKS = [
  ['/customer/chat', 'Live Chat & AI Assistant'],
  ['/customer/requests/new', 'Pengaduan & Tiket (Submit)'],
  ['/customer/requests', 'Track Status & SLA'],
  ['/customer/conversations', 'Riwayat Chat (History)'],
  ['/customer/account', 'Profil Akun'],
]

export const ROUTES = {
  '/login': { title: 'Portal Login', audience: 'public', page: 'login' },
  '/customer/login': { title: 'Customer Login', audience: 'public', page: 'login' },
  '/staff/login': { title: 'Staff Workspace Login', audience: 'public', page: 'login' },
  '/customer/chat': { title: 'Customer Live Chat & Assistant', audience: 'customer', page: 'customer-chat' },
  '/customer/requests/new': { title: 'Submit Complaint & Ticket', audience: 'customer', page: 'customer-request' },
  '/customer/requests': { title: 'Track Status & SLA Tickets', audience: 'customer', page: 'customer-track' },
  '/customer/conversations': { title: 'Conversation History', audience: 'customer', page: 'customer-history' },
  '/customer/account': { title: 'Customer Account Profile', audience: 'customer', page: 'customer-account' },
  '/agent/queue': { title: 'Queue & Handoff Management', audience: ['cs_agent', 'supervisor'], page: 'queue' },
  '/agent/conversations': { title: 'Customer Conversations Workbench', audience: ['cs_agent', 'supervisor'], page: 'conv' },
  '/agent/cases': { title: 'Tickets & Case Management', audience: ['cs_agent', 'supervisor'], page: 'cases' },
  '/supervisor': { title: 'Supervisor Operations Dashboard', audience: 'supervisor', page: 'dash' },
  '/supervisor/queue': { title: 'Queue & Escalation Monitor', audience: 'supervisor', page: 'queue' },
  '/supervisor/cases': { title: 'Cases & Dispute Resolution', audience: 'supervisor', page: 'cases' },
  '/supervisor/approvals': { title: 'Approval Requests (Dual Custody)', audience: 'supervisor', page: 'approvals' },
  '/supervisor/sla': { title: 'SLA Monitoring & Notifications', audience: 'supervisor', page: 'sla' },
  '/supervisor/audit': { title: 'Audit Trail & Compliance', audience: 'supervisor', page: 'audit' },
  '/complaints': { title: 'Complaint & Dispute Officer', audience: 'complaint_officer', unit: '09' },
  '/knowledge': { title: 'Knowledge Base Manager', audience: KNOWLEDGE_WORKSPACE_ROLES, page: 'knowledge' },
  '/qa': { title: 'QA Review & Quality Assurance', audience: 'qa_analyst', page: 'qa' },
  '/management': { title: 'Executive Analytics & Performance', audience: 'management', page: 'analytics' },
  '/admin': { title: 'System Administration', audience: 'admin', unit: '14' },
}
