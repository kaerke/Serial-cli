Write-Host "Starting Python Serial Terminal + STM32 Flasher..." -ForegroundColor Cyan
python cli.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nApplication exited with error code $LASTEXITCODE." -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
