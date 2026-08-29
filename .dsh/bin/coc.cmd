@echo off
rem coc.cmd -- workspace-only entry point for CoC7th keeper scripts.
rem Designed to keep all paths inside the current DSH workspace so that
rem python invocations never trigger plan-gate for cross-drive access.

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
set "PYTHONIOENCODING=utf-8"

rem --- Pin workspace root (= parent of this script's parent) ---
set "COC_ROOT=%~dp0..\.."
for %%I in ("%COC_ROOT%") do set "COC_ROOT=%%~fI"

set "COC_SKILL_DIR=%COC_ROOT%\.dsh\skills\coc7th-keeper"
set "COC_SCRIPTS=%COC_SKILL_DIR%\scripts"
set "COC_SESSION_ROOT=%COC_ROOT%\coc-session"
if not defined COC_MODULES_DIR set "COC_MODULES_DIR=%COC_SKILL_DIR%\modules"

if "%COC_ROOM%"=="" set "COC_ROOM=demo"

rem --- Take first arg as command, rest pass through ---
set "COC_CMD=%~1"
if "%COC_CMD%"=="" goto :usage
shift

rem --- Direct script routing (all paths inside workspace) ---
rem NOTE: %* in cmd includes the original %1 (the command name).
rem       We have to strip it via a subshell trick: pass %1~z to python,
rem       but easier: use a helper variable with %1~z syntax via a copy.
rem       Actually cmd lacks "args after shift". Trick: forward %* via cmd /c
rem       with the command name already stripped by re-quoting everything.

rem We use %0 expansion to get just the trailing args after the command.
rem Approach: capture %* into COC_ARGS, then strip leading token.
set "COC_ALL=%*"
for /F "tokens=1*" %%A in ("%COC_ALL%") do set "COC_ARGS=%%B"

if /I "%COC_CMD%"=="modules"             python "%COC_SCRIPTS%\modules.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="help"                python "%COC_SCRIPTS%\help.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="build_help_cache"    python "%COC_SCRIPTS%\build_help_cache.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="build_modules_cache" python "%COC_SCRIPTS%\build_modules_cache.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="build_all_cache"     python "%COC_SCRIPTS%\build_all_cache.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="roll"                python "%COC_SCRIPTS%\roll.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="check"               python "%COC_SCRIPTS%\check.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="sanity"              python "%COC_SCRIPTS%\sanity.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="combat"              python "%COC_SCRIPTS%\combat.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="room"                python "%COC_SCRIPTS%\room.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="build"               python "%COC_SCRIPTS%\build.py" %COC_ARGS% & goto :eof
if /I "%COC_CMD%"=="use-pregen"          python "%COC_SCRIPTS%\use_pregen.py" %COC_ARGS% & goto :eof

echo Unknown coc command: %COC_CMD% 1>&2
echo Run `coc.cmd` without arguments for usage. 1>&2
exit /b 2

:usage
echo Usage: coc.cmd ^<command^> [args...]
echo.
echo Direct script routing (workspace-only, no absolute paths):
echo   modules list ^| show ^<id^> ^| pick ^| ids
echo   help md ^| json
echo   build_help_cache
echo   build_modules_cache
echo   build_all_cache
echo   roll ^<expr^> [--by X] [--why ...] [--room X] [--no-log]
echo   check skill ^<name^> ^<val^> ... ^| luck ^<val^> ... ^| opposed ... ^| combined ...
echo   sanity check --player-file ^<path^> ^<loss^> ... ^| indef
echo   combat attack ^<atk^> ^<def^> ^<dmg^> ^<db^> ... ^| ini ... ^| wound ...
echo   room init|join|leave|build|status|audit|save|load|kick|pwd ^<args^>
echo   build ^<name^> [--age N] [--out PATH]
echo.
echo Composite helpers:
echo   use-pregen ^<name^> --room ^<id^> --player ^<name^>
echo.
echo Environment (auto-set by this wrapper; do not export outside):
echo   COC_SESSION_ROOT=%COC_SESSION_ROOT%
echo   COC_ROOM=%COC_ROOM%
echo   COC_SKILL_DIR=%COC_SKILL_DIR%
exit /b 0