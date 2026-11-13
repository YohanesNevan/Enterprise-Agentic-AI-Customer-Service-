export const CUSTOMER_CONVERSATION_STATES = {
  NEW: 'Percakapan baru', ACTIVE_AI: 'Sedang ditangani layanan', AWAITING_CUSTOMER: 'Menunggu balasan Anda',
  AWAITING_AUTH: 'Menunggu verifikasi', AWAITING_EVIDENCE: 'Menunggu informasi tambahan',
  PENDING_HANDOFF: 'Menunggu petugas', ACTIVE_HUMAN: 'Dialihkan ke petugas',
  RESOLVED_PENDING_CONFIRMATION: 'Menunggu konfirmasi Anda', CLOSED: 'Selesai',
  ABANDONED: 'Tidak dilanjutkan', REOPENED: 'Dibuka kembali',
}

export function customerConversationState(status) { return CUSTOMER_CONVERSATION_STATES[status] || 'Status layanan diperbarui' }

export function navigate(path) { if (window.location.pathname !== path) window.history.pushState({}, '', path); window.dispatchEvent(new PopStateEvent('popstate')) }
