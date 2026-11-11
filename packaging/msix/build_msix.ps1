<#
.SYNOPSIS
  Builds dist\UltraShot.msix for the Microsoft Store (or for local testing).

.DESCRIPTION
  1. Builds the PyInstaller app (build_exe.bat) unless -SkipBuild.
  2. Renders the tile and icon assets.
  3. Stages dist\UltraShot\* + Assets + AppxManifest.xml (with identity and version substituted).
  4. Packs it with makeappx from the Windows SDK build tools (fetched from NuGet into
     packaging\msix\tools on first use; nothing is installed system-wide).
  5. With -Sign, creates a self-signed test certificate matching the Publisher and signs the package
     so it can be installed on this PC after the certificate is trusted (see docs/store.md).
     The Store upload must NOT be signed: Partner Center signs it.

.EXAMPLE
  .\packaging\msix\build_msix.ps1 -Version 1.1.0.0 -IdentityName "12345Publisher.UltraShot" -Publisher "CN=0000-0000" -PublisherDisplayName "Your name"
#>
param(
  [string]$Version = "1.1.0.0",
  [string]$IdentityName = "PLACEHOLDER.UltraShot",
  [string]$Publisher = "CN=PLACEHOLDER",
  [string]$PublisherDisplayName = "PLACEHOLDER",
  [switch]$SkipBuild,
  [switch]$Sign
)
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$root = Resolve-Path (Join-Path $here "..\..")
$tools = Join-Path $here "tools"
$stage = Join-Path $root "dist\msix-staging"
$out = Join-Path $root "dist\UltraShot.msix"

# --- tools -----------------------------------------------------------------------------------
$makeappx = Join-Path $tools "makeappx.exe"
if (-not (Test-Path $makeappx)) {
  Write-Host "Fetching makeappx/signtool from the Microsoft.Windows.SDK.BuildTools NuGet package..."
  New-Item -ItemType Directory -Force $tools | Out-Null
  $nupkg = Join-Path $tools "buildtools.zip"
  Invoke-WebRequest -UseBasicParsing "https://www.nuget.org/api/v2/package/Microsoft.Windows.SDK.BuildTools" -OutFile $nupkg
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [IO.Compression.ZipFile]::OpenRead($nupkg)
  # the whole x64 folder: makeappx needs its side-by-side .manifest files and the en-US resources
  foreach ($e in $zip.Entries) {
    if ($e.FullName -match '^bin/[^/]+/x64/(.+)$' -and $e.Name) {
      $dest = Join-Path $tools $Matches[1]
      New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
      [IO.Compression.ZipFileExtensions]::ExtractToFile($e, $dest, $true)
    }
  }
  $zip.Dispose(); Remove-Item $nupkg
}

# --- app build -------------------------------------------------------------------------------
if (-not $SkipBuild) {
  Write-Host "Building the app..."
  Push-Location $root
  # stderr is folded into stdout inside cmd: PyInstaller prints harmless warnings there, and with
  # ErrorActionPreference = Stop PowerShell would otherwise treat the first one as a failure.
  cmd /c "`"$root\build_exe.bat`" -q 2>&1"
  if ($LASTEXITCODE -ne 0) { Pop-Location; throw "build_exe.bat failed" }
  Pop-Location
}
if (-not (Test-Path (Join-Path $root "dist\UltraShot\UltraShot.exe"))) { throw "dist\UltraShot\UltraShot.exe not found" }

# --- assets + staging ------------------------------------------------------------------------
Write-Host "Rendering assets..."
python (Join-Path $here "make_assets.py")
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item (Join-Path $root "dist\UltraShot\*") $stage -Recurse
Copy-Item (Join-Path $here "Assets") (Join-Path $stage "Assets") -Recurse
$manifest = Get-Content (Join-Path $here "AppxManifest.xml") -Raw
$manifest = $manifest.Replace('Name="PLACEHOLDER.UltraShot"', "Name=`"$IdentityName`"")
$manifest = $manifest.Replace('Publisher="CN=PLACEHOLDER"', "Publisher=`"$Publisher`"")
$manifest = $manifest.Replace('<PublisherDisplayName>PLACEHOLDER</PublisherDisplayName>', "<PublisherDisplayName>$PublisherDisplayName</PublisherDisplayName>")
# Only the Identity element's Version: MinVersion/MaxVersionTested also end in "Version".
$manifest = $manifest -replace '(<Identity\b[^>]*?\s)Version="\d+\.\d+\.\d+\.\d+"', "`${1}Version=`"$Version`""
[IO.File]::WriteAllText((Join-Path $stage "AppxManifest.xml"), $manifest, (New-Object Text.UTF8Encoding $false))

# --- pack ------------------------------------------------------------------------------------
Write-Host "Packing..."
if (Test-Path $out) { Remove-Item $out -Force }
& $makeappx pack /d $stage /p $out /o
if ($LASTEXITCODE -ne 0) { throw "makeappx failed" }
Write-Host ("Built {0} ({1:N1} MB)" -f $out, ((Get-Item $out).Length / 1MB))

# --- optional test signing -------------------------------------------------------------------
if ($Sign) {
  $signtool = Join-Path $tools "signtool.exe"
  $pfx = Join-Path $root "dist\UltraShot-test.pfx"
  $pw = ConvertTo-SecureString "ultrashot-test" -AsPlainText -Force
  $cert = New-SelfSignedCertificate -Type Custom -Subject $Publisher -KeyUsage DigitalSignature `
    -FriendlyName "UltraShot test signing" -CertStoreLocation "Cert:\CurrentUser\My" `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
  Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $pw | Out-Null
  & $signtool sign /fd SHA256 /a /f $pfx /p "ultrashot-test" $out
  if ($LASTEXITCODE -ne 0) { throw "signtool failed" }
  Export-Certificate -Cert $cert -FilePath (Join-Path $root "dist\UltraShot-test.cer") | Out-Null
  Write-Host "Signed with a test certificate. To install locally, import dist\UltraShot-test.cer into"
  Write-Host "Local Machine > Trusted People (needs an administrator prompt), then: Add-AppxPackage $out"
}
