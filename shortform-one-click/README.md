# Shortform — local Windows draft maker

Extract the ZIP into a writable folder, then double-click **Start.cmd**. Choose your long video and click **Make Shorts**. Subsequent launches reuse installed dependencies. Do not run inside the ZIP.

First launch can install Python 3.12 and FFmpeg through WinGet, with normal Windows permission prompts. If either installs, reopen the launcher so PATH refreshes. Python and its libraries power local speech recognition; no Python commands are needed. First transcription downloads the multilingual `small` Whisper model from Hugging Face (internet required). After the model is cached, transcription and rendering run locally. No account or API key is used. Package and model downloads contact their providers; the application does not upload your footage.

Defaults: up to five non-overlapping 20–60 second drafts, 1080×1920, full source image with padding, six-word caption groups, H.264/AAC MP4. A center-crop option fills the screen but does not track faces. The app uses a simple text scoring heuristic for opening hooks and sentence endings; it does not understand or guarantee editorial quality. It may return fewer clips when there are not enough non-overlapping candidates. Review context, captions, and framing before publishing. Captions are automatic, not human verified.

For better selections, upload the generated transcript.txt to your chat and ask for clips.csv with `name,start,end` columns (seconds). Select that CSV in the app and rerun to export the exact selections. Chat is a manual handoff; this app is not connected to your ChatGPT account. A rerun transcribes again. No automatic posting or paid AI service is included.

Outputs are in `output/<job>/`: transcript.txt, transcript.json, clips.csv, and per-clip folders with MP4s and editable ASS captions. Originals are read only. Every run uses a new output folder. Allow disk space for exports and several GB for dependencies/model cache. Long videos can take substantial time on a CPU; close unnecessary apps on low-memory systems. Keep the launcher open while processing.

This package creates cuts, captions, and vertical exports with FFmpeg. It does not generate HyperFrames compositions, animated motion keyframes, or face tracking. The exported MP4s can be used as footage in a separately authored HyperFrames project; HyperFrames is not required to run this app.

Requirements: Windows 10/11, Python 3.12 with Tk (standard python.org installer), FFmpeg/FFprobe with libass support. WinGet is needed only for automatic prerequisite installation. If absent, install Python 3.12 from python.org and FFmpeg from ffmpeg.org, then reopen Start.cmd. Setup does not disable TLS or signature verification. Local launch policy override applies only to the bundled PowerShell setup process.

Validation: core clip selection, CSV validation, caption timing, and an FFmpeg render are checked in the development environment. Windows launcher, GUI, model download and end-to-end transcription still require a Windows-machine check.
