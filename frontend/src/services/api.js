import axios from 'axios'
import { ref } from 'vue'
import { device, events, manuals, cases, logs, recentActions, chartPoints } from '../data/mockData'

// The local FastAPI backend is the default. Mock mode must be selected explicitly.
const useApi = import.meta.env.VITE_DATA_SOURCE !== 'mock'
const client = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api', timeout: 8000 })
export const connectionState = ref(useApi ? 'checking' : 'mock')
export const monitoringState = ref(null)
client.interceptors.response.use(
  (response) => { connectionState.value = 'connected'; return response },
  (error) => { if (!error.config?.url?.includes('/ai-guidance')) connectionState.value = 'error'; return Promise.reject(error) },
)
const copy = (value) => structuredClone(value)
const read = async (path, mockValue) => useApi ? (await client.get(path)).data : copy(mockValue)

export const dataMode = useApi ? 'api' : 'mock'
export const getHealth = async () => {
  if (!useApi) return null
  const result = (await client.get('/health')).data
  monitoringState.value = result
  return result
}
export const getDashboard = async () => useApi ? (await client.get('/dashboard')).data : {
  devices: 1,
  normalDevices: device.status === 'normal' ? 1 : 0,
  faults: events.length,
  unrecoveredFaults: events.filter((event) => !event.recoveredAt).length,
  unresolvedFaults: events.filter((event) => event.status === 'open').length,
  recoveredFaults: events.filter((event) => Boolean(event.recoveredAt)).length,
  completedActions: events.filter((event) => event.status === 'resolved').length,
  faultsByType: {
    CONNECTION_TIMEOUT: events.filter((event) => event.type === 'message_timeout').length,
    RESPONSE_DELAY: events.filter((event) => event.type === 'response_delay').length,
    INVALID_MESSAGE: events.filter((event) => event.type === 'format_error').length,
  },
}
export const getDevices = () => read('/devices', [device])
export const getDevice = () => read('/devices/RPI-01', useApi ? device : {
  ...device,
  lastReceivedAt: new Date().toISOString(),
  recentMessage: { ...device.recentMessage, timestamp: new Date().toISOString() },
})
export const getEvents = () => read('/events', events)
export const getEvent = async (id) => useApi ? (await client.get(`/events/${encodeURIComponent(id)}`)).data : copy(events.find((item) => item.id === id) || null)
// Knowledge documents remain explicitly labeled practice data until phase 3.
export const getManuals = async () => useApi ? (await client.get('/manuals')).data : copy(manuals)
export const getCases = async () => copy(cases)
export const getAiGuidance = async (id) => useApi ? (await client.get(`/events/${encodeURIComponent(id)}/ai-guidance`, { timeout: 65000 })).data : null
export const getEventLogs = (id) => read(`/events/${encodeURIComponent(id)}/logs`, id === 'EVT-20261027-006' ? logs : [])
export const getRecentActions = () => read('/actions/recent', recentActions)
// 최근 15분 분 단위 집계 (시연 중 끊긴 구간이 보이도록)
export const getChartPoints = () => read('/metrics/recent', chartPoints)
// 이 시스템에 실제로 저장된 조치 기록 (지식으로 재사용)
export const getKnowledgeActions = async () => useApi ? (await client.get('/actions/recent', { params: { limit: 50 } })).data : []
export const getPastActions = async (id) => useApi ? (await client.get(`/events/${encodeURIComponent(id)}/past-actions`)).data : []

// Demo responses are saved in this browser only.
export const getLocalResponse = (id) => {
  try { return JSON.parse(localStorage.getItem(`event-response:${id}`) || 'null') }
  catch { return null }
}
export const saveEventResponse = async (id, response) => {
  if (useApi) return (await client.post(`/events/${encodeURIComponent(id)}/actions`, {
    checklist: response.checked,
    action_text: response.action,
    resolved: Boolean(response.resolved),
  })).data
  localStorage.setItem(`event-response:${id}`, JSON.stringify(response))
  return response
}
