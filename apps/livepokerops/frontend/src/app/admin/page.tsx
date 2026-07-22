'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

interface DashboardSummary {
  total_players: number
  total_tournaments: number
  tournaments_by_status: Record<string, number>
  upcoming_tournaments: number
}

export default function AdminPage() {
  const router = useRouter()
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    const t = localStorage.getItem('access_token')
    if (!t) { router.push('/login'); return }
    setToken(t)
  }, [])

  if (!token) return null

  return <AdminDashboard token={token} />
}

function AdminDashboard({ token }: { token: string }) {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState<string>('dashboard')

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    router.push('/login')
  }

  const tabs = [
    { id: 'dashboard', label: '📊 Dashboard' },
    { id: 'tournaments', label: '🏟 Tournaments' },
    { id: 'players', label: '👥 Players' },
    { id: 'rsvp', label: '📝 RSVP' },
    { id: 'attendance', label: '✅ Attendance' },
    { id: 'broadcast', label: '📢 Broadcast' },
    { id: 'league', label: '🏆 League' },
    { id: 'finances', label: '💰 Finances' },
    { id: 'archive', label: '📚 Archive' },
    { id: 'history', label: '📜 History' },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">♠️ LivePokerOPS</h1>
          <p className="text-sm text-gray-400 mt-1">Poker Club Operating System</p>
        </div>
        <button onClick={logout} className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 rounded-lg">
          Logout
        </button>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-0.5 border-b border-gray-800 pb-px overflow-x-auto">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-3 py-2 text-sm whitespace-nowrap rounded-t-lg transition-colors ${
              activeTab === t.id
                ? 'bg-gray-800 text-green-400 border-b-2 border-green-500'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'dashboard' && <DashboardTab token={token} />}
      {activeTab === 'tournaments' && <TournamentsTab token={token} />}
      {activeTab === 'players' && <PlayersTab token={token} />}
      {activeTab === 'rsvp' && <RsvpTab token={token} />}
      {activeTab === 'attendance' && <AttendanceTab token={token} />}
      {activeTab === 'broadcast' && <BroadcastComposeTab token={token} />}
      {activeTab === 'league' && <LeagueTab token={token} />}
      {activeTab === 'finances' && <FinancesTab token={token} />}
      {activeTab === 'archive' && <ArchiveTab token={token} />}
      {activeTab === 'history' && <HistoryTab token={token} />}
    </div>
  )
}

/* ═══════════════════════════════════════════════
   DASHBOARD TAB
   ═══════════════════════════════════════════════ */

