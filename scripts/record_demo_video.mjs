import fs from 'node:fs/promises'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { pathToFileURL } from 'node:url'

const root = path.resolve(import.meta.dirname, '..')
const playwrightPath = process.env.PLAYWRIGHT_MODULE_PATH
if (!playwrightPath) throw new Error('PLAYWRIGHT_MODULE_PATH must point to an installed Playwright package')
const { chromium } = await import(pathToFileURL(path.join(playwrightPath, 'index.mjs')).href)
const python = path.join(root, '.venv/Scripts/python.exe')
const mosquitto = 'C:/Program Files/mosquitto/mosquitto.exe'
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const db = path.join(root, `presentation/demo_recording_${stamp}.sqlite3`)
const videoDir = path.join(root, 'presentation/video')
const running = []
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
function start(exe, args, env = {}, cwd = root) {
  const child = spawn(exe, args, { cwd, env: { ...process.env, ...env }, windowsHide: true, stdio: 'ignore' })
  running.push(child)
  return child
}
async function ready(url) {
  for (let attempt = 0; attempt < 40; attempt++) {
    try { if ((await fetch(url)).ok) return } catch { /* wait for startup */ }
    await sleep(500)
  }
  throw new Error(`Service did not start: ${url}`)
}
let browser
try {
  await fs.mkdir(videoDir, { recursive: true })
  start(mosquitto, ['-p', '1884'])
  const env = { IOT_DB_PATH: db, MQTT_PORT: '1884' }
  start(python, ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8001'], env)
  start(python, ['-m', 'backend.mqtt_worker'], env)
  start(process.execPath, [path.join(root, 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5175', '--strictPort'], { VITE_API_BASE_URL: 'http://127.0.0.1:8001/api' }, path.join(root, 'frontend'))
  await ready('http://127.0.0.1:8001/api/health')
  await ready('http://127.0.0.1:5175/')
  let simulator = start(python, ['-m', 'raspberry_pi.device_simulator', '--mode', 'normal'], env)
  browser = await chromium.launch({ channel: 'chrome', headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: videoDir, size: { width: 1440, height: 900 } } })
  const page = await context.newPage()
  await page.goto('http://127.0.0.1:5175/dashboard')
  await page.waitForTimeout(5000)
  simulator.kill()
  simulator = start(python, ['-m', 'raspberry_pi.device_simulator', '--mode', 'delay'], env)
  await page.waitForTimeout(13000)
  await page.goto('http://127.0.0.1:5175/events')
  await page.waitForTimeout(2500)
  const firstLink = page.locator('.event-table .text-link').first()
  await firstLink.click()
  await page.waitForTimeout(9000)
  simulator.kill()
  start(python, ['-m', 'raspberry_pi.device_simulator', '--mode', 'normal'], env)
  await page.waitForTimeout(5000)
  const video = page.video()
  await context.close()
  const recorded = await video.path()
  const target = path.join(videoDir, `mqtt_fault_demo_${stamp}.webm`)
  await fs.rename(recorded, target)
  console.log(target)
} finally {
  await browser?.close()
  for (const child of running.reverse()) child.kill()
}
