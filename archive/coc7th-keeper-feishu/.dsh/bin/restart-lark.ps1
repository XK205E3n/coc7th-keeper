$logOut = "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stdout.log"
$logErr = "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stderr.log"
Remove-Item $logOut, $logErr -ErrorAction SilentlyContinue

Write-Host "=== Killing old dsh-lark (PID 13928) ==="
Stop-Process -Id 13928 -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "=== Remaining DSH nodes ==="
Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.Id -eq 13928 -or $_.Id -eq 15996 -or $_.Id -eq 42136 } | Select-Object Id, ProcessName

Write-Host ""
Write-Host "=== Starting dsh --profile dsh-lark (background) ==="
$dshBin = "C:\Users\xingk\AppData\Local\Programs\DSH Desktop\resources\app\node_modules\@deepseek-ai\dsh\lib\bin.js"
$env:DSH_PERMISSION_MODE = "workspace-write"
$proc = Start-Process -FilePath "C:\Program Files\nodejs\node.exe" -ArgumentList "`"$dshBin`" --profile dsh-lark" -PassThru -NoNewWindow -RedirectStandardOutput $logOut -RedirectStandardError $logErr
Write-Host "Started PID:" $proc.Id

Start-Sleep -Seconds 12

Write-Host ""
Write-Host "=== Process still alive? ==="
Get-Process -Id $proc.Id -ErrorAction SilentlyContinue | Select-Object Id, ProcessName

Write-Host ""
Write-Host "=== stdout (last 40 lines) ==="
if (Test-Path $logOut) { Get-Content $logOut -Tail 40 }

Write-Host ""
Write-Host "=== stderr (last 40 lines) ==="
if (Test-Path $logErr) { Get-Content $logErr -Tail 40 }