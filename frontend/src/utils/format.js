export const formatTime = (value) => value ? new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'medium' }).format(new Date(value)) : '—'
export const formatDuration = (seconds) => seconds == null ? '진행 중' : `${Math.floor(seconds / 60)}분 ${seconds % 60}초`
export const formatElapsed = (time, now = Date.now()) => {
  if (!time) return '—'
  const seconds = Math.max(0, Math.floor((now - new Date(time).getTime()) / 1000))
  return seconds < 60 ? `${seconds}초` : `${Math.floor(seconds / 60)}분 ${seconds % 60}초`
}
