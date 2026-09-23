@echo off
setlocal EnableExtensions
where uv >nul 2>nul
if errorlevel 1 (
    echo Install uv first: winget install --id=astral-sh.uv -e
    echo Then reopen your terminal and run this command again.
    exit /b 2
)
pushd "%~dp0.."
if errorlevel 1 exit /b 2

rem Keep the managed environment outside deeply nested extracted project folders.
rem An explicit caller setting still wins, which is useful for troubleshooting.
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
if not defined UV_PROJECT_ENVIRONMENT set "UV_PROJECT_ENVIRONMENT=%LOCALAPPDATA%\cwi-validation-venv"

rem The uv cache and a downloaded ZIP are commonly on different Windows volumes.
rem Copy mode avoids failed/partial hard-link installations and the associated warning.
if not defined UV_LINK_MODE set "UV_LINK_MODE=copy"

echo Preparing the pinned validation environment at:
echo   %UV_PROJECT_ENVIRONMENT%
uv sync --locked --no-dev
if errorlevel 1 (
    echo.
    echo Dependency setup failed; no validation report was created.
    echo Close other Python processes and retry this command. If the error persists,
    echo remove only the folder shown above and run this command again.
    popd
    exit /b 2
)

uv run --locked --no-dev cwi-validate-local %*
set "CWI_VALIDATION_EXIT=%ERRORLEVEL%"
popd
exit /b %CWI_VALIDATION_EXIT%
