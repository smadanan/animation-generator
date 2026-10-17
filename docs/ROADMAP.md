# Implementation roadmap

## Milestone 1 — Current starter MVP

- Mobile-friendly browser UI for uploading one reference image and one mixed dialogue audio file.
- Backend job endpoints and progress/status display.
- Word-timestamped transcript via faster-whisper.
- Optional speaker diarization if a compatible model and credentials are configured.
- Optional Claude-based scene/dialogue analysis.
- A basic MP4 animatic using the reference image and the exact original audio.

## Milestone 2 — Cartoon lip-sync prototype (not yet implemented)

1. Test with a real reference image and a short 5–10 second sample.
2. Build a character/mouth-region setup step so the user can confirm each character's face and mouth area.
3. Produce a small set of mouth poses for each character and map speech timing/phonetic cues to those poses.
4. Animate only the speaking character's mouth, with restrained blinking, head motion, and listener reactions.
5. Composite frames with FFmpeg and mux the **original uploaded audio unchanged as the final audio track**.
6. Compare output against the source audio for timing drift and verify the speaker-to-character mapping.

## Milestone 3 — Reliability before regular use

- Persist jobs and metadata in a database; do not rely on in-memory job state.
- Store uploads and results in durable object storage; do not rely on `/tmp` for retention.
- Add user authentication, quotas, deletion/retention controls, file-size/duration limits, retries, and cost controls.
- Add automated tests and monitoring.

## Language plan

Start validation with English, Hindi/Hinglish, then test Malayalam, Tamil, Telugu, Kannada, Marathi, and Bengali. Language detection and speech-to-mouth mapping must be evaluated with real samples and accents. Transcription is an analysis aid only; it must not replace, translate, or regenerate the final audio.

## Important limitation

This repository is an initial working scaffold, not a finished automatic lip-sync engine. The current video output is an audio-backed still-image animatic. Do not advertise it as completed lip-synced animation until Milestone 2 has been implemented and tested.
