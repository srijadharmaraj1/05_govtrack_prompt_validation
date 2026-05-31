const express = require('express')
const cors    = require('cors')
const fs      = require('fs')
const path    = require('path')
const { execFile } = require('child_process')

const app       = express()
const DATA_FILE = path.join(__dirname, '..', 'data', 'profiles.json')
const AGENT_PY  = path.join(__dirname, '..', 'agent.py')

app.use(cors())
app.use(express.json())

let store = { profiles: [], message: '', pushed_at: '', searching: false, lastQuery: '' }

function loadFromDisk() {
  try {
    const db = JSON.parse(fs.readFileSync(DATA_FILE, 'utf-8'))
    store.profiles  = db.profiles || []
    store.pushed_at = db.last_updated || new Date().toISOString()
    store.message   = `Loaded ${store.profiles.length} profiles from disk`
    console.log(`[bridge] ✅ Loaded ${store.profiles.length} profiles from disk`)
  } catch { console.log('[bridge] No existing data, starting fresh') }
}

function saveToDisk() {
  fs.writeFileSync(DATA_FILE, JSON.stringify({ profiles: store.profiles, last_updated: new Date().toISOString() }, null, 2), 'utf-8')
}

loadFromDisk()

// React polls this
app.get('/api/state', (req, res) => res.json(store))

// Frontend search trigger
app.post('/api/search', (req, res) => {
  const { query } = req.body
  if (!query?.trim()) return res.status(400).json({ error: 'Query required' })
  if (store.searching) return res.status(429).json({ error: 'Search in progress' })
  console.log(`[bridge] 🔍 Search: "${query}"`)
  store.searching = true; store.lastQuery = query; store.message = `Searching: "${query}"...`
  res.json({ ok: true })
  const python = process.platform === 'win32' ? 'python' : 'python3'
  const child  = execFile(python, [AGENT_PY, '--query', query], { timeout: 60000 })
  child.stdout.on('data', d => console.log('[agent]', d.trim()))
  child.stderr.on('data', d => console.error('[agent err]', d.trim()))
  child.on('close', (code) => {
    store.searching = false
    loadFromDisk()
    store.pushed_at = new Date().toISOString()
    store.message = code === 0 ? `✅ Results for: "${query}"` : `❌ Failed: "${query}"`
  })
})

// Agent pushes profiles
app.post('/api/push', (req, res) => {
  const { profiles, message, pushed_at } = req.body
  const existingQueries = new Set(store.profiles.map(p => p.query))
  const newOnes = (profiles||[]).filter(p => !existingQueries.has(p.query))
  store.profiles = [...store.profiles.map(e => { const inc=(profiles||[]).find(p=>p.query===e.query); return inc?{...e,...inc}:e }), ...newOnes]
  store.message  = message||''; store.pushed_at = pushed_at||new Date().toISOString()
  saveToDisk()
  console.log(`[bridge] /push — ${store.profiles.length} profiles total`)
  res.json({ ok: true })
})

// Refresh single profile
app.post('/api/refresh', (req, res) => {
  const { query } = req.body
  if (store.searching) return res.status(429).json({ error: 'Search in progress' })
  store.searching = true; store.message = `Refreshing: "${query}"...`
  res.json({ ok: true })
  const python = process.platform === 'win32' ? 'python' : 'python3'
  const child  = execFile(python, [AGENT_PY, '--query', query], { timeout: 60000 })
  child.stdout.on('data', d => console.log('[agent]', d.trim()))
  child.on('close', () => { store.searching = false; loadFromDisk(); store.pushed_at = new Date().toISOString(); store.message = `✅ Refreshed: "${query}"` })
})

// Delete
app.post('/api/delete', (req, res) => {
  const { query } = req.body
  store.profiles  = store.profiles.filter(p => p.query !== query)
  store.pushed_at = new Date().toISOString()
  saveToDisk()
  res.json({ ok: true })
})

// Note
app.post('/api/note', (req, res) => {
  const { query, note } = req.body
  const p = store.profiles.find(p => p.query === query)
  if (!p) return res.status(404).json({ error: 'Not found' })
  p.note = note; p.note_at = new Date().toISOString()
  store.pushed_at = new Date().toISOString(); saveToDisk()
  res.json({ ok: true })
})

// Bookmark toggle
app.post('/api/bookmark', (req, res) => {
  const { query } = req.body
  const p = store.profiles.find(p => p.query === query)
  if (!p) return res.status(404).json({ error: 'Not found' })
  p.bookmarked = !p.bookmarked
  store.pushed_at = new Date().toISOString(); saveToDisk()
  res.json({ ok: true, bookmarked: p.bookmarked })
})

// Flag toggle
app.post('/api/flag', (req, res) => {
  const { query } = req.body
  const p = store.profiles.find(p => p.query === query)
  if (!p) return res.status(404).json({ error: 'Not found' })
  p.flagged = !p.flagged
  store.pushed_at = new Date().toISOString(); saveToDisk()
  res.json({ ok: true, flagged: p.flagged })
})

app.listen(3001, () => {
  console.log('\n[bridge] 🏛️  GovTrack Bridge Server')
  console.log('[bridge] ✅ Running on http://localhost:3001')
  console.log('[bridge] Endpoints: /api/state /api/search /api/push /api/refresh /api/delete /api/note /api/bookmark /api/flag\n')
})
