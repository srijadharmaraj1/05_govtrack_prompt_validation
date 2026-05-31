import { useState, useEffect, useRef } from 'react'
import './App.css'

const ROLE_META = {
  'District Collector'            : { icon: '🏛️', color: '#1a4fa0' },
  'Superintendent of Police'      : { icon: '👮', color: '#8b1a1a' },
  'Member of Legislative Assembly': { icon: '🗳️', color: '#1a7a3a' },
  'MLA'                           : { icon: '🗳️', color: '#1a7a3a' },
  'Member of Parliament'          : { icon: '🏛️', color: '#6b2fa0' },
  'Cabinet Minister'              : { icon: '👔', color: '#a06b1a' },
  'Chief Minister'                : { icon: '⭐', color: '#c0392b' },
  'IAS Officer'                   : { icon: '🎖️', color: '#1a6080' },
  'IPS Officer'                   : { icon: '🛡️', color: '#4a1a80' },
}
const EXAMPLES = [
  'Get all top officers of Coimbatore district',
  'Who is the Collector of Salem',
  'SP of Madurai Tamil Nadu',
  'Tamil Nadu Chief Minister',
  'MLA of Chennai district',
  'Collector of Erode district',
]
function getMeta(role) {
  if (!role) return { icon: '📋', color: '#2563eb' }
  for (const [k, v] of Object.entries(ROLE_META))
    if (role.toLowerCase().includes(k.toLowerCase())) return v
  return { icon: '📋', color: '#2563eb' }
}

function NoteModal({ profile, onSave, onClose }) {
  const [note, setNote] = useState(profile.note || '')
  return (
    <div className="backdrop" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-head"><span>📝 Note — {profile.name}</span><button className="x-btn" onClick={onClose}>✕</button></div>
        <div className="modal-body"><textarea className="note-ta" placeholder="Add notes about this officer..." value={note} onChange={e=>setNote(e.target.value)} rows={5} autoFocus/></div>
        <div className="modal-foot"><button className="btn-cancel" onClick={onClose}>Cancel</button><button className="btn-save" onClick={()=>onSave(profile.query,note)}>💾 Save Note</button></div>
      </div>
    </div>
  )
}

function Toast({ msg, onDone }) {
  useEffect(()=>{ const t=setTimeout(onDone,2500); return ()=>clearTimeout(t) },[])
  return <div className="toast">{msg}</div>
}

function Btn({ children, onClick, title, disabled, active, cls }) {
  return <button className={`abtn ${cls||''} ${active?'on':''}`} onClick={onClick} title={title} disabled={disabled}>{children}</button>
}
function R({ l, v, mono }) {
  if (!v) return null
  return <div className="row"><span>{l}</span><span style={mono?{fontFamily:'var(--mono)',fontSize:11,color:'#93b4fa'}:{}}>{v}</span></div>
}

function Card({ profile, index, onDelete, onRefresh, onBookmark, onFlag, onNote, refreshingQuery }) {
  const [open, setOpen] = useState(false)
  const { icon, color } = getMeta(profile.role)
  const busy = refreshingQuery === profile.query
  return (
    <div className={`card ${profile.bookmarked?'bookmarked':''} ${profile.flagged?'flagged':''} ${busy?'busy':''}`} style={{'--acc':color, animationDelay:`${index*70}ms`}}>
      {(profile.bookmarked||profile.flagged||profile.note) && (
        <div className="badges">
          {profile.bookmarked && <span className="badge bk">⭐ Pinned</span>}
          {profile.flagged    && <span className="badge fl">🚨 Outdated</span>}
          {profile.note       && <span className="badge nt">📝 Note</span>}
        </div>
      )}
      <div className="card-top">
        <div className="icon-box">{busy?'⏳':icon}</div>
        <div className="card-info"><span className="crole">{profile.role||'Government Official'}</span><span className="cdist">📍 {profile.district||profile.state||'Tamil Nadu'}</span></div>
      </div>
      <div className="cname" onClick={()=>setOpen(o=>!o)}>{profile.name||'Unknown'}</div>
      <div className="ctags">
        {profile.cadre      && <span className="tag">{profile.cadre}</span>}
        {profile.batch_year && <span className="tag">Batch {profile.batch_year}</span>}
        {profile.party      && <span className="tag party">{profile.party}</span>}
      </div>
      {profile.note && !open && <div className="note-prev">"{profile.note.slice(0,80)}{profile.note.length>80?'…':''}"</div>}
      {open && (
        <div className="expanded">
          <hr className="divider"/>
          <R l="Department"  v={profile.department}/>
          <R l="📞 Phone"    v={profile.office_phone}/>
          <R l="📧 Email"    v={profile.email}/>
          <R l="📅 Since"    v={profile.posted_since}/>
          {profile.additional_info && <div className="snippet">"{profile.additional_info}"</div>}
          {profile.note && <div className="note-box"><span className="note-lbl">📝 Your Note</span><p>{profile.note}</p></div>}
          {profile.sources?.length>0 && (
            <div className="sources"><span className="src-lbl">Sources:</span>
              {profile.sources.slice(0,2).map((s,i)=>{ try{return <a key={i} href={s} target="_blank" rel="noreferrer" className="src-link">{new URL(s).hostname}</a>}catch{return null} })}
            </div>
          )}
          <R l="AI Model" v={profile.model_used} mono/>
          <R l="Fetched"  v={profile.fetched_at?new Date(profile.fetched_at).toLocaleString('en-IN'):'—'}/>
        </div>
      )}
      <div className="actions">
        <Btn active={profile.bookmarked} cls="gold" onClick={()=>onBookmark(profile.query)} title={profile.bookmarked?'Unpin':'Pin'}>⭐</Btn>
        <Btn onClick={()=>onNote(profile)} title="Add note">📝</Btn>
        <Btn active={profile.flagged} cls="red" onClick={()=>onFlag(profile.query)} title="Flag outdated">🚨</Btn>
        <Btn onClick={()=>onRefresh(profile.query)} disabled={busy} title="Re-fetch">{busy?'⏳':'🔄'}</Btn>
        <Btn cls="del" onClick={()=>onDelete(profile.query)} title="Delete">🗑️</Btn>
        <Btn cls="exp" onClick={()=>setOpen(o=>!o)}>{open?'▲':'▼'}</Btn>
      </div>
    </div>
  )
}

