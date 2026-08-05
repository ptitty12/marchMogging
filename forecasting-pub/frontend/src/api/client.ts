import type { AuditRecord, BusinessUnit, Dimension, Grid, Period } from '../types'

let currentUser = localStorage.getItem('fp.user') || 'demo.user'

export function getUser() {
  return currentUser
}

export function setUser(user: string) {
  currentUser = user
  localStorage.setItem('fp.user', user)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-User': currentUser,
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`${res.status}: ${body}`)
  }
  return res.json()
}

export const api = {
  businessUnits: () => request<BusinessUnit[]>('/api/business-units'),
  periods: () => request<Period[]>('/api/periods'),
  dimensions: () => request<Dimension[]>('/api/dimensions'),

  grid: (configId: number, periods: string[]) => {
    const qs = new URLSearchParams({ config_id: String(configId) })
    periods.forEach((p) => qs.append('periods', p))
    return request<Grid>(`/api/forecast/grid?${qs}`)
  },

  saveEntry: (
    configId: number,
    payload: {
      period_code: string
      slice_values: Record<string, string>
      adjustment?: number | null
      total_forecast?: number | null
      comment?: string | null
      set_fields: string[]
    },
  ) =>
    request(`/api/forecast/configs/${configId}/entries`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  audit: (configId: number, params?: { period_code?: string; slice_key?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>)
    return request<AuditRecord[]>(`/api/forecast/configs/${configId}/audit?${qs}`)
  },

  createBusinessUnit: (payload: { code: string; name: string; description?: string }) =>
    request<BusinessUnit>('/api/business-units', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  createConfig: (buId: number, payload: unknown) =>
    request(`/api/business-units/${buId}/configs`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
}
