$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) {
        $hasPython = $false
        if (Get-Command py -ErrorAction SilentlyContinue) {
            try {
                & py -3.12 -c "import sys; sys.exit(0)" 2>$null
                $hasPython = ($LASTEXITCODE -eq 0)
            } catch {
                $hasPython = $false
            }
        }
        if (!$hasPython) {
            Write-Host 'Installing Python 3.12. Windows may ask for permission.'
            if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
                throw 'Install Python 3.12 from python.org (include the Python launcher), then double-click Start.cmd again.'
            }
            & winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -ne 0) { throw 'Python installation did not complete.' }
            Write-Host 'Python installed. Close this window and double-click Start.cmd again.'
            Read-Host 'Press Enter to close'
            exit 0
        }
        & py -3.12 -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required. Install it from python.org, then reopen Start.cmd.' }
    }
    if (!(Get-Command ffmpeg -ErrorAction SilentlyContinue) -or !(Get-Command ffprobe -ErrorAction SilentlyContinue)) {
        if (!(Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Install FFmpeg and add its bin folder to PATH, then reopen Start.cmd.' }
        Write-Host 'Installing FFmpeg. Windows may ask for permission.'
        & winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) { throw 'FFmpeg installation did not complete.' }
        Write-Host 'FFmpeg installed. Close this window and double-click Start.cmd again.'
        Read-Host 'Press Enter to close'
        exit 0
    }
    & $python -c "import faster_whisper"
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'First launch: installing the local transcription engine. This can take several minutes.'
        & $python -m pip install --disable-pip-version-check -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check your internet connection and retry.' }
    }
    & $python app.py
    if ($LASTEXITCODE -ne 0) { throw 'The app exited with an error.' }
} catch {
    Write-Host $_ -ForegroundColor Red
    exit 1
}