function SearchBar({ onSearch, searching, lastQuery }) {
  const [q, setQ] = useState('')
  const [show, setShow] = useState(false)
  const ref = useRef()
  const go = () => { if (!q.trim()||searching) return; onSearch(q.trim()); setShow(false) }
  return (
    <div className="sb-wrap">
      <div className={`sb ${searching?'busy':''}`}>
        <span className="sb-icon">{searching?'⏳':'🔍'}</span>
        <input ref={ref} className="sb-input" placeholder={searching?`Searching: "${lastQuery}"...`:'Search any Tamil Nadu government authority…'} value={q} onChange={e=>setQ(e.target.value)} onFocus={()=>setShow(true)} onBlur={()=>setTimeout(()=>setShow(false),150)} onKeyDown={e=>e.key==='Enter'&&go()} disabled={searching}/>
        <button className="sb-btn" onClick={go} disabled={searching||!q.trim()}>{searching?'Searching…':'Search'}</button>
      </div>
      {show && !searching && (
        <div className="drop">
          <div className="drop-lbl">Try these:</div>
          {EXAMPLES.map((ex,i)=><div key={i} className="drop-item" onMouseDown={()=>{setQ(ex);setShow(false);setTimeout(()=>ref.current?.focus(),50)}}>🔍 {ex}</div>)}
        </div>
      )}
    </div>
  )
}

function Empty({ filter }) {
  return (
    <div className="empty">
      <div className="ei">{filter?'🔍':'🏛️'}</div>
      <div className="et">{filter?'No results match':'Search for any authority'}</div>
      <div className="es">{filter?'Try a different filter':'Type a query above — results appear here instantly'}</div>
      {!filter && <div className="echips">{EXAMPLES.slice(0,3).map((ex,i)=><div key={i} className="echip">{ex}</div>)}</div>}
    </div>
  )
}

function Stat({ n, l }) { return <div className="stat"><span>{n}</span>{l}</div> }