function DashboardTab({ token }: { token: string }) {
  const [data, setData] = useState<DashboardSummary | null>(null)

  useEffect(() => {
    api('/api/v1/analytics/dashboard', { headers: { Authorization: `Bearer ${token}` } })
      .then(setData)
      .catch(() => {})
  }, [])

  if (!data) {
    return <div className="text-center py-12 text-gray-500">Loading dashboard...</div>
  }

  const statusColors: Record<string, string> = {
    planned: 'bg-blue-900/50 text-blue-400',
    announced: 'bg-purple-900/50 text-purple-400',
    in_progress: 'bg-green-900/50 text-green-400',
    completed: 'bg-gray-800 text-gray-400',
    cancelled: 'bg-red-900/50 text-red-400',
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Players" value={data.total_players} icon="👥" />
        <StatCard label="Total Tournaments" value={data.total_tournaments} icon="🏟" />
        <StatCard label="Upcoming (7d)" value={data.upcoming_tournaments} icon="📅" />
        <StatCard label="Completed" value={data.tournaments_by_status?.completed || 0} icon="✅" />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h3 className="font-semibold mb-3">Tournaments by Status</h3>
        <div className="space-y-2">
          {Object.entries(data.tournaments_by_status || {}).map(([status, count]) => (
            <div key={status} className="flex items-center justify-between">
              <span className={`text-sm px-2 py-0.5 rounded-full ${statusColors[status] || 'bg-gray-800 text-gray-400'}`}>
                {status.replace(/_/g, ' ')}
              </span>
              <span className="text-lg font-bold">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, icon }: { label: string; value: number; icon: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="text-2xl mb-1">{icon}</div>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm text-gray-400 mt-1">{label}</div>
    </div>
  )
}

/* ═══════════════════════════════════════════════
   TOURNAMENTS TAB
   ═══════════════════════════════════════════════ */

function TournamentsTab({ token }: { token: string }) {
  const [tournaments, setTournaments] = useState<any[]>([])
  const [creating, setCreating] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ name: '', buy_in: '', starting_stack: '', min_players: '', max_players: '', late_reg_levels: '4', notes: '' })
  const [status, setStatus] = useState('')

  useEffect(() => { load() }, [])

  async function load() {
    try {
      const data = await api('/api/v1/tournaments/', { headers: { Authorization: `Bearer ${token}` } })
      setTournaments(data)
    } catch { /* ignore */ }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    setStatus('')
    try {
      await api('/api/v1/tournaments/', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: {
          name: form.name,
          buy_in: form.buy_in ? parseFloat(form.buy_in) : undefined,
          starting_stack: form.starting_stack ? parseInt(form.starting_stack) : undefined,
          min_players: form.min_players ? parseInt(form.min_players) : undefined,
          max_players: form.max_players ? parseInt(form.max_players) : undefined,
          late_reg_levels: parseInt(form.late_reg_levels) || 4,
          notes: form.notes || undefined,
        },
      })
      setForm({ name: '', buy_in: '', starting_stack: '', min_players: '', max_players: '', late_reg_levels: '4', notes: '' })
      setCreating(false)
      setStatus('✅ Tournament created')
      load()
    } catch (err: any) { setStatus('❌ ' + err.message) }
  }

  async function handleUpdateStatus(tid: string, newStatus: string) {
    try {
      await api(`/api/v1/tournaments/${tid}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        body: { status: newStatus },
      })
      load()
    } catch { /* ignore */ }
  }

  const statusColors: Record<string, string> = {
    planned: 'bg-blue-900/50 text-blue-400',
    announced: 'bg-purple-900/50 text-purple-400',
    in_progress: 'bg-green-900/50 text-green-400',
    completed: 'bg-gray-700 text-gray-300',
    cancelled: 'bg-red-900/50 text-red-400',
    paused: 'bg-yellow-900/50 text-yellow-400',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-400">{tournaments.length} tournaments</span>
        <button onClick={() => setCreating(!creating)} className="px-4 py-1.5 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium">
          {creating ? 'Cancel' : '+ New Tournament'}
        </button>
      </div>

      {creating && (
        <form onSubmit={handleCreate} className="p-5 bg-gray-900 border border-gray-800 rounded-xl space-y-3">
          <h3 className="font-semibold">Create Tournament</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Name *</label>
              <input type="text" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} required
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Buy-in (R)</label>
              <input type="number" step="0.01" value={form.buy_in} onChange={e => setForm(p => ({ ...p, buy_in: e.target.value }))}
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Starting Stack</label>
              <input type="number" value={form.starting_stack} onChange={e => setForm(p => ({ ...p, starting_stack: e.target.value }))}
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Min Players</label>
              <input type="number" value={form.min_players} onChange={e => setForm(p => ({ ...p, min_players: e.target.value }))}
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Max Players</label>
              <input type="number" value={form.max_players} onChange={e => setForm(p => ({ ...p, max_players: e.target.value }))}
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Late Reg Levels</label>
              <input type="number" value={form.late_reg_levels} onChange={e => setForm(p => ({ ...p, late_reg_levels: e.target.value }))}
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-0.5">Notes</label>
            <textarea value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} rows={2}
              className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white" />
          </div>
          <button type="submit" className="px-4 py-1.5 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium">Create Tournament</button>
          {status && <div className="text-sm">{status}</div>}
        </form>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-2 px-2">Name</th>
              <th className="text-left py-2 px-2">Status</th>
              <th className="text-right py-2 px-2">Buy-in</th>
              <th className="text-right py-2 px-2">Stack</th>
              <th className="text-center py-2 px-2">Players</th>
              <th className="text-center py-2 px-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tournaments.map((t: any) => (
              <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-2 px-2 font-medium">{t.name}</td>
                <td className="py-2 px-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[t.status] || 'bg-gray-800'}`}>
                    {t.status.replace(/_/g, ' ')}
                  </span>
                </td>
                <td className="py-2 px-2 text-right">{t.buy_in ? `R${t.buy_in}` : '-'}</td>
                <td className="py-2 px-2 text-right text-gray-400">{t.starting_stack?.toLocaleString() || '-'}</td>
                <td className="py-2 px-2 text-center text-gray-400">{t.min_players || '?'}-{t.max_players || '?'}</td>
                <td className="py-2 px-2 text-center">
                  <select
                    value={t.status}
                    onChange={e => handleUpdateStatus(t.id, e.target.value)}
                    className="bg-gray-800 border border-gray-700 rounded text-xs px-1.5 py-1 text-white focus:outline-none focus:border-green-500"
                  >
                    <option value="planned">Planned</option>
                    <option value="announced">Announced</option>
                    <option value="in_progress">In Progress</option>
                    <option value="paused">Paused</option>
                    <option value="completed">Completed</option>
                    <option value="cancelled">Cancelled</option>
                  </select>
                </td>
              </tr>
            ))}
            {tournaments.length === 0 && (
              <tr><td colSpan={6} className="py-8 text-center text-gray-500">No tournaments yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════
   PLAYERS TAB
   ═══════════════════════════════════════════════ */

function PlayersTab({ token }: { token: string }) {
  const [players, setPlayers] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [uploadStatus, setUploadStatus] = useState('')
  const [uploading, setUploading] = useState(false)
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number; errors: string[] } | null>(null)

  useEffect(() => { loadPlayers(); loadCount() }, [])

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
    setUploading(true); setUploadStatus(''); setImportResult(null)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch('http://localhost:8000/api/v1/players/import-csv', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      })
      if (!res.ok) { const err = await res.json(); setUploadStatus(`❌ ${err.detail || 'Upload failed'}`); return }
      const result = await res.json()
      setImportResult(result)
      setUploadStatus(`✅ ${result.imported} imported, ${result.skipped} skipped`)
      loadPlayers(); loadCount()
    } catch (err: any) { setUploadStatus('❌ Upload error: ' + err.message) }
    finally { setUploading(false); e.target.value = '' }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-400">Total: <span className="text-white font-medium">{total}</span></div>
        <input type="text" value={search} onChange={e => { setSearch(e.target.value); loadPlayers(e.target.value) }}
          placeholder="Search players..." className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white w-48" />
      </div>

      <div className="p-4 bg-gray-900 border border-gray-800 rounded-lg">
        <h3 className="font-medium text-sm mb-2">📥 Import Players from CSV</h3>
        <p className="text-xs text-gray-500 mb-3">CSV: <code className="text-green-400">first_name</code>, <code className="text-green-400">last_name</code>, <code className="text-green-400">phone</code>. Optional: email, nickname.</p>
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

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left py-2 px-2">Name</th>
              <th className="text-left py-2 px-2">Nickname</th>
              <th className="text-left py-2 px-2">Phone</th>
              <th className="text-left py-2 px-2">Email</th>
              <th className="text-center py-2 px-2">Active</th>
            </tr>
          </thead>
          <tbody>
            {players.map((p: any) => (
              <tr key={p.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-2 px-2 font-medium">{p.first_name} {p.last_name}</td>
                <td className="py-2 px-2 text-gray-400">{p.nickname || '-'}</td>
                <td className="py-2 px-2 text-gray-400">{p.phone || '-'}</td>
                <td className="py-2 px-2 text-gray-400 text-xs">{p.email}</td>
                <td className="py-2 px-2 text-center">{p.is_active ? '✅' : '❌'}</td>
              </tr>
            ))}
            {players.length === 0 && (
              <tr><td colSpan={5} className="py-8 text-center text-gray-500">No players found.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════
   RSVP TAB
   ═══════════════════════════════════════════════ */

function RsvpTab({ token }: { token: string }) {
  const [tournaments, setTournaments] = useState<any[]>([])
  const [selectedTid, setSelectedTid] = useState<string>('')
  const [rsvps, setRsvps] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [status, setStatus] = useState('')

  useEffect(() => {
    api('/api/v1/tournaments/', { headers: { Authorization: `Bearer ${token}` } })
      .then(setTournaments)
      .catch(() => {})
  }, [])

  async function loadRsvps(tid: string) {
    if (!tid) return
    setSelectedTid(tid)
    try {
      const [rsvpData, statsData] = await Promise.all([
        api(`/api/v1/tournaments/${tid}/rsvps`, { headers: { Authorization: `Bearer ${token}` } }),
        api(`/api/v1/tournaments/${tid}/rsvps/stats`, { headers: { Authorization: `Bearer ${token}` } }),
      ])
      setRsvps(rsvpData)
      setStats(statsData)
    } catch { setRsvps([]); setStats(null) }
  }

  async function updateRsvpStatus(playerId: string, newStatus: string) {
    try {
      await api(`/api/v1/tournaments/${selectedTid}/rsvps/${playerId}`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
        body: { status: newStatus },
      })
      setStatus(`✅ Updated → ${newStatus}`)
      loadRsvps(selectedTid)
    } catch (err: any) { setStatus('❌ ' + err.message) }
  }

  const rsvpColors: Record<string, string> = {
    confirmed: 'bg-green-900/50 text-green-400',
    waiting: 'bg-yellow-900/50 text-yellow-400',
    cancelled: 'bg-red-900/50 text-red-400',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Tournament:</label>
        <select value={selectedTid} onChange={e => loadRsvps(e.target.value)} className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white">
          <option value="">Select...</option>
          {tournaments.map((t: any) => (
            <option key={t.id} value={t.id}>{t.name} ({t.status})</option>
          ))}
        </select>
      </div>

      {stats && (
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-400">{stats.total_confirmed}</div>
            <div className="text-xs text-gray-400">Confirmed</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-yellow-400">{stats.total_waiting}</div>
            <div className="text-xs text-gray-400">Waitlist</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-red-400">{stats.total_cancelled}</div>
            <div className="text-xs text-gray-400">Cancelled</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{stats.capacity_remaining ?? '∞'}</div>
            <div className="text-xs text-gray-400">Spots Left</div>
          </div>
        </div>
      )}

      {status && <div className="text-sm">{status}</div>}

      {rsvps.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-2">Player</th>
                <th className="text-left py-2 px-2">Status</th>
                <th className="text-left py-2 px-2">Notes</th>
                <th className="text-center py-2 px-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rsvps.map((r: any) => (
                <tr key={r.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 px-2">{r.player_name}</td>
                  <td className="py-2 px-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${rsvpColors[r.status] || 'bg-gray-800'}`}>{r.status}</span>
                  </td>
                  <td className="py-2 px-2 text-gray-400 text-xs">{r.notes || '-'}</td>
                  <td className="py-2 px-2 text-center">
                    {r.status === 'waiting' && (
                      <button onClick={() => updateRsvpStatus(r.player_id, 'confirmed')} className="px-2 py-1 bg-green-700 rounded text-xs mr-1">Confirm</button>
                    )}
                    {r.status !== 'cancelled' && (
                      <button onClick={() => updateRsvpStatus(r.player_id, 'cancelled')} className="px-2 py-1 bg-red-700 rounded text-xs">Cancel</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selectedTid && rsvps.length === 0 && (
        <div className="text-center py-8 text-gray-500">No RSVPs for this tournament yet.</div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════
   ATTENDANCE TAB
   ═══════════════════════════════════════════════ */

function AttendanceTab({ token }: { token: string }) {
  const [tournaments, setTournaments] = useState<any[]>([])
  const [selectedTid, setSelectedTid] = useState<string>('')
  const [records, setRecords] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)

  useEffect(() => {
    api('/api/v1/tournaments/', { headers: { Authorization: `Bearer ${token}` } })
      .then(setTournaments)
      .catch(() => {})
  }, [])

  async function loadAttendance(tid: string) {
    if (!tid) return
    setSelectedTid(tid)
    try {
      const [attData, statsData] = await Promise.all([
        api(`/api/v1/tournaments/${tid}/attendance`, { headers: { Authorization: `Bearer ${token}` } }),
        api(`/api/v1/tournaments/${tid}/attendance/stats`, { headers: { Authorization: `Bearer ${token}` } }),
      ])
      setRecords(attData)
      setStats(statsData)
    } catch { setRecords([]); setStats(null) }
  }

  async function checkIn(playerId: string) {
    try {
      await api(`/api/v1/tournaments/${selectedTid}/attendance/check-in`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: { player_id: playerId },
      })
      loadAttendance(selectedTid)
    } catch { /* ignore */ }
  }

  const attColors: Record<string, string> = {
    checked_in: 'bg-green-900/50 text-green-400',
    no_show: 'bg-red-900/50 text-red-400',
    late_cancellation: 'bg-yellow-900/50 text-yellow-400',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Tournament:</label>
        <select value={selectedTid} onChange={e => loadAttendance(e.target.value)} className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white">
          <option value="">Select...</option>
          {tournaments.map((t: any) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>

      {stats && (
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-400">{stats.checked_in}</div>
            <div className="text-xs text-gray-400">Checked In</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-red-400">{stats.no_shows}</div>
            <div className="text-xs text-gray-400">No-shows</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{stats.check_in_rate || 0}%</div>
            <div className="text-xs text-gray-400">Check-in Rate</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold">{stats.total_players || 0}</div>
            <div className="text-xs text-gray-400">Total Players</div>
          </div>
        </div>
      )}

      {records.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-2">Player</th>
                <th className="text-left py-2 px-2">Status</th>
                <th className="text-left py-2 px-2">Time</th>
                <th className="text-center py-2 px-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {records.map((r: any) => (
                <tr key={r.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 px-2">{r.player_name}</td>
                  <td className="py-2 px-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${attColors[r.status] || 'bg-gray-800'}`}>{r.status}</span>
                  </td>
                  <td className="py-2 px-2 text-gray-400 text-xs">{r.checked_in_at ? new Date(r.checked_in_at).toLocaleString() : '-'}</td>
                  <td className="py-2 px-2 text-center">
                    {r.status !== 'checked_in' && <button onClick={() => checkIn(r.player_id)} className="px-2 py-1 bg-green-700 rounded text-xs">Check In</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════
   BROADCAST COMPOSE TAB
   ═══════════════════════════════════════════════ */

function BroadcastComposeTab({ token }: { token: string }) {
  const router = useRouter()
  const [templates, setTemplates] = useState<any[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<any | null>(null)
  const [variables, setVariables] = useState<Record<string, string>>({})
  const [preview, setPreview] = useState('')
  const [subject, setSubject] = useState('')
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState('')
  const [filterCategory, setFilterCategory] = useState('all')

  useEffect(() => {
    api('/api/v1/broadcast/templates', { headers: { Authorization: `Bearer ${token}` } })
      .then(setTemplates)
      .catch(() => router.push('/login'))
  }, [])

  function handleTemplateSelect(id: string) {
    if (id === '__manual__') {
      setSelectedTemplate(null); setPreview(''); setSubject('Custom Message'); setVariables({}); return
    }
    const tmpl = templates.find(t => t.id === id) || null
    setSelectedTemplate(tmpl); setPreview('')
    if (tmpl) {
      const vars: Record<string, string> = {}
      tmpl.variables.forEach((v: string) => { vars[v] = '' })
      setVariables(vars)
      setSubject(tmpl.name.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()))
    }
  }

  async function handlePreview() {
    if (!selectedTemplate) return
    try {
      const data = await api('/api/v1/broadcast/preview', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: { template_id: selectedTemplate.id, variables },
      })
      setPreview(data.rendered_body)
    } catch (err: any) { setStatus('Preview failed: ' + err.message) }
  }

  async function handleSend() {
    if (!selectedTemplate) return
    setSending(true); setStatus('')
    try {
      const data = await api('/api/v1/broadcast/send', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: { template_id: selectedTemplate.id, variables, subject, player_ids: [] },
      })
      setStatus(`✅ Broadcast sent! ID: ${data.id.slice(0, 8)}...`)
    } catch (err: any) { setStatus('❌ ' + err.message) }
    finally { setSending(false) }
  }

  async function handleSendManual() {
    if (!subject.trim() || !preview.trim()) return
    setSending(true); setStatus('')
    try {
      const data = await api('/api/v1/broadcast/send-manual', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: { subject, body: preview, player_ids: [] },
      })
      setStatus(`✅ Sent! ID: ${data.id.slice(0, 8)}...`)
    } catch (err: any) { setStatus('❌ ' + err.message) }
    finally { setSending(false) }
  }

  const categories = [
    { id: 'all', name: 'All' }, { id: 'announcement', name: '📢 Announce' },
    { id: 'game_on', name: '🎯 Game On' }, { id: 'final_table', name: '🏆 Final' },
    { id: 'results', name: '📊 Results' }, { id: 'reminder', name: '⏰ Remind' },
  ]
  const filtered = filterCategory === 'all' ? templates : templates.filter((t: any) => t.category === filterCategory)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <div className="lg:col-span-2 space-y-3">
        <div className="flex flex-wrap gap-1.5">
          {categories.map(cat => (
            <button key={cat.id} onClick={() => setFilterCategory(cat.id)}
              className={`px-2.5 py-1 text-xs rounded-full ${filterCategory === cat.id ? 'bg-green-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}>
              {cat.name}
            </button>
          ))}
        </div>
        <div className="space-y-1.5 max-h-[65vh] overflow-y-auto pr-1">
          {filtered.map((tmpl: any) => (
            <button key={tmpl.id} onClick={() => handleTemplateSelect(tmpl.id)}
              className={`w-full text-left p-2.5 rounded-lg border transition-colors ${
                selectedTemplate?.id === tmpl.id ? 'border-green-500 bg-green-900/20' : 'border-gray-800 bg-gray-900 hover:border-gray-700'
              }`}>
              <div className="flex items-center justify-between">
                <div className="font-medium text-sm">{tmpl.name.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}</div>
                {tmpl.is_builtin && <span className="text-[10px] text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">built-in</span>}
              </div>
              {tmpl.description && <div className="text-xs text-gray-500 mt-0.5 truncate">{tmpl.description}</div>}
              <div className="text-[10px] text-gray-600 mt-0.5">{tmpl.variables.length} variables</div>
            </button>
          ))}
          <button onClick={() => handleTemplateSelect('__manual__')}
            className="w-full text-left p-2.5 rounded-lg border border-dashed border-gray-800 bg-gray-900 hover:border-gray-700">
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
          {selectedTemplate && (
            <button onClick={handleSend} disabled={sending}
              className="px-5 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 rounded-lg text-sm font-medium">
              {sending ? 'Sending...' : '📨 Send to WhatsApp'}
            </button>
          )}
          {!selectedTemplate && preview && (
            <button onClick={handleSendManual} disabled={sending}
              className="px-5 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-800 rounded-lg text-sm font-medium">
              {sending ? 'Sending...' : '📨 Send'}
            </button>
          )}
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

/* ═══════════════════════════════════════════════
   LEAGUE TAB
   ═══════════════════════════════════════════════ */

function LeagueTab({ token }: { token: string }) {
  const [seasons, setSeasons] = useState<any[]>([])
  const [selectedSeason, setSelectedSeason] = useState<string>('')
  const [leaderboard, setLeaderboard] = useState<any>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ name: '', start_date: '', end_date: '', description: '' })
  const [status, setStatus] = useState('')

  useEffect(() => { loadSeasons() }, [])

  async function loadSeasons() {
    try {
      const data = await api('/api/v1/league/seasons', { headers: { Authorization: `Bearer ${token}` } })
      setSeasons(data)
    } catch { /* ignore */ }
  }

  async function loadLeaderboard(sid: string) {
    setSelectedSeason(sid)
    try {
      const data = await api(`/api/v1/league/seasons/${sid}/leaderboard`, { headers: { Authorization: `Bearer ${token}` } })
      setLeaderboard(data)
    } catch { setLeaderboard(null) }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault(); setStatus('')
    try {
      await api('/api/v1/league/seasons', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: { name: form.name, start_date: form.start_date, end_date: form.end_date, description: form.description || undefined },
      })
      setForm({ name: '', start_date: '', end_date: '', description: '' })
      setCreating(false)
      setStatus('✅ Season created')
      loadSeasons()
    } catch (err: any) { setStatus('❌ ' + err.message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <label className="text-sm text-gray-400">Season:</label>
          <select value={selectedSeason} onChange={e => loadLeaderboard(e.target.value)} className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white">
            <option value="">Select...</option>
            {seasons.map((s: any) => (
              <option key={s.id} value={s.id}>{s.name} ({s.status})</option>
            ))}
          </select>
        </div>
        <button onClick={() => setCreating(!creating)} className="px-4 py-1.5 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium">
          {creating ? 'Cancel' : '+ New Season'}
        </button>
      </div>

      {creating && (
        <form onSubmit={handleCreate} className="p-5 bg-gray-900 border border-gray-800 rounded-xl space-y-3">
          <h3 className="font-semibold">Create Season</h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Name *</label>
              <input type="text" value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} required
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">Start Date</label>
              <input type="date" value={form.start_date} onChange={e => setForm(p => ({ ...p, start_date: e.target.value }))} required
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-0.5">End Date</label>
              <input type="date" value={form.end_date} onChange={e => setForm(p => ({ ...p, end_date: e.target.value }))} required
                className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-0.5">Description</label>
            <textarea value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} rows={2}
              className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white" />
          </div>
          <button type="submit" className="px-4 py-1.5 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium">Create Season</button>
          {status && <div className="text-sm">{status}</div>}
        </form>
      )}

      {leaderboard && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-center py-2 px-2 w-10">#</th>
                <th className="text-left py-2 px-2">Player</th>
                <th className="text-right py-2 px-2">Points</th>
                <th className="text-right py-2 px-2">Played</th>
                <th className="text-right py-2 px-2">FTs</th>
                <th className="text-right py-2 px-2">Best</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.entries.map((e: any) => (
                <tr key={e.player_id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="text-center py-2 px-2 font-bold text-lg">{e.rank <= 3 ? ['🥇','🥈','🥉'][e.rank-1] : e.rank}</td>
                  <td className="py-2 px-2">{e.player_name}{e.nickname ? ` (${e.nickname})` : ''}</td>
                  <td className="py-2 px-2 text-right font-bold text-green-400">{e.total_points}</td>
                  <td className="py-2 px-2 text-right text-gray-400">{e.tournaments_played}</td>
                  <td className="py-2 px-2 text-right text-gray-400">{e.final_table_count}</td>
                  <td className="py-2 px-2 text-right text-gray-400">{e.best_position ? `#${e.best_position}` : '-'}</td>
                </tr>
              ))}
              {leaderboard.entries.length === 0 && (
                <tr><td colSpan={6} className="py-8 text-center text-gray-500">No points recorded yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════
   FINANCES TAB
   ═══════════════════════════════════════════════ */

function FinancesTab({ token }: { token: string }) {
  const [tournaments, setTournaments] = useState<any[]>([])
  const [selectedTid, setSelectedTid] = useState<string>('')
  const [buyIns, setBuyIns] = useState<any[]>([])
  const [prizePool, setPrizePool] = useState<any>(null)

  useEffect(() => {
    api('/api/v1/tournaments/', { headers: { Authorization: `Bearer ${token}` } })
      .then(setTournaments)
      .catch(() => {})
  }, [])

  async function loadFinances(tid: string) {
    if (!tid) return
    setSelectedTid(tid)
    try {
      const [buyInData, poolData] = await Promise.all([
        api(`/api/v1/tournaments/${tid}/finances/buy-ins`, { headers: { Authorization: `Bearer ${token}` } }),
        api(`/api/v1/tournaments/${tid}/finances/prize-pool`, { headers: { Authorization: `Bearer ${token}` } }),
      ])
      setBuyIns(buyInData)
      setPrizePool(poolData)
    } catch { setBuyIns([]); setPrizePool(null) }
  }

  const typeColors: Record<string, string> = {
    buy_in: 'bg-green-900/50 text-green-400',
    re_buy: 'bg-yellow-900/50 text-yellow-400',
    add_on: 'bg-blue-900/50 text-blue-400',
    prize_payout: 'bg-red-900/50 text-red-400',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-sm text-gray-400">Tournament:</label>
        <select value={selectedTid} onChange={e => loadFinances(e.target.value)} className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white">
          <option value="">Select...</option>
          {tournaments.map((t: any) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>

      {prizePool && (
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-green-400">R{prizePool.total_prize_pool?.toFixed(2) || '0.00'}</div>
            <div className="text-xs text-gray-400">Total Prize Pool</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-lg font-bold">R{prizePool.total_buy_in?.toFixed(2) || '0.00'}</div>
            <div className="text-xs text-gray-400">Buy-ins</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-lg font-bold">R{prizePool.total_rebuys?.toFixed(2) || '0.00'}</div>
            <div className="text-xs text-gray-400">Re-buys</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 text-center">
            <div className="text-lg font-bold">{prizePool.entries_count || 0}</div>
            <div className="text-xs text-gray-400">Entries</div>
          </div>
        </div>
      )}

      {buyIns.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 border-b border-gray-800">
                <th className="text-left py-2 px-2">Player</th>
                <th className="text-left py-2 px-2">Type</th>
                <th className="text-right py-2 px-2">Amount</th>
                <th className="text-left py-2 px-2">Notes</th>
              </tr>
            </thead>
            <tbody>
              {buyIns.map((b: any) => (
                <tr key={b.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                  <td className="py-2 px-2">{b.player_name}</td>
                  <td className="py-2 px-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${typeColors[b.type] || 'bg-gray-800'}`}>
                      {b.type.replace(/_/g, ' ')}
                    </span>
                  </td>
                  <td className="py-2 px-2 text-right font-medium">R{parseFloat(b.amount).toFixed(2)}</td>
                  <td className="py-2 px-2 text-gray-400 text-xs">{b.notes || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {selectedTid && buyIns.length === 0 && (
        <div className="text-center py-8 text-gray-500">No financial records for this tournament.</div>
      )}
    </div>
  )
}

/* ═══════════════════════════════════════════════
   ARCHIVE TAB
   ═══════════════════════════════════════════════ */

function ArchiveTab({ token }: { token: string }) {
  const [results, setResults] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(false)

  async function doSearch() {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (search) params.set('q', search)
      if (statusFilter) params.set('status', statusFilter)

      const data = await api(`/api/v1/tournaments/archive/search?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      setResults(data.results)
      setTotal(data.total)
    } catch { setResults([]); setTotal(0) }
    finally { setLoading(false) }
  }

  useEffect(() => { doSearch() }, [])

  const statusColors: Record<string, string> = {
    planned: 'bg-blue-900/50 text-blue-400',
    announced: 'bg-purple-900/50 text-purple-400',
    in_progress: 'bg-green-900/50 text-green-400',
    completed: 'bg-gray-700 text-gray-300',
    cancelled: 'bg-red-900/50 text-red-400',
    paused: 'bg-yellow-900/50 text-yellow-400',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search tournaments..."
          className="flex-1 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-green-500 text-white"
          onKeyDown={e => e.key === 'Enter' && doSearch()} />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white">
          <option value="">All Statuses</option>
          <option value="planned">Planned</option>
          <option value="announced">Announced</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
        <button onClick={doSearch} disabled={loading}
          className="px-4 py-1.5 bg-green-600 hover:bg-green-700 rounded-lg text-sm font-medium">
          {loading ? 'Searching...' : '🔍 Search'}
        </button>
      </div>

      <div className="text-sm text-gray-400">{total} result{total !== 1 ? 's' : ''}</div>

      <div className="space-y-2">
        {results.map((t: any) => (
          <div key={t.id} className="p-4 bg-gray-900 border border-gray-800 rounded-lg">
            <div className="flex items-center justify-between mb-1">
              <div className="font-medium">{t.name}</div>
              <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[t.status] || 'bg-gray-800'}`}>
                {t.status.replace(/_/g, ' ')}
              </span>
            </div>
            <div className="text-xs text-gray-500">
              {t.start_time ? new Date(t.start_time).toLocaleString() : 'No date set'}
              {t.buy_in ? ` • R${t.buy_in} buy-in` : ''}
              {t.starting_stack ? ` • ${t.starting_stack.toLocaleString()} chips` : ''}
            </div>
            {t.notes && <div className="text-xs text-gray-400 mt-1 line-clamp-2">{t.notes}</div>}
          </div>
        ))}
        {!loading && results.length === 0 && (
          <div className="text-center py-8 text-gray-500">No tournaments found.</div>
        )}
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════
   HISTORY TAB
   ═══════════════════════════════════════════════ */

function HistoryTab({ token }: { token: string }) {
  const [history, setHistory] = useState<any[]>([])

  useEffect(() => {
    api('/api/v1/broadcast/history?limit=50', { headers: { Authorization: `Bearer ${token}` } })
      .then(setHistory)
      .catch(() => {})
  }, [])

  if (history.length === 0) {
    return <div className="text-center py-12 text-gray-500">No broadcasts sent yet.</div>
  }

  return (
    <div className="space-y-2">
      {history.map((b: any) => (
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
          <div className="text-xs text-gray-500 mb-2">
            {new Date(b.created_at).toLocaleString()}
            {b.sent_at && ` • Sent: ${new Date(b.sent_at).toLocaleString()}`}
          </div>
          <div className="text-xs text-gray-400 whitespace-pre-wrap line-clamp-3">{b.rendered_body}</div>
        </div>
      ))}
    </div>
  )
}
