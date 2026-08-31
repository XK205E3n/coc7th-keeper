taskkill /F /PID 17104 2>&1
Start-Sleep -Seconds 2
Write-Host "=== remaining node processes (expect only 42136) ==="
Get-Process node | Where-Object { $_.Id -ne 16072 } | Select-Object Id, ProcessName | Format-Table -AutoSize
Write-Host ""
Write-Host "=== patch status ==="
Get-Content "$env:USERPROFILE\.dsh\profiles\dsh-lark\cordis.patch.yml"
Write-Host ""
Write-Host "=== NEXT STEPS ==="
Write-Host "1. Close current PowerShell window"
Write-Host "2. Open a NEW PowerShell window"
Write-Host "3. Run: dsh --profile dsh-lark"
Write-Host "4. Wait for QR code (first time) or 'connected' status (if already bound)"
Write-Host "5. Keep PowerShell open"
Write-Host "6. In Feishu group, @bot send: hello"
Write-Host "7. Tell me the result"