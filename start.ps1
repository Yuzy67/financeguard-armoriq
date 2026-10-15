$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
  py -3.13 -m venv .venv
  if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.13 with its launcher and run again.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m uvicorn app:app --host 127.0.0.1 --port 8001
