param([Parameter(Mandatory = $true)][string]$StageDir)
$ErrorActionPreference = 'Stop'
$stage = (Resolve-Path $StageDir).Path
$repo = (Resolve-Path '.').Path
$source = Join-Path $repo 'builder\BitwardenPortable.cs'
$ico = Join-Path $stage 'App\AppInfo\appicon.ico'
$target = Join-Path $stage 'BitwardenPortable.exe'
foreach ($file in @($source,$ico)) { if (-not (Test-Path $file)) { throw "Required build input missing: $file" } }
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
if (-not (Test-Path $csc)) { throw "Windows .NET Framework compiler unavailable: $csc" }
Write-Host 'Compiling small community launcher with the official Bitwarden Windows icon.'
& $csc /nologo /target:winexe /platform:anycpu "/out:$target" "/win32icon:$ico" /reference:System.Windows.Forms.dll $source
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $target)) { throw 'Portable launcher compilation failed' }
Write-Host "Portable launcher created: $target"
