import axios from 'axios'
import { ref } from 'vue'
import { device, events, manuals, cases, logs, recentActions, chartPoints } from '../data/mockData'

// The local FastAPI backend is the default. Mock mode must be selected explicitly.
const useApi = import.meta.env.VITE_DATA_SOURCE !== 'mock'
const client = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api', timeout: 8000 })
export const connectionState = ref(useApi ? 'checking' : 'mock')
client.interceptors.response.use(
  (response) => { connectionState.value = 'connected'; return response },
  (error) => { if (!error.config?.url?.includes('/ai-guidance')) connectionState.value = 'error'; return Promise.reject(error) },
)
const copy = (value) => structuredClone(value)
const read = async (path, mockValue) => useApi ? (await client.get(path)).data : copy(mockValue)

export const dataMode = useApi ? 'api' : 'mock'
export const getDashboard = async () => useApi ? (await client.get('/dashboard')).data : {
  devices: 1,
  normalDevices: device.status === 'normal' ? 1 : 0,
  faults: events.length,
  unrecoveredFaults: events.filter((event) => !event.recoveredAt).length,
  unresolvedFaults: events.filter((event) => event.status === 'open').length,
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
export const getChartPoints = () => read('/metrics/events', chartPoints)

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
