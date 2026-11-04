const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

let authProvider = null
const authListeners = new Set()
let developmentToken = null
let developmentPrincipal = null

export const isDevelopmentAuthEnabled = import.meta.env.VITE_ENABLE_DEV_CUSTOMER_AUTH === 'true'
export const isDevelopmentStaffAuthEnabled = import.meta.env.VITE_ENABLE_DEV_STAFF_AUTH === 'true'

async function installDevelopmentSession(endpoint, username, password) {
  const result = await req(endpoint, { method: 'POST', body: { username, password }, auth: false })
  developmentToken = result.access_token
  developmentPrincipal = result.principal
  configureAuthProvider({
    getAccessToken: async () => developmentToken,
    getSession: async () => developmentToken ? { principal: developmentPrincipal } : null,
    onUnauthorized: async () => { developmentToken = null; developmentPrincipal = null },
  })
  return developmentPrincipal
}

export async function devUniversalLogin(username, password) {
  try {
    return await installDevelopmentSession('/v1/dev-auth/login', username, password)
  } catch (err) {
    // Jika endpoint baru belum termuat (backend belum restart), fallback otomatis ke rute lama
    if (err?.status === 404) {
      try {
        return await installDevelopmentSession('/v1/dev-auth/customer/login', username, password)
      } catch (custErr) {
        try {
          return await installDevelopmentSession('/v1/dev-auth/staff/login', username, password)
        } catch {
          throw custErr
        }
      }
    }
    throw err
  }
}

export function devCustomerLogin(username, password) {
  return installDevelopmentSession('/v1/dev-auth/customer/login', username, password)
}

export function devStaffLogin(username, password) {
  return installDevelopmentSession('/v1/dev-auth/staff/login', username, password)
}

export function devCustomerLogout() {
  developmentToken = null
  developmentPrincipal = null
  configureAuthProvider(null)
}

export function configureAuthProvider(provider) {
  authProvider = provider || null
  authListeners.forEach((listener) => listener())
}

export async function getAuthSession() {
  if (!authProvider?.getSession) return null
  return authProvider.getSession()
}

export function subscribeAuth(listener) {
  authListeners.add(listener)
  return () => authListeners.delete(listener)
}

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export async function req(path, { method = 'GET', body, download = false, auth = true, headers: extraHeaders = {} } = {}) {
  let accessToken = null
  if (auth) {
    if (!authProvider?.getAccessToken) {
      throw new ApiError(401, 'AUTH_REQUIRED', 'Authentication is required to access this service.')
    }
    accessToken = await authProvider.getAccessToken()
    if (!accessToken) throw new ApiError(401, 'AUTH_REQUIRED', 'Authentication is required to access this service.')
  }

  const headers = {}
  Object.assign(headers, extraHeaders)
  const isFormData = body instanceof FormData
  if (body !== undefined && !isFormData) headers['Content-Type'] = 'application/json'
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : (isFormData ? body : JSON.stringify(body)),
  })

  if (response.status === 401) {
    if (auth) {
      try { await authProvider?.onUnauthorized?.() } catch { /* the provider owns its own error reporting */ }
      authListeners.forEach((listener) => listener())
      throw new ApiError(401, 'UNAUTHENTICATED', 'Your session is missing or expired. Sign in again.')
    }
    throw new ApiError(401, 'INVALID_CREDENTIALS', 'Username or password is incorrect.')
  }
  if (response.status === 403) throw new ApiError(403, 'FORBIDDEN', 'You do not have permission to perform this action.')
  if (!response.ok) {
    let message = `Request failed (${response.status}).`
    try {
      const data = await response.json()
      const detail = data.detail || data
      message = typeof detail === 'string' ? detail : detail.message || detail.customer_message_id || message
    } catch { /* use generic response */ }
    if (accessToken && String(message).includes(accessToken)) message = `Request failed (${response.status}).`
    throw new ApiError(response.status, 'REQUEST_FAILED', message)
  }
  if (download) return response.text()
  if (response.status === 204) return null
  return response.json()
}

export const CLOSURE_ITEMS = [
  ['outcome_recorded', 'Outcome recorded'],
  ['customer_notified', 'Customer notified'],
  ['root_cause_set', 'Root cause set'],
  ['evidence_adjudicated', 'Evidence adjudicated'],
  ['no_open_child_tickets', 'No open child tickets'],
  ['sla_finalised', 'SLA finalised'],
  ['qa_eligible_set', 'QA eligibility set'],
]
export const QA_FIELDS = ['identitas', 'sitasi', 'klasifikasi', 'tool', 'bukti', 'komunikasi', 'komitmen', 'penutupan']
export const QA_AUTO_FAIL = ['PII_UNDER_AL', 'NO_CITATION', 'PROHIBITED_TOOL']
export const QA_FINDING_TYPES = ['individual_coaching', 'knowledge_gap', 'process_defect', 'ai_defect', 'system_defect']
export const SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
export const REASONS = ['LOW_CONFIDENCE', 'CUSTOMER_REQUEST', 'MANDATORY_INTENT', 'APPROVAL_REQUIRED', 'SENTIMENT_ESCALATION', 'VULNERABILITY', 'TOOL_FAILURE', 'AUTH_LOCKOUT', 'REPEAT_CONTACT', 'POLICY_DENIED', 'DEGRADED_MODE']
