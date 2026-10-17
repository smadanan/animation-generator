from __future__ import annotations
import json, os, shutil, subprocess, uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(os.getenv('DATA_DIR', '/tmp/chai-animation-data'))
ROOT.mkdir(parents=True, exist_ok=True)
app = FastAPI(title='Chai Animation Generator API', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(','), allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
app.mount('/files', StaticFiles(directory=str(ROOT)), name='files')

JOBS: dict[str, dict[str, Any]] = {}
ALLOWED_IMAGE = {'.png', '.jpg', '.jpeg', '.webp'}
ALLOWED_AUDIO = {'.mp3', '.wav', '.m4a', '.flac', '.aac'}

class MappingUpdate(BaseModel):
    speaker_map: dict[str, str]

class GenerateRequest(BaseModel):
    aspect_ratio: str = '9:16'
    animation_style: str = 'natural'
    speaker_map: dict[str, str] = {'SPEAKER_00': 'Character A', 'SPEAKER_01': 'Character B'}

async def save_upload(upload: UploadFile, destination: Path, allowed: set[str]) -> None:
    ext = Path(upload.filename or '').suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f'Unsupported file extension: {ext}')
    size = 0
    with destination.open('wb') as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > 200 * 1024 * 1024:
                out.close(); destination.unlink(missing_ok=True)
                raise HTTPException(413, 'File exceeds 200 MB limit')
            out.write(chunk)

@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'chai-animation-generator'}

@app.post('/api/jobs')
async def create_job(reference_image: UploadFile = File(...), audio: UploadFile = File(...)):
    job_id = uuid.uuid4().hex[:12]
    folder = ROOT / job_id
    folder.mkdir(parents=True)
    image_path = folder / f'reference{Path(reference_image.filename or "image.png").suffix.lower()}'
    audio_path = folder / f'dialogue{Path(audio.filename or "audio.mp3").suffix.lower()}'
    try:
        await save_upload(reference_image, image_path, ALLOWED_IMAGE)
        await save_upload(audio, audio_path, ALLOWED_AUDIO)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    JOBS[job_id] = {
        'id': job_id, 'status': 'uploaded', 'progress': 10,
        'reference_image': str(image_path), 'audio': str(audio_path),
        'speaker_map': {'SPEAKER_00': 'Character A', 'SPEAKER_01': 'Character B'},
        'timeline': [], 'result_url': None, 'error': None,
        'note': 'Files uploaded. Start analysis to transcribe and identify speakers.'
    }
    return public_job(JOBS[job_id])

def public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in job.items() if k not in {'reference_image', 'audio'}}

@app.get('/api/jobs/{job_id}')
def get_job(job_id: str):
    if job_id not in JOBS: raise HTTPException(404, 'Job not found (jobs are in-memory in this starter build)')
    return public_job(JOBS[job_id])

@app.post('/api/jobs/{job_id}/analyze')
def analyze_job(job_id: str, background: BackgroundTasks):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(404, 'Job not found')
    if job['status'] in {'analyzing', 'rendering'}: return public_job(job)
    job['status'] = 'analyzing'; job['progress'] = 20
    background.add_task(run_analysis, job_id)
    return public_job(job)

def run_analysis(job_id: str):
    job = JOBS[job_id]
    try:
        # Optional dependencies are imported only inside the worker.
        from faster_whisper import WhisperModel
        job['progress'] = 30
        model = WhisperModel(os.getenv('WHISPER_MODEL', 'small'), device=os.getenv('WHISPER_DEVICE', 'cpu'), compute_type=os.getenv('WHISPER_COMPUTE_TYPE', 'int8'))
        segments, info = model.transcribe(job['audio'], word_timestamps=True, vad_filter=True)
        timeline = []
        for seg in segments:
            timeline.append({'start': round(float(seg.start), 3), 'end': round(float(seg.end), 3), 'text': seg.text.strip(), 'speaker': 'UNKNOWN', 'words': [{'start': round(float(w.start), 3), 'end': round(float(w.end), 3), 'word': w.word} for w in (seg.words or []) if w.start is not None and w.end is not None]})
        job['timeline'] = timeline
        job['language'] = getattr(info, 'language', None)
        job['duration'] = round(max((x['end'] for x in timeline), default=0), 2)
        job['progress'] = 55
        diarize_audio(job_id)
        analyze_with_claude(job_id)
        job['status'] = 'ready_for_review'; job['progress'] = 65
        job['note'] = 'Transcript prepared. Review speaker assignments before rendering.'
    except Exception as exc:
        job['status'] = 'error'; job['error'] = str(exc); job['note'] = 'Analysis failed. Check server logs and required API keys.'

