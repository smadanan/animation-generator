from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(os.getenv("DATA_DIR", "/tmp/chai-animation-data"))
ROOT.mkdir(parents=True, exist_ok=True)
app = FastAPI(title="Creators Animation Studio API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/files", StaticFiles(directory=str(ROOT)), name="files")

JOBS: dict[str, dict[str, Any]] = {}
ALLOWED_IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".flac", ".aac"}


class MappingUpdate(BaseModel):
    speaker_map: dict[str, str]


class GenerateRequest(BaseModel):
    aspect_ratio: str = "9:16"
    animation_style: str = "natural"
    speaker_map: dict[str, str] = {"SPEAKER_00": "Character A", "SPEAKER_01": "Character B"}


def persist_job(job: dict[str, Any]) -> None:
    """Atomically save job metadata and the latest real worker heartbeat."""
    now = time.time()
    job["last_updated"] = now
    if job.get("status") in {"analyzing", "rendering"}:
        job.setdefault("started_at", now)
    note = str(job.get("note", "")).lower()
    if job.get("status") == "analyzing":
        if "loading" in note or "model" in note:
            job["stage"] = "loading_model"
        elif "speaker" in note or "diariz" in note:
            job["stage"] = "identifying_speakers"
        elif "transcrib" in note:
            job["stage"] = "transcribing"
        elif "claude" in note or "scene" in note:
            job["stage"] = "scene_analysis"
    elif job.get("status") == "rendering":
        job["stage"] = "rendering"
    elif job.get("status") == "ready_for_review":
        job["stage"] = "completed"
    elif job.get("status") == "error":
        job["stage"] = "error"
    folder = ROOT / str(job["id"])
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "job.json"
    temporary = folder / "job.json.tmp"
    temporary.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


def load_jobs() -> None:
    """Restore jobs from persistent storage when the API process starts."""
    for metadata in ROOT.glob("*/job.json"):
        try:
            job = json.loads(metadata.read_text(encoding="utf-8"))
            # BackgroundTasks are process-bound. Mark interrupted work as retryable.
            if job.get("status") in {"analyzing", "rendering"}:
                if job.get("status") == "rendering" and job.get("result_url"):
                    job["status"] = "animatic_ready"
                else:
                    job["status"] = "ready_for_review" if job.get("timeline") else "uploaded"
                    job["progress"] = 65 if job.get("timeline") else 10
                    job["note"] = "The service restarted before this task finished. Please run the step again."
                persist_job(job)
            JOBS[job["id"]] = job
        except Exception as exc:
            print(f"Could not restore job metadata {metadata}: {exc}", flush=True)


@app.on_event("startup")
def restore_persisted_jobs() -> None:
    load_jobs()


async def save_upload(upload: UploadFile, destination: Path, allowed: set[str]) -> None:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file extension: {ext}")
    size = 0
    with destination.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > 200 * 1024 * 1024:
                out.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(413, "File exceeds 200 MB limit")
            out.write(chunk)


@app.get("/health")
def health():
    return {"status": "ok", "service": "creators-animation-studio"}


@app.post("/api/jobs")
async def create_job(background: BackgroundTasks, reference_image: UploadFile = File(...), audio: UploadFile = File(...)):
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
    job = {
        "id": job_id,
        "status": "analyzing",
        "progress": 20,
        "reference_image": str(image_path),
        "audio": str(audio_path),
        "speaker_map": {"SPEAKER_00": "Character A", "SPEAKER_01": "Character B"},
        "timeline": [],
        "result_url": None,
        "error": None,
        "note": "Files uploaded. Starting transcription and speaker analysis automatically.",
    }
    JOBS[job_id] = job
    persist_job(job)
    background.add_task(run_analysis, job_id)
    return public_job(job)


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in job.items() if k not in {"reference_image", "audio"}}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found in persistent storage")
    return public_job(job)


