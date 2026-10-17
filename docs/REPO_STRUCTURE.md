# GitHub repository structure

Keep the repository root exactly like this. Upload the *contents* of this project folder to the root of the GitHub repository, not the ZIP file and not an extra nested `chai-animation-generator/` folder.

```text
chai-animation-studio/             # GitHub repository root
├── .gitignore
├── README.md
├── docker-compose.yml             # Local development
├── render.yaml                    # Render Blueprint: frontend + backend
├── docs/
│   ├── REPO_STRUCTURE.md
│   └── ROADMAP.md
├── backend/                       # Python API and media processing
│   ├── .env.example               # Template only; never put real keys here
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       └── main.py                # FastAPI routes and current MVP pipeline
└── frontend/                      # Mobile-friendly Next.js website
    ├── Dockerfile
    ├── next.config.mjs             # Proxies /backend requests to API
    ├── package.json
    └── app/
        ├── layout.tsx
        ├── page.tsx                # Upload, job status, transcript, preview UI
        └── style.css               # Responsive styling, including iPhone
```

## What belongs where?

- `frontend/`: browser UI. It should work in Chrome on an iPhone; video processing runs on the server.
- `backend/`: upload validation, job endpoints, audio transcription, optional speaker diarization, Claude-assisted scene analysis, and the current preview renderer.
- `render.yaml`: deploy configuration. Render reads it when you create a Blueprint.
- `docker-compose.yml`: optional local development setup.
- `docs/`: project documentation and the next implementation milestones.

## Before pushing to GitHub

1. Create an **empty private** repository named `chai-animation-studio`.
2. Extract this ZIP on a computer if possible.
3. Open the extracted `chai-animation-generator` folder and upload its *contents* (the items shown above) to the repository root.
4. Do not upload `backend/.env`, API keys, `node_modules/`, `.next/`, Python cache files, or generated videos.
5. Confirm `README.md`, `render.yaml`, `backend/`, `frontend/`, `docker-compose.yml`, and `docs/` are visible at the top level.

You can upload files through GitHub's web UI. For ongoing development, Git is easier, but it is not required for the initial upload.
