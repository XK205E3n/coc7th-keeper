Remove-Item "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stdout.log" -ErrorAction SilentlyContinue
Remove-Item "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stderr.log" -ErrorAction SilentlyContinue

$dshBin = "C:\Users\xingk\AppData\Local\Programs\DSH Desktop\resources\app\node_modules\@deepseek-ai\dsh\lib\bin.js"
$env:DSH_PERMISSION_MODE = "workspace-write"

Write-Host "starting..."
Start-Process -FilePath "C:\Program Files\nodejs\node.exe" -ArgumentList "`"$dshBin`" --profile dsh-lark" -NoNewWindow -RedirectStandardOutput "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stdout.log" -RedirectStandardError "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stderr.log"
Start-Sleep -Seconds 8
Write-Host "=== procs ==="
Get-Process node | Where-Object { $_.Id -ne 16072 } | Select-Object Id, ProcessName | Format-Table
Write-Host "=== stderr ==="
if (Test-Path "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stderr.log") { Get-Content "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stderr.log" -Tail 25 }
Write-Host "=== stdout ==="
if (Test-Path "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stdout.log") { Get-Content "D:\DeepSeek Harness\跑团\.dsh\bin\dsh-stdout.log" -Tail 25 }