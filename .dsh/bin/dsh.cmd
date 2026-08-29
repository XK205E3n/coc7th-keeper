@echo off
rem dsh.cmd - wrapper for the dsh CLI shipped inside DSH Desktop.
rem DSH Desktop is an Electron GUI app; its bundled dsh CLI is not on PATH by default.
rem This wrapper invokes node directly with the bin.js shipped inside the Desktop install.
rem
rem IMPORTANT: DSH Desktop injects DSH_HOME=C:\Users\xingk\AppData\Roaming\dsh-desktop\harness
rem into child processes. dsh-lark-bot spawns a dsh-lark-sdk subprocess whose profile lookup
rem depends on DSH_HOME; the harness home has NO dsh-lark profiles, so the SDK fails to boot.
rem We explicitly pin DSH_HOME to the user-level ~/.dsh here so both the main dsh-lark
rem profile and the dsh-lark-sdk subprocess resolve profiles correctly.

if "%DSH_HOME%"=="" set "DSH_HOME=%USERPROFILE%\.dsh"
set "DSH_HOME=%USERPROFILE%\.dsh"

node "C:\Users\xingk\AppData\Local\Programs\DSH Desktop\resources\app\node_modules\@deepseek-ai\dsh\lib\bin.js" %*