export default function App() {
  const [profiles,   setProfiles]   = useState([])
  const [message,    setMessage]    = useState('')
  const [pushedAt,   setPushedAt]   = useState('')
  const [searching,  setSearching]  = useState(false)
  const [lastQuery,  setLastQuery]  = useState('')
  const [roleFilter, setRoleFilter] = useState('All')
  const [tab,        setTab]        = useState('all')
  const [textFilter, setTextFilter] = useState('')
  const [noteTarget, setNoteTarget] = useState(null)
  const [refreshing, setRefreshing] = useState(null)
  const [toast,      setToast]      = useState('')
  const [lastSync,   setLastSync]   = useState(null)
  const prevAt = useRef('')

  useEffect(()=>{
    const poll = async () => {
      try {
        const d = await fetch('/api/state').then(r=>r.json())
        setSearching(d.searching||false); setLastQuery(d.lastQuery||'')
        if (d.pushed_at && d.pushed_at !== prevAt.current) {
          prevAt.current=d.pushed_at; setProfiles(d.profiles||[]); setMessage(d.message||''); setPushedAt(d.pushed_at); setLastSync(new Date())
        }
      } catch {}
    }
    poll(); const id=setInterval(poll,2000); return ()=>clearInterval(id)
  },[])

  const post = (url,body) => fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
  const showToast = m => setToast(m)

  const handleSearch   = async q => { await post('/api/search',{query:q}); showToast(`🔍 Searching: "${q}"`) }
  const handleRefresh  = async q => { setRefreshing(q); await post('/api/refresh',{query:q}); showToast('🔄 Re-fetching…'); setTimeout(()=>setRefreshing(null),8000) }
  const handleDelete   = async q => { if(!confirm(`Delete "${q}"?`))return; await post('/api/delete',{query:q}); setProfiles(p=>p.filter(x=>x.query!==q)); showToast('🗑️ Deleted') }
  const handleBookmark = async q => { await post('/api/bookmark',{query:q}); setProfiles(p=>p.map(x=>x.query===q?{...x,bookmarked:!x.bookmarked}:x)); showToast('⭐ Toggled') }
  const handleFlag     = async q => { await post('/api/flag',{query:q}); setProfiles(p=>p.map(x=>x.query===q?{...x,flagged:!x.flagged}:x)); showToast('🚨 Toggled') }
  const handleNote     = async (q,note) => { await post('/api/note',{query:q,note}); setProfiles(p=>p.map(x=>x.query===q?{...x,note}:x)); setNoteTarget(null); showToast('📝 Saved') }

  const roles   = ['All',...new Set(profiles.map(p=>p.role).filter(Boolean))]
  const sorted  = [...profiles].sort((a,b)=>(b.bookmarked?1:0)-(a.bookmarked?1:0))
  const visible = sorted.filter(p=>{
    const rOk = roleFilter==='All'||p.role===roleFilter
    const tOk = tab==='all'||(tab==='bookmarked'&&p.bookmarked)||(tab==='flagged'&&p.flagged)
    const fOk = !textFilter||[p.name,p.district,p.role].some(v=>(v||'').toLowerCase().includes(textFilter.toLowerCase()))
    return rOk&&tOk&&fOk
  })
  const bkCnt=profiles.filter(p=>p.bookmarked).length
  const flCnt=profiles.filter(p=>p.flagged).length

  return (
    <div className="app">
      {toast      && <Toast msg={toast} onDone={()=>setToast('')}/>}
      {noteTarget && <NoteModal profile={noteTarget} onSave={handleNote} onClose={()=>setNoteTarget(null)}/>}
      <header className="hdr">
        <div className="hdr-l"><div className="logo">🏛️</div><div><div className="title">GovTrack Tamil Nadu</div><div className="sub">Tamil Nadu Authority Directory</div></div></div>
        <div className="hdr-r">{message&&<div className="hmsg">{searching?'⏳':'💬'} {message}</div>}<div className="live"><span className="dot"/>LIVE</div></div>
      </header>
      <SearchBar onSearch={handleSearch} searching={searching} lastQuery={lastQuery}/>
      {profiles.length>0 && (
        <div className="stats">
          <Stat n={profiles.length} l="Total"/>
          <Stat n={new Set(profiles.map(p=>p.district).filter(Boolean)).size} l="Districts"/>
          <Stat n={bkCnt} l="Pinned"/>
          <Stat n={lastSync?lastSync.toLocaleTimeString('en-IN'):'—'} l="Synced"/>
        </div>
      )}
      {profiles.length>0 && (
        <div className="fbar">
          <div className="tabs">
            <button className={`tab ${tab==='all'?'on':''}`}        onClick={()=>setTab('all')}>All ({profiles.length})</button>
            <button className={`tab ${tab==='bookmarked'?'on':''}`} onClick={()=>setTab('bookmarked')}>⭐ Pinned ({bkCnt})</button>
            <button className={`tab ${tab==='flagged'?'on':''}`}    onClick={()=>setTab('flagged')}>🚨 Flagged ({flCnt})</button>
          </div>
          <div className="pills">{roles.map(r=><button key={r} className={`pill ${roleFilter===r?'on':''}`} onClick={()=>setRoleFilter(r)}>{r}</button>)}</div>
          <input className="tfil" placeholder="Filter by name…" value={textFilter} onChange={e=>setTextFilter(e.target.value)}/>
        </div>
      )}
      <main className="grid">
        {profiles.length===0?<Empty filter={false}/>:visible.length===0?<Empty filter={true}/>:
          visible.map((p,i)=><Card key={p.query} profile={p} index={i} onDelete={handleDelete} onRefresh={handleRefresh} onBookmark={handleBookmark} onFlag={handleFlag} onNote={setNoteTarget} refreshingQuery={refreshing}/>)}
      </main>
      <footer className="ftr">GovTrack Tamil Nadu · Public data only · Tamil Nadu · {pushedAt?`Last update: ${new Date(pushedAt).toLocaleString('en-IN')}`:'Waiting…'}</footer>
    </div>
  )
}
