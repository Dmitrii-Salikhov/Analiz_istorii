# Build Python sidecar into desktop/backend for electron-builder (Windows).
$ErrorActionPreference = "Stop"
$Repo = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $Repo

$Py = $null
foreach ($c in @(
  "$Repo\venv\Scripts\python.exe",
  "$Repo\.venv\Scripts\python.exe"
)) {
  if (Test-Path $c) { $Py = $c; break }
}
if (-not $Py) { $Py = "python" }

& $Py -m pip install -q pyinstaller
& $Py -m PyInstaller desktop/analiz_backend.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

if (Test-Path "desktop\backend") { Remove-Item -Recurse -Force "desktop\backend" }
New-Item -ItemType Directory -Path "desktop\backend" | Out-Null

if (-not (Test-Path "dist\AnalizIstoriiBackend")) {
  throw "PyInstaller output not found at dist\AnalizIstoriiBackend"
}
Copy-Item -Path "dist\AnalizIstoriiBackend\*" -Destination "desktop\backend\" -Recurse -Force

Write-Host "Backend ready in desktop/backend/"
Get-ChildItem "desktop\backend" | Select-Object -First 20 | Format-Table Name, Length
