'use client';
import { useEffect, useState } from 'react';
const API = '/backend';
type Job = { id:string; status:string; progress:number; stage?:string; last_updated?:number; started_at?:number; note?:string; error?:string; timeline?:Array<{start:number;end:number;text:string;speaker:string;character?:string}>; speaker_map?:Record<string,string>; result_url?:string; diarization_note?:string; claude_note?:string; claude_analysis?:unknown };
export default function Home() {
 const [image,setImage]=useState<File|null>(null), [audio,setAudio]=useState<File|null>(null), [job,setJob]=useState<Job|null>(null), [busy,setBusy]=useState(false), [err,setErr]=useState('');
 const [durationLimit,setDurationLimit]=useState('10');
 const [clock,setClock]=useState(Date.now()), [uploading,setUploading]=useState(false), [uploadStartedAt,setUploadStartedAt]=useState<number|null>(null);
 useEffect(() => {
  if (!uploading && (!job || !['analyzing', 'rendering'].includes(job.status))) return;
  const clockTimer = window.setInterval(() => setClock(Date.now()), 1000);
  return () => window.clearInterval(clockTimer);
 }, [job?.id, job?.status, uploading]);
 useEffect(() => {
  if (!job || !['analyzing', 'rendering'].includes(job.status)) return;
  let cancelled = false;
  const poll = async () => {
   try {
    const response = await fetch(`${API}/api/jobs/${job.id}`, { cache: 'no-store' });
    const data = await response.json();
    if (!response.ok) {
     if (!cancelled) {
      setErr(data.detail || 'Could not refresh job status.');
      if (response.status === 404) setJob(current => current && current.id === job.id ? { ...current, status: 'error', error: 'This job was not found by the backend. Please upload the files again.' } : current);
     }
     return;
    }
    if (!cancelled) setJob(current => current && current.id === job.id ? data : current);
   } catch {
    if (!cancelled) setErr('Status refresh failed temporarily. Retrying automatically…');
   }
  };
  void poll();
  const timer = window.setInterval(poll, 2500);
  return () => { cancelled = true; window.clearInterval(timer); };
 }, [job?.id, job?.status]);
 async function create(){ if(!image||!audio||busy)return; setBusy(true);setUploading(true);setUploadStartedAt(Date.now()/1000);setClock(Date.now());setErr('');try{const f=new FormData();f.append('reference_image',image);f.append('audio',audio);const r=await fetch(`${API}/api/jobs`,{method:'POST',body:f});const d=await r.json();if(!r.ok)throw Error(d.detail||'Upload failed');setJob(d);}catch(e){setErr(e instanceof Error?e.message:String(e));}finally{setUploading(false);setBusy(false)} }
 async function action(path:string,body?:unknown,method='POST'){if(!job)return;setBusy(true);setErr('');if(path==='analyze')setJob(current=>current?{...current,status:'analyzing',progress:20,stage:'starting',error:undefined,note:'Starting audio analysis and speaker detection…',started_at:current.started_at||Date.now()/1000}:current);try{const r=await fetch(`${API}/api/jobs/${job.id}/${path}`,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw Error(d.detail||'Request failed');setJob(d);}catch(e){const message=e instanceof Error?e.message:String(e);setErr(message);if(path==='analyze')setJob(current=>current?{...current,status:'error',error:message,note:'Could not start audio analysis.'}:current);}finally{setBusy(false)} }
 async function refresh(){if(!job)return;const r=await fetch(`${API}/api/jobs/${job.id}`);if(r.ok)setJob(await r.json());}
 return <main className="shell"><header><div className="eyebrow">AI CREATOR WORKSPACE</div><h1>Creators Animation <span>Studio</span></h1><p className="sub">From a reference image and a real conversation to a ready-to-edit debate video.</p></header>
 <section className="panel"><h2>01 · Add your source files</h2><div className="uploads"><label className="drop"><span className="glyph">▧</span><strong>Reference image</strong><small>PNG, JPG or WebP · two characters preferred</small><input type="file" accept="image/*" onChange={e=>setImage(e.target.files?.[0]||null)}/><em>{image?.name||'Choose image'}</em>{image&&<img className="thumb" src={URL.createObjectURL(image)} alt="Reference preview"/>}</label><label className="drop"><span className="glyph">♫</span><strong>Dialogue audio</strong><small>MP3, WAV, M4A, FLAC · max 200 MB</small><input type="file" accept="audio/*" onChange={e=>setAudio(e.target.files?.[0]||null)}/><em>{audio?.name||'Choose audio'}</em></label></div><div className="field" style={{marginTop:16}}><label htmlFor="duration-limit"><strong>Transcription target</strong></label><select id="duration-limit" value={durationLimit} onChange={e=>setDurationLimit(e.target.value)} disabled={!!job}><option value="10">10 seconds</option><option value="30">30 seconds</option><option value="60">60 seconds</option><option value="full">Full audio</option></select><small className="muted">The target may be exceeded to finish the current dialogue.</small></div><button disabled={!image||!audio||busy||!!job} onClick={create}>{busy&&!job?'Uploading…':'Upload files'}</button></section>
 {uploading&&<section className="panel" role="status" aria-live="polite"><div className="row"><h2>02 · Generation job</h2><span className="status">uploading</span></div><div className="work-status"><span className="work-spinner" aria-hidden="true"></span><div className="work-copy"><strong>Working on your audio</strong><span>Uploading your audio and reference image to the server…</span><small>Elapsed {Math.floor(Math.max(0,clock/1000-(uploadStartedAt||clock/1000))/60).toString().padStart(2,'0')}:{Math.floor(Math.max(0,clock/1000-(uploadStartedAt||clock/1000))%60).toString().padStart(2,'0')} · Upload in progress</small></div></div><div className="progress" aria-label="Upload in progress"><span style={{width:'8%'}}/></div><p className="muted">Upload started. Analysis status will appear as soon as the server accepts the files.</p></section>}
 {job&&<section className="panel"><div className="row"><h2>02 · Generation job</h2><span className="status">{job.status.replaceAll('_',' ')}</span></div>
 {['analyzing','rendering'].includes(job.status)&&<div className="work-status" role="status" aria-live="polite">
  <span className="work-spinner" aria-hidden="true"></span>
  <div className="work-copy"><strong>{job.status==='rendering'?'Rendering preview':'Working on your audio'}</strong><span>{job.note||'Processing started…'}</span>
   <small>Elapsed {Math.floor(Math.max(0,clock/1000-(job.started_at||clock/1000)) / 60).toString().padStart(2,'0')}:{Math.floor(Math.max(0,clock/1000-(job.started_at||clock/1000)) % 60).toString().padStart(2,'0')} · Auto-refresh every 2.5 seconds</small>
   {job.last_updated&&clock/1000-job.last_updated>30&&<em className="stale-warning">No new transcript segments have been saved for over 30 seconds. The model may still be processing a segment; check Render logs if this continues.</em>}
  </div>
 </div>}<div className="progress" aria-label={`Progress ${job.progress||0}%`}><span style={{width:`${job.progress||0}%`}}/></div><p className="muted"><strong>{job.progress||0}%</strong> · {job.note}</p>{job.error&&<p className="error">{job.error}</p>}<div className="actions">{(job.status==='error'||job.status==='uploaded')&&<button disabled={busy} onClick={()=>action('analyze', {duration_seconds: durationLimit==='full'?null:Number(durationLimit)})}>{job.timeline&&job.timeline.length?'Retry scene analysis (reuse transcript)':'Transcribe & analyze selected duration'}</button>}}{job.timeline&&job.timeline.length>0&&(job.claude_note?.startsWith('Claude analysis failed')||job.note?.toLowerCase().includes('service restarted'))&&<button disabled={busy||job.status==='analyzing'} onClick={()=>action('analyze')}>Retry Claude scene analysis (keep transcript)</button>}</div>{job.diarization_note&&<p className="muted">{job.diarization_note}</p>}{job.claude_note&&<p className="muted">{job.claude_note}</p>}
 {job.timeline&&job.timeline.length>0&&<><h3>Transcript timeline</h3><div className="timeline">{job.timeline.map((s,i)=><div className="segment" key={i}><time>{s.start.toFixed(2)}–{s.end.toFixed(2)}s</time><b>{s.speaker}</b><span>{s.text}</span></div>)}</div><details><summary>Claude scene analysis (JSON)</summary><pre>{JSON.stringify(job.claude_analysis||{},null,2)}</pre></details><p className="muted">Speaker labels need a quick review before final rendering. This starter version creates an audio-backed animatic, not yet the final lip-synced generation.</p><button disabled={busy} onClick={()=>action('generate',{aspect_ratio:'9:16',animation_style:'natural',speaker_map:job.speaker_map||{'SPEAKER_00':'Character A','SPEAKER_01':'Character B'}})}>Create preview animatic</button></>}
 {job.result_url&&<div className="result"><h3>Preview render</h3><video controls src={`${API}${job.result_url}`} /><a href={`${API}${job.result_url}`} target="_blank" rel="noreferrer">Open video file ↗</a></div>}</section>}
 {err&&<p className="error">{err}</p>}<footer>Starter MVP · Files are stored temporarily by the backend. Add durable cloud storage and authentication before public deployment.</footer></main>
}
