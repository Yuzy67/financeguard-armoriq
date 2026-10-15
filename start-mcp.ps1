$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
& '.\.venv\Scripts\python.exe' finance_mcp/server.py
