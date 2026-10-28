param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$isccCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
)

if (-not (Test-Path $python)) {
    throw "Project virtual environment not found. Create it with: py -m venv .venv"
}

$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        $iscc = $command.Source
    }
}
if (-not $iscc) {
    throw "Inno Setup 6 was not found. Install it with: winget install --id JRSoftware.InnoSetup --exact"
}

if (-not $SkipDependencyInstall) {
    & $python -m pip install -r (Join-Path $projectRoot "requirements-build.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install build dependencies."
    }
}

$pythonRoot = & $python -c "import sys; print(sys.base_prefix)"
if ($LASTEXITCODE -ne 0) {
    throw "Could not locate the Python installation directory."
}
$tclDirectory = Join-Path $pythonRoot "tcl"
$tclLibrary = Get-ChildItem $tclDirectory -Directory -Filter "tcl8.*" |
    Where-Object { Test-Path (Join-Path $_.FullName "init.tcl") } |
    Select-Object -First 1
$tkLibrary = Get-ChildItem $tclDirectory -Directory -Filter "tk8.*" |
    Where-Object { Test-Path (Join-Path $_.FullName "tk.tcl") } |
    Select-Object -First 1
if (-not $tclLibrary -or -not $tkLibrary) {
    throw "Tcl/Tk libraries are missing. Install Python with Tcl/Tk support before packaging."
}
$env:TCL_LIBRARY = $tclLibrary.FullName
$env:TK_LIBRARY = $tkLibrary.FullName
$env:TVMAZE_PROJECT_ROOT = $projectRoot
$env:TVMAZE_APP_VERSION = & $python -c "import os, runpy; print(runpy.run_path(os.path.join(os.environ['TVMAZE_PROJECT_ROOT'], 'version.py'))['__version__'])"
if ($LASTEXITCODE -ne 0 -or -not $env:TVMAZE_APP_VERSION) {
    throw "Could not read the application version."
}

Push-Location $projectRoot
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --windowed `
        --name TVMazeShowFinder `
        --add-data "config/config.json;config" `
        main.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed to build the application."
    }

    & $iscc (Join-Path $projectRoot "installer\TVMazeShowFinder.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed to create the installer."
    }
}
finally {
    Pop-Location
    Remove-Item Env:\TVMAZE_PROJECT_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:\TVMAZE_APP_VERSION -ErrorAction SilentlyContinue
}

$installerPath = Join-Path $projectRoot "dist-installer\TVMazeShowFinder-Setup.exe"
if (-not (Test-Path $installerPath)) {
    throw "The installer was not created at the expected location: $installerPath"
}
Write-Output "Installer created: $installerPath"
