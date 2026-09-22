@echo off
setlocal
where uv >nul 2>nul
if errorlevel 1 (
    echo Install uv first: winget install --id=astral-sh.uv -e
    echo Then reopen your terminal and run this command again.
    exit /b 2
)
pushd "%~dp0.."
if errorlevel 1 exit /b 2
uv run --locked --no-dev cwi-validate-local %*
set "CWI_VALIDATION_EXIT=%ERRORLEVEL%"
popd
exit /b %CWI_VALIDATION_EXIT%