@app.post("/api/jobs/{job_id}/analyze")
def analyze_job(job_id: str, background: BackgroundTasks):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] in {"analyzing", "rendering"}:
        return public_job(job)
    if job.get("timeline") and job["status"] == "ready_for_review":
        return public_job(job)
    job["status"] = "analyzing"
    job["progress"] = 20
    job["error"] = None
    job["note"] = "Loading speech recognition model and transcribing audio."
    persist_job(job)
    background.add_task(run_analysis, job_id)
    return public_job(job)


def run_analysis(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return
    try:
        import assemblyai as aai

        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ASSEMBLYAI_API_KEY is missing. Add it to the creators-animation-api "
                "service environment variables in Render, then redeploy."
            )

        aai.settings.api_key = api_key
        job["progress"] = 25
        job["note"] = "Sending audio securely to AssemblyAI for online transcription and speaker separation."
        persist_job(job)

        config = aai.TranscriptionConfig(
            speech_models=["universal-2"],
            language_detection=True,
            speaker_labels=True,
        )
        transcript = aai.Transcriber().transcribe(job["audio"], config=config)
        if transcript.status == aai.TranscriptStatus.error:
            raise RuntimeError(f"AssemblyAI transcription failed: {transcript.error}")

        job["progress"] = 50
        job["note"] = "Transcription complete. Preparing timestamped dialogue and speaker labels."
        persist_job(job)

        timeline = []
        speaker_ids: dict[str, str] = {}
        utterances = transcript.utterances or []
        for utterance in utterances:
            source_speaker = str(utterance.speaker or "UNKNOWN")
            if source_speaker not in speaker_ids:
                speaker_ids[source_speaker] = f"SPEAKER_{len(speaker_ids):02d}"
            words = []
            for word in (utterance.words or []):
                start_ms = getattr(word, "start", None)
                end_ms = getattr(word, "end", None)
                word_text = getattr(word, "text", None)
                if start_ms is not None and end_ms is not None and word_text:
                    words.append({
                        "start": round(float(start_ms) / 1000, 3),
                        "end": round(float(end_ms) / 1000, 3),
                        "word": str(word_text),
                    })
            start_ms = getattr(utterance, "start", 0) or 0
            end_ms = getattr(utterance, "end", start_ms) or start_ms
            timeline.append({
                "start": round(float(start_ms) / 1000, 3),
                "end": round(float(end_ms) / 1000, 3),
                "text": str(utterance.text or "").strip(),
                "speaker": speaker_ids[source_speaker],
                "words": words,
            })

        # Some audio may not produce utterance objects; retain a usable transcript fallback.
        if not timeline and transcript.text:
            timeline.append({
                "start": 0.0,
                "end": round(float(getattr(transcript, "audio_duration", 0) or 0), 3),
                "text": transcript.text.strip(),
                "speaker": "UNKNOWN",
                "words": [],
            })

        job["timeline"] = timeline
        job["language"] = str(getattr(transcript, "language_code", "") or "") or None
        job["duration"] = round(max((item["end"] for item in timeline), default=0), 2)
        job["speaker_map"] = {
            speaker_id: ("Character A" if i == 0 else "Character B" if i == 1 else f"Extra speaker {i+1}")
            for i, speaker_id in enumerate(speaker_ids.values())
        } or {"SPEAKER_00": "Character A", "SPEAKER_01": "Character B"}
        job["progress"] = 55
        job["note"] = f"AssemblyAI transcription complete ({len(timeline)} dialogue segments). Speaker labels are ready to review."
        persist_job(job)

        # AssemblyAI already performed speaker diarization; no local Whisper or pyannote model is needed.
        analyze_with_claude(job_id)
        job["status"] = "ready_for_review"
        job["progress"] = 65
        job["note"] = "Transcript prepared. Review speaker assignments before rendering."
        persist_job(job)
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        job["note"] = "Analysis failed. Check the AssemblyAI API key and server logs, then retry."
        persist_job(job)
        print(f"Analysis failed for job {job_id}: {exc}", flush=True)