def diarize_audio(job_id: str):
    """Optional pyannote diarization. Requires HF_TOKEN and pyannote.audio model access."""
    job = JOBS[job_id]
    token = os.getenv('HF_TOKEN')
    if not token:
        job['diarization_note'] = 'HF_TOKEN not configured; speaker labels are provisional. Add HF_TOKEN for diarization or edit mapping manually.'
        return
    try:
        from pyannote.audio import Pipeline
        pipeline = Pipeline.from_pretrained('pyannote/speaker-diarization-community-1', token=token)
        diarization = pipeline(job['audio'])
        turns = []
        # pyannote.audio versions differ; support common annotation iterator shape.
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            turns.append({'start': float(turn.start), 'end': float(turn.end), 'speaker': str(speaker)})
        for seg in job['timeline']:
            midpoint = (seg['start'] + seg['end']) / 2
            match = next((t for t in turns if t['start'] <= midpoint <= t['end']), None)
            if match: seg['speaker'] = match['speaker']
        speakers = sorted({t['speaker'] for t in turns})
        job['speaker_map'] = {s: ('Character A' if i == 0 else 'Character B' if i == 1 else f'Extra speaker {i+1}') for i, s in enumerate(speakers)}
        job['diarization_note'] = f'Diarization detected {len(speakers)} speaker(s). Verify assignments.'
    except Exception as exc:
        job['diarization_note'] = f'Diarization failed; using provisional labels: {exc}'

def analyze_with_claude(job_id: str):
    """Claude interprets dialogue and suggests role mapping; it does not do diarization itself."""
    job = JOBS[job_id]
    key = os.getenv('ANTHROPIC_API_KEY')
    if not key:
        job['claude_note'] = 'ANTHROPIC_API_KEY not configured; transcript available without semantic analysis.'
        return
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        sample = [{'start': s['start'], 'end': s['end'], 'speaker': s['speaker'], 'text': s['text']} for s in job['timeline'][:250]]
        prompt = '''Analyze this two-person dialogue for animation planning. Return ONLY valid JSON with keys: summary (string), characters (array of objects with speaker_id, suggested_role, voice_cues, confidence), scenes (array of objects with start, end, active_speaker, listener, expression, camera). Do not change dialogue or infer political identity without evidence. If a speaker label is UNKNOWN, say so rather than guessing. Use concise scene boundaries and preserve timestamps. Transcript JSON:\n''' + json.dumps(sample, ensure_ascii=False)
        response = client.messages.create(model=os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514'), max_tokens=3500, messages=[{'role': 'user', 'content': prompt}])
        raw = ''.join(block.text for block in response.content if getattr(block, 'type', '') == 'text')
        start, end = raw.find('{'), raw.rfind('}')
        job['claude_analysis'] = json.loads(raw[start:end+1]) if start >= 0 else {'raw': raw}
        job['claude_note'] = 'Claude scene analysis complete.'
    except Exception as exc:
        job['claude_note'] = f'Claude analysis failed: {exc}'

@app.patch('/api/jobs/{job_id}/speaker-map')
def update_speaker_map(job_id: str, update: MappingUpdate):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(404, 'Job not found')
    job['speaker_map'] = update.speaker_map
    for seg in job['timeline']:
        if seg['speaker'] in update.speaker_map:
            seg['character'] = update.speaker_map[seg['speaker']]
    return public_job(job)

@app.post('/api/jobs/{job_id}/generate')
def generate(job_id: str, request: GenerateRequest, background: BackgroundTasks):
    job = JOBS.get(job_id)
    if not job: raise HTTPException(404, 'Job not found')
    if not job.get('timeline'): raise HTTPException(409, 'Run audio analysis before generation')
    job['status'] = 'rendering'; job['progress'] = 70
    job['speaker_map'] = request.speaker_map
    job['render_options'] = {'aspect_ratio': request.aspect_ratio, 'animation_style': request.animation_style}
    background.add_task(render_video, job_id)
    return public_job(job)

def render_video(job_id: str):
    """MVP render: original audio + still reference image. Replace provider adapter with real generated clips."""
    job = JOBS[job_id]
    try:
        out = ROOT / job_id / 'preview.mp4'
        # A clearly labelled animatic is useful before configuring paid video API credentials.
        cmd = ['ffmpeg', '-y', '-loop', '1', '-i', job['reference_image'], '-i', job['audio'], '-c:v', 'libx264', '-tune', 'stillimage', '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p', '-shortest', '-vf', 'scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2', str(out)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0: raise RuntimeError(proc.stderr[-2500:])
        job['result_url'] = f'/files/{job_id}/preview.mp4'
        job['status'] = 'animatic_ready'; job['progress'] = 100
        job['note'] = 'Animatic ready with original audio. This starter build does not yet generate lip-synced character footage; connect a video provider adapter next.'
    except Exception as exc:
        job['status'] = 'error'; job['error'] = str(exc)
