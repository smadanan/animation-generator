# Creators Animation Studio

A cloud-oriented starter project for a mobile-friendly web app that accepts a reference image and one mixed dialogue audio file, then analyzes speaker timing and prepares a video preview. The website is intended to be used in Chrome on an iPhone; processing runs on the backend.

## Honest status

This is **Milestone 1: a starter MVP**. It includes the upload UI, backend job endpoints, transcript/timeline analysis, optional speaker diarization, optional Claude-assisted scene analysis, and a basic MP4 animatic with the uploaded original audio. **It does not yet produce finished lip-synced character animation.** The custom cartoon mouth-animation engine is the next milestone. See [`docs/ROADMAP.md`](docs/ROADMAP.md).

## GitHub folder structure

See [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md). The important rule is to upload the contents of this folder into the root of your repository, so `backend/`, `frontend/`, `render.yaml`, and `README.md` appear at the top level. Do not upload only the ZIP or create an extra nested folder.

```text
creators-animation-studio/
├── README.md
├── .gitignore
├── render.yaml
├── docker-compose.yml
├── docs/
├── backend/
│   ├── .env.example
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/main.py
└── frontend/
    ├── Dockerfile
    ├── next.config.mjs
    ├── package.json
    └── app/
        ├── layout.tsx
        ├── page.tsx
        └── style.css
```

## What it uses

- Frontend: Next.js / React, responsive layout.
- Backend: FastAPI / Python.
- Media: FFmpeg.
- Speech analysis: faster-whisper; optional pyannote speaker diarization.
- Optional semantic scene analysis: Anthropic Claude API.
- Hosting: GitHub for source, Render for deployment.

No paid Hugging Face subscription is required by the design. `HF_TOKEN` is optional and only used if you enable a pyannote model that requires gated model access. Model licences and access terms must be checked before commercial use. You can defer diarization and validate the upload/transcription flow first.

## Local development

Prerequisites: Docker Desktop/Engine and Docker Compose.

1. Copy `backend/.env.example` to `backend/.env`.
2. Add your `ANTHROPIC_API_KEY` only if you want Claude analysis. Keep `HF_TOKEN` blank unless you deliberately configure optional diarization.
3. From the repository root run:

   ```bash
   docker compose up --build
   ```

4. Open `http://localhost:3000`. API health/docs are at `http://localhost:8080/health` and `http://localhost:8080/docs`.

The first speech-model download may take time and use substantial memory. Start with short audio clips.

## GitHub setup

1. Use the existing repository `smadanan/animation-generator`. Do not create a second repository just to change the product name.
2. Upload the project contents to the repository root, or use Git from the extracted folder:

   ```bash
   git init
   git add .
   git commit -m "Initial Creators Animation Studio MVP"
   git branch -M main
   git remote add origin https://github.com/smadanan/animation-generator.git
   git push -u origin main
   ```

3. Never commit `.env` files, API keys, tokens, uploaded source audio, or generated videos.

## Render deployment

The root `render.yaml` defines a frontend service and a backend API. In Render, choose **New → Blueprint**, connect GitHub, and select this repository. Review the cost estimate and service plans before confirming deployment: the current YAML uses Render's `starter` plan for both services, which may incur charges. Configure secrets in the backend service's Render Environment settings, never in GitHub.

The initial frontend hostname may differ if the suggested name is unavailable. If it differs, update `CORS_ORIGINS` to match the actual frontend URL and redeploy the backend.

## Limitations and safety

- Job metadata currently lives in process memory and files use `/tmp`; jobs and uploads can be lost after restarts/redeploys. This is a development scaffold, not durable production storage.
- The current renderer produces a still-image animatic with the original uploaded audio, not real mouth movement.
- The final animation engine must keep the uploaded original audio as the final soundtrack. Any transcript is analysis-only and must not translate, replace, or regenerate that audio.
- Before public use, add authentication, persistent job storage, durable object storage, retention/deletion controls, quotas, retry logic, and cost limits.