def diarize_audio(job_id: str):
    """Optional pyannote diarization. Requires HF_TOKEN and model access."""
    job = JOBS[job_id]
    token = os.getenv("HF_TOKEN")
    if not token:
        job["diarization_note"] = "HF_TOKEN not configured; speaker labels are provisional. You can edit mapping manually."
        persist_job(job)
        return
    try:
        from pyannote.audio import Pipeline

        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1", token=token)
        diarization = pipeline(job["audio"])
        turns = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            turns.append({"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)})
        for seg in job["timeline"]:
            midpoint = (seg["start"] + seg["end"]) / 2
            match = next((t for t in turns if t["start"] <= midpoint <= t["end"]), None)
            if match:
                seg["speaker"] = match["speaker"]
        speakers = sorted({t["speaker"] for t in turns})
        job["speaker_map"] = {
            s: ("Character A" if i == 0 else "Character B" if i == 1 else f"Extra speaker {i+1}")
            for i, s in enumerate(speakers)
        }
        job["diarization_note"] = f"Diarization detected {len(speakers)} speaker(s). Verify assignments."
    except Exception as exc:
        job["diarization_note"] = f"Diarization failed; using provisional labels: {exc}"
    persist_job(job)


def analyze_with_claude(job_id: str):
    """Claude interprets dialogue for planning; it does not perform diarization."""
    job = JOBS[job_id]
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        job["claude_note"] = "ANTHROPIC_API_KEY not configured; transcript available without semantic analysis."
        persist_job(job)
        return
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=key)
        sample = [
            {"start": s["start"], "end": s["end"], "speaker": s["speaker"], "text": s["text"]}
            for s in job["timeline"][:250]
        ]
        prompt = (
            "Analyze this two-person dialogue for animation planning. Return ONLY valid JSON with keys: "
            "summary (string), characters (array of objects with speaker_id, suggested_role, voice_cues, confidence), "
            "scenes (array of objects with start, end, active_speaker, listener, expression, camera). "
            "Do not change dialogue or infer political identity without evidence. If a speaker label is UNKNOWN, "
            "say so rather than guessing. Use concise scene boundaries and preserve timestamps. Transcript JSON:\\n"
            + json.dumps(sample, ensure_ascii=False)
        )
        response = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6"),
            max_tokens=3500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
        start, end = raw.find("{"), raw.rfind("}")
        job["claude_analysis"] = json.loads(raw[start:end + 1]) if start >= 0 else {"raw": raw}
        job["claude_note"] = "Claude scene analysis complete."
    except Exception as exc:
        job["claude_note"] = f"Claude analysis failed: {exc}"
    persist_job(job)


@app.patch("/api/jobs/{job_id}/speaker-map")
def update_speaker_map(job_id: str, update: MappingUpdate):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    job["speaker_map"] = update.speaker_map
    for seg in job["timeline"]:
        if seg["speaker"] in update.speaker_map:
            seg["character"] = update.speaker_map[seg["speaker"]]
    persist_job(job)
    return public_job(job)


@app.post("/api/jobs/{job_id}/generate")
def generate(job_id: str, request: GenerateRequest, background: BackgroundTasks):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.get("timeline"):
        raise HTTPException(409, "Run audio analysis before generation")
    job["status"] = "rendering"
    job["progress"] = 70
    job["speaker_map"] = request.speaker_map
    job["render_options"] = {"aspect_ratio": request.aspect_ratio, "animation_style": request.animation_style}
    persist_job(job)
    background.add_task(render_video, job_id)
    return public_job(job)


def render_video(job_id: str):
    """MVP render: original audio plus still image, not generated lip-sync footage."""
    job = JOBS.get(job_id)
    if not job:
        return
    try:
        out = ROOT / job_id / "preview.mp4"
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", job["reference_image"], "-i", job["audio"],
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-shortest", "-vf",
            "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            str(out),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-2500:])
        job["result_url"] = f"/files/{job_id}/preview.mp4"
        job["status"] = "animatic_ready"
        job["progress"] = 100
        job["note"] = "Animatic ready with original audio. This build does not yet generate lip-synced character footage."
        persist_job(job)
    except Exception as exc:
        job["status"] = "error"
        job["error"] = str(exc)
        persist_job(job)
        print(f"Rendering failed for job {job_id}: {exc}", flush=True)
