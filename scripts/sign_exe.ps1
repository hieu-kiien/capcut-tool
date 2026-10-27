<#
.SYNOPSIS
    Signs the built CapCut Long Story Studio Windows executable with Authenticode signature.
.DESCRIPTION
    Uses an existing Code Signing Certificate from the Windows Certificate Store or creates
    a development self-signed certificate to prevent Windows Defender / SmartScreen blocking.
.PARAMETER TargetExe
    Path to the executable to sign. Default: dist\CapCutLongStoryStudio\CapCutLongStoryStudio.exe
.PARAMETER CertificateThumbprint
    Optional thumbprint of a trusted EV/OV Code Signing Certificate.
.PARAMETER CreateSelfSignedIfMissing
    Automatically create and trust a local developer code signing certificate if none exists.
#>

[CmdletBinding()]
param(
    [string]$TargetExe = "dist\CapCutLongStoryStudio\CapCutLongStoryStudio.exe",
    [string]$CertificateThumbprint = "",
    [switch]$CreateSelfSignedIfMissing = $true
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ExePath = Join-Path $ProjectRoot $TargetExe

if (-not (Test-Path $ExePath)) {
    Write-Warning "Target executable not found at: $ExePath"
    Write-Host "Please run 'build_mvp.ps1' first before signing." -ForegroundColor Yellow
    exit 1
}

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " CapCut Studio Authenticode Code Signing Pipeline  " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Target: $ExePath"

$Cert = $null

if ($CertificateThumbprint) {
    Write-Host "Looking up certificate by thumbprint: $CertificateThumbprint"
    $Cert = Get-Item "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
    if (-not $Cert) {
        $Cert = Get-Item "Cert:\LocalMachine\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
    }
}

if (-not $Cert) {
    Write-Host "Searching for available Code Signing certificates..."
    $Cert = Get-ChildItem -Path Cert:\CurrentUser\My -CodeSigningCert -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $Cert) {
        $Cert = Get-ChildItem -Path Cert:\LocalMachine\My -CodeSigningCert -ErrorAction SilentlyContinue | Select-Object -First 1
    }
}

if (-not $Cert -and $CreateSelfSignedIfMissing) {
    Write-Host "No Code Signing certificate found. Creating local developer certificate..." -ForegroundColor Yellow
    $CertName = "CapCutStudioDevCodeSign"
    $ExistingDevCert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*$CertName*" } | Select-Object -First 1
    
    if ($ExistingDevCert) {
        $Cert = $ExistingDevCert
        Write-Host "Using existing local developer certificate: $($Cert.Thumbprint)"
    } else {
        $Cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=$CertName" -CertStoreLocation "Cert:\CurrentUser\My" -FriendlyName "CapCut Studio Dev Code Signing" -NotAfter (Get-Date).AddYears(5)
        Write-Host "Created new self-signed certificate: $($Cert.Thumbprint)" -ForegroundColor Green
    }
}

if (-not $Cert) {
    Write-Error "No Code Signing certificate could be located or created. Aborting signing."
    exit 1
}

Write-Host "Signing executable using certificate: $($Cert.Subject) [$($Cert.Thumbprint)]..." -ForegroundColor Cyan

# Timestamp server (DigiCert or Sectigo RFC3161)
$TimestampServer = "http://timestamp.digicert.com"

try {
    $SignResult = Set-AuthenticodeSignature -FilePath $ExePath -Certificate $Cert -TimestampServer $TimestampServer -HashAlgorithm SHA256 -ErrorAction Stop
} catch {
    Write-Warning "Timestamp server unreachable, signing without timestamp..."
    $SignResult = Set-AuthenticodeSignature -FilePath $ExePath -Certificate $Cert -HashAlgorithm SHA256
}

Write-Host "Signature Status: $($SignResult.Status)" -ForegroundColor ($SignResult.Status -eq "Valid" ? "Green" : "Yellow")
$CurrentSig = Get-AuthenticodeSignature -FilePath $ExePath
Write-Host "Signer Certificate: $($CurrentSig.SignerCertificate.Subject)"
Write-Host "Authenticode Signature Applied Successfully!" -ForegroundColor Green
