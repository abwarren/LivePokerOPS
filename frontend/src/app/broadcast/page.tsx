'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'

interface Template {
  id: string
  name: string
  description: string | null
  category: string
  body_template: string
  variables: string[]
  is_builtin: boolean
  created_at: string
}

interface Broadcast {
  id: string
  template_id: string | null
  subject: string
  rendered_body: string
  status: string
  scheduled_for: string | null
  sent_at: string | null
  created_at: string
}

interface PlayerSummary {
  id: string
  first_name: string
  last_name: string
  nickname: string | null
  email: string
  phone: string | null
  is_active: boolean
}

export default function AdminDashboard() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'broadcast' | 'players' | 'history'>('broadcast')

  useEffect(() => {
    const t = localStorage.getItem('access_token')
    if (!t) {
      router.push('/login')
      return
    }
    setToken(t)
  }, [])

  function logout() {
    localStorage.removeItem('access_token')
    router.push('/login')
  }

  if (!token) return null

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">♠️ LivePokerOPS Admin</h1>
          <p className="text-sm text-gray-400 mt-1">Poker Club Operating System</p>
        </div>
        <button onClick={logout} className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 rounded-lg">
          Logout
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800 pb-px">
        <button
          onClick={() => setActiveTab('broadcast')}
          className={`px-4 py-2 text-sm rounded-t-lg ${
            activeTab === 'broadcast' ? 'bg-gray-800 text-green-400' : 'text-gray-500 hover:text-gray-300'
          }`}
        >📢 Broadcast</button>
        <button
          onClick={() => setActiveTab('players')}
          className={`px-4 py-2 text-sm rounded-t-lg ${
            activeTab === 'players' ? 'bg-gray-800 text-green-400' : 'text-gray-500 hover:text-gray-300'
          }`}
        >👥 Players</button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 text-sm rounded-t-lg ${
            activeTab === 'history' ? 'bg-gray-800 text-green-400' : 'text-gray-500 hover:text-gray-300'
          }`}
        >📜 Broadcast History</button>
      </div>

      {activeTab === 'broadcast' && <BroadcastTab token={token} />}
      {activeTab === 'players' && <PlayersTab token={token} />}
      {activeTab === 'history' && <HistoryTab token={token} />}
    </div>
  )
}

/* ─── BROADCAST TAB ─── */

function BroadcastTab({ token }: { token: string }) {
  const router = useRouter()
  const [templates, setTemplates] = useState<Template[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null)
  const [variables, setVariables] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState('')
  const [subject, setSubject] = useState('')
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState('')
  const [filterCategory, setFilterCategory] = useState('all')

  useEffect(() => {
    loadTemplates()
  }, [])

  async function loadTemplates() {
    try {
      const data = await api('/api/v1/broadcast/templates', {
        headers: { Authorization: `Bearer ${token}` },
      })
      setTemplates(data)
    } catch {
      router.push('/login')
    }
  }

  function handleTemplateSelect(id: string) {
    if (id === '__manual__') {
      setSelectedTemplate(null)
      setPreview('')
      setSubject('Custom Message')
      setVariables({})
      return
    }
    const tmpl = templates.find(t => t.id === id) || null
    setSelectedTemplate(tmpl)
    setPreview('')
    if (tmpl) {
      const vars: Record<string, string> = {}
      tmpl.variables.forEach(v => { vars[v] = '' })
      setVariables(vars)
      setSubject(tmpl.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()))
    } else {
      setVariables({})
      setSubject('')
    }
  }

  async function handlePreview() {
    if (!selectedTemplate) return
    try {
      const data = await api('/api/v1/broadcast/preview', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: selectedTemplate.id, variables }),
      })
      setPreview(data.rendered_body)
    } catch (err: any) {
      setStatus('Preview failed: ' + err.message)
    }
  }

  async function handleSend() {
    if (!selectedTemplate) return
    setSending(true)
    setStatus('')
    try {
      const data = await api('/api/v1/broadcast/send', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: selectedTemplate.id, variables, subject }),
      })
      setStatus(`✅ Broadcast sent! ID: ${data.id.slice(0, 8)}...`)
    } catch (err: any) {
      setStatus('❌ Send failed: ' + err.message)
    } finally {
      setSending(false)
    }
  }

  async function handleSendManual() {
    if (!subject.trim() || !preview.trim()) return
    setSending(true)
    setStatus('')
    try {
      const data = await api('/api/v1/broadcast/send-manual', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ subject, body: preview }),
      })
      setStatus(`✅ Sent! ID: ${data.id.slice(0, 8)}...`)
    } catch (err: any) {
      setStatus('❌ Send failed: ' + err.message)
    } finally {
      setSending(false)
    }
  }

  const categories = [
    { id: 'all', name: 'All' },
    { id: 'announcement', name: '📢 Announce' },
    { id: 'game_on', name: '🎯 Game On' },
    { id: 'final_table', name: '🏆 Final' },
    { id: 'results', name: '📊 Results' },
    { id: 'reminder', name: '⏰ Remind' },
  ]
  const filteredTemplates = filterCategory === 'all' ? templates : templates.filter(t => t.category === filterCategory)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-2 space-y-3">
        <div className="flex flex-wrap gap-1.5">
          {categories.map(cat => (
            <button key={cat.id} onClick={() => setFilterCategory(cat.id)}
              className={`px-2.5 py-1 text-xs rounded-full ${
                filterCategory === cat.id ? 'bg-green-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}>{cat.name}</button>
          ))}
        </div>
        <div className="space-y-1.5 max-h-[65vh] overflow-y-auto pr-1">
          {filteredTemplates.map(tmpl => (
            <button key={tmpl.id} onClick={() => handleTemplateSelect(tmpl.id)}
              className={`w-full text-left p-2.5 rounded-lg border transition-colors ${
                selectedTemplate?.id === tmpl.id ? 'border-green-500 bg-green-900/20' : 'border-gray-800 bg-gray-900 hover:border-gray-700'
              }`}>
              <div className="flex items-center justify-between">
                <div className="font-medium text-sm">{tmpl.name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</div>
                {tmpl.is_builtin && <span className="text-[10px] text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">built-in</span>}
              </div>
              {tmpl.description && <div className="text-xs text-gray-500 mt-0.5 truncate">{tmpl.description}</div>}
              <div className="text-[10px] text-gray-600 mt-0.5">{tmpl.variables.length} variables</div>
            </button>
          ))}
          <button onClick={() => handleTemplateSelect('__manual__')}
            className={`w-full text-left p-2.5 rounded-lg border border-dashed transition-colors border-gray-800 bg-gray-900 hover:border-gray-700`}>
            <div className="font-medium text-sm">✏️ Custom Message</div>
            <div className="text-xs text-gray-500 mt-0.5">Override — write anything</div>
          </button>
        </div>
      </div>
      <div className="lg:col-span-3 space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Subject</label>
          <input type="text" value={subject} onChange={e => setSubject(e.target.value)}
            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-green-500 text-white text-sm"
            placeholder="Tournament Announcement" />
        </div>
        {selectedTemplate && Object.keys(variables).length > 0 && (
          <div className="space-y-2">
            <label className="block text-sm text-gray-400">Variables</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(variables).map(([key, val]) => (
                <div key={key}>
                  <label className="block text-xs text-gray-500 mb-0.5">{key}</label>
                  <input type="text" value={val} onChange={e => setVariables(prev => ({ ...prev, [key]: e.target.value }))}
                    className="w-full px-2.5 py-1.5 bg-gray-800 border border-gray-700 rounded focus:outline-none focus:border-green-500 text-white text-xs"
                    placeholder={`Enter ${key}...`} />
                </div>
              ))}
            </div>
          </div>
        )}
        {!selectedTemplate && (
          <div>
            <label className="block text-sm text-gray-400 mb-1">Message Body</label>
            <textarea value={preview} onChange={e => setPreview(e.target.value)} rows={8}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-green-500 text-white text-sm font-mono"
              placeholder="Type your message..." />
          </div>
        )}
        <div className="flex gap-2">
          {selectedTemplate && <button onClick={handlePreview} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm">👁 Preview</button>}
          {selectedTemplate && <button onClick={handleSend} disabled={sending}
            className="px-5 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 rounded-lg text-sm font-medium">
            {sending ? 'Sending...' : '📨 Send to WhatsApp'}
          </button>}
          {!selectedTemplate && preview && <button onClick={handleSendManual} disabled={sending}
            className="px-5 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 rounded-lg text-sm font-medium">
            {sending ? 'Sending...' : '📨 Send'}
          </button>}
        </div>
        {status && <div className="p-3 bg-gray-800 border border-gray-700 rounded-lg text-sm">{status}</div>}
        {preview && selectedTemplate && (
          <div>
            <label className="block text-sm text-gray-400 mb-1">Preview</label>
            <div className="p-4 bg-gray-800 border border-gray-700 rounded-xl whitespace-pre-wrap text-sm leading-relaxed">{preview}</div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ─── PLAYERS TAB ─── */

function PlayersTab({ token }: { token: string }) {
  const [players, setPlayers] = useState<PlayerSummary[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [uploadStatus, setUploadStatus] = useState('')
  const [uploading, setUploading] = useState(false)
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number; errors: string[] } | null>(null)

  useEffect(() => {
    loadPlayers()
    loadCount()
  }, [])

  async function loadPlayers(q?: string) {
    try {
      const url = q ? `/api/v1/players/?search=${encodeURIComponent(q)}` : '/api/v1/players/'
      const data = await api(url, { headers: { Authorization: `Bearer ${token}` } })
      setPlayers(data)
    } catch { /* ignore */ }
  }

  async function loadCount() {
    try {
      const data = await api('/api/v1/players/count', { headers: { Authorization: `Bearer ${token}` } })
      setTotal(data.total)
    } catch { /* ignore */ }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setUploadStatus('')
    setImportResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch('http://localhost:8000/api/v1/players/import-csv', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json()
        setUploadStatus(`❌ ${err.detail || 'Upload failed'}`)
        return
      }

      const result = await res.json()
      setImportResult(result)
      setUploadStatus(`✅ ${result.imported} imported, ${result.skipped} skipped`)
      loadPlayers()
      loadCount()
    } catch (err: any) {
      setUploadStatus('❌ Upload error: ' + err.message)
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  return (
    <div className="space-y-6">
      {/* Stats + Search */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-400">Total players: <span className="text-white font-medium">{total}</span></div>
        <div className="flex gap-2">
          <input type="text" value={search} onChange={e => { setSearch(e.target.value); loadPlayers(e.target.value) }}
            placeholder="Search players..."
            className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white w-48" />
        </div>
      </div>

      {/* CSV Upload */}
      <div className="p-4 bg-gray-900 border border-gray-800 rounded-lg">
        <h3 className="font-medium text-sm mb-2">📥 Import Players from CSV</h3>
        <p className="text-xs text-gray-500 mb-3">
          CSV must have columns: <code className="text-green-400">first_name</code>, <code className="text-green-400">last_name</code>, <code className="text-green-400">phone</code>.
          Optional: <code className="text-gray-400">email</code>, <code className="text-gray-400">nickname</code>.
        </p>
        <div className="flex items-center gap-3">
          <label className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium cursor-pointer">
            {uploading ? 'Uploading...' : 'Choose CSV File'}
            <input type="file" accept=".csv" onChange={handleFileUpload} className="hidden" disabled={uploading} />
          </label>
          {uploadStatus && <span className="text-sm text-gray-300">{uploadStatus}</span>}
        </div>
        {importResult && importResult.errors.length > 0 && (
          <div className="mt-2 text-xs text-yellow-400">
            {importResult.errors.slice(0, 5).map((e, i) => <div key={i}>{e}</div>)}
            {importResult.errors.length > 5 && <div>...and {importResult.errors.length - 5} more</div>}
          </div>
        )}
      </div>

      {/* Player List */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-2 px-2">Name</th>
              <th className="text-left py-2 px-2">Phone</th>
              <th className="text-left py-2 px-2">Email</th>
              <th className="text-center py-2 px-2">Active</th>
            </tr>
          </thead>
          <tbody>
            {players.map(p => (
              <tr key={p.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-2 px-2">{p.first_name} {p.last_name}{p.nickname ? ` (${p.nickname})` : ''}</td>
                <td className="py-2 px-2 text-gray-400">{p.phone || '-'}</td>
                <td className="py-2 px-2 text-gray-400">{p.email}</td>
                <td className="py-2 px-2 text-center">{p.is_active ? '✅' : '❌'}</td>
              </tr>
            ))}
            {players.length === 0 && (
              <tr><td colSpan={4} className="py-8 text-center text-gray-500">No players found. Import a CSV to get started.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ─── HISTORY TAB ─── */

function HistoryTab({ token }: { token: string }) {
  const [history, setHistory] = useState<Broadcast[]>([])

  useEffect(() => {
    loadHistory()
  }, [])

  async function loadHistory() {
    try {
      const data = await api('/api/v1/broadcast/history?limit=50', {
        headers: { Authorization: `Bearer ${token}` },
      })
      setHistory(data)
    } catch { /* ignore */ }
  }

  if (history.length === 0) {
    return <div className="text-center py-12 text-gray-500">No broadcasts sent yet.</div>
  }

  return (
    <div className="space-y-2">
      {history.map(b => (
        <div key={b.id} className="p-4 bg-gray-900 border border-gray-800 rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <div className="font-medium text-sm">{b.subject}</div>
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              b.status === 'sent' ? 'bg-green-900/50 text-green-400' :
              b.status === 'failed' ? 'bg-red-900/50 text-red-400' :
              b.status === 'scheduled' ? 'bg-blue-900/50 text-blue-400' :
              'bg-gray-800 text-gray-400'
            }`}>{b.status}</span>
          </div>
          <div className="text-xs text-gray-500 mb-2">{new Date(b.created_at).toLocaleString()}{b.sent_at && ` • Sent: ${new Date(b.sent_at).toLocaleString()}`}</div>
          <div className="text-xs text-gray-400 whitespace-pre-wrap line-clamp-3">{b.rendered_body}</div>
        </div>
      ))}
    </div>
  )
}
