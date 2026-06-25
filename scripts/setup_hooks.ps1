# Install git pre-push hook for AI log submission (Windows PowerShell).
# Run once after cloning: powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1

$ErrorActionPreference = 'Stop'

$HookFile = '.git/hooks/pre-push'

# Use cmd.exe-compatible hook for Windows (no Git Bash required).
$HookBody = @'
#!/bin/sh
# Pre-push: sweep recent Antigravity / Gemini prompts, then submit AI logs.
scripts/_pyrun.cmd scripts/log_antigravity.py --auto || true
scripts/_pyrun.cmd scripts/submit_log.py || true
exit 0
'@

Set-Content -Path $HookFile -Value $HookBody -Encoding UTF8 -NoNewline
Write-Host "[ai-log] Git pre-push hook installed."

if (-not (Test-Path .ai-log)) { New-Item -ItemType Directory -Path .ai-log | Out-Null }
if (-not (Test-Path .ai-log/.gitkeep)) { New-Item -ItemType File -Path .ai-log/.gitkeep | Out-Null }

Write-Host "[ai-log] Setup complete. Configure AI_LOG_SERVER in your .env file."
