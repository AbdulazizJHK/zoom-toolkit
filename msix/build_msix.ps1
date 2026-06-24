<#
.SYNOPSIS
  Builds an MSIX package for Zoom Toolkit from the PyInstaller exe.

.DESCRIPTION
  Stages the manifest, Assets, and dist\Zoom Toolkit.exe (copied as
  ZoomToolkit.exe), then runs makeappx to produce ZoomToolkit.msix.

  For Store submission: upload the UNSIGNED .msix to Partner Center
  (Microsoft re-signs it). First update Identity Name/Publisher in
  AppxManifest.xml to your reserved-app values.

  For LOCAL testing: run with -Sign. This creates a self-signed cert
  (CN=AbdulazizJHK, matching the manifest Publisher), signs the package,
  and tells you how to trust + install it.

.EXAMPLE
  pwsh -File build_msix.ps1            # build unsigned (for the Store)
  pwsh -File build_msix.ps1 -Sign      # build + self-sign (for local install)
#>
param([switch]$Sign)

$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $MyInvocation.MyCommand.Path     # ...\msix
$project = Split-Path -Parent $root                            # ...\Script
$exe     = Join-Path $project "dist\Zoom Toolkit.exe"
$stage   = Join-Path $root "stage"
$out     = Join-Path $root "ZoomToolkit.msix"
$publisher = "CN=AbdulazizJHK"   # must match AppxManifest.xml <Identity Publisher>

if (-not (Test-Path $exe)) { throw "Build the app first: $exe not found." }

# --- locate the Windows SDK tools (makeappx / signtool) ---
function Find-SdkTool($name) {
    $bins = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending
    foreach ($b in $bins) {
        $p = Join-Path $b.FullName "x64\$name"
        if (Test-Path $p) { return $p }
    }
    throw "$name not found. Install the Windows 10/11 SDK (or 'App development' workload)."
}
$makeappx = Find-SdkTool "makeappx.exe"

# --- stage the package layout ---
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null
Copy-Item (Join-Path $root "AppxManifest.xml") $stage
Copy-Item (Join-Path $root "Assets") $stage -Recurse
Copy-Item $exe (Join-Path $stage "ZoomToolkit.exe")   # rename: no spaces in manifest Executable

# --- pack ---
if (Test-Path $out) { Remove-Item $out -Force }
& $makeappx pack /o /d $stage /p $out
if ($LASTEXITCODE -ne 0) { throw "makeappx failed." }
Write-Host "`nBuilt: $out" -ForegroundColor Green

if ($Sign) {
    $signtool = Find-SdkTool "signtool.exe"
    $pfx = Join-Path $root "ZoomToolkit_test.pfx"
    $pwd = ConvertTo-SecureString "test123" -AsPlainText -Force
    Write-Host "Creating self-signed test certificate ($publisher)..." -ForegroundColor Cyan
    $cert = New-SelfSignedCertificate -Type Custom -Subject $publisher `
        -KeyUsage DigitalSignature -FriendlyName "Zoom Toolkit Test" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
    Export-PfxCertificate -Cert $cert -FilePath $pfx -Password $pwd | Out-Null
    & $signtool sign /fd SHA256 /a /f $pfx /p "test123" $out
    if ($LASTEXITCODE -ne 0) { throw "signtool failed." }
    $cer = Join-Path $root "ZoomToolkit_test.cer"
    Export-Certificate -Cert $cert -FilePath $cer | Out-Null
    Write-Host "`nSigned. To install locally:" -ForegroundColor Green
    Write-Host "  1) Trust the test cert (one time, as admin):"
    Write-Host "     Import-Certificate -FilePath `"$cer`" -CertStoreLocation Cert:\LocalMachine\TrustedPeople"
    Write-Host "  2) Install the package:  Add-AppxPackage `"$out`""
    Write-Host "  (The self-signed cert is for LOCAL TESTING ONLY — never ship it.)"
}
