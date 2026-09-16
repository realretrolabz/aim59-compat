<#
.SYNOPSIS
Installs AIM 5.9.3861 on Windows 11 and applies the tested compatibility fix.

.DESCRIPTION
Downloads the pinned AIM 5.9.3861 installer from OldVersion.com to a user
cache, or accepts a user-selected local installer. It verifies the installer's
size and SHA-256, runs the normal installer, then disables aimapi.dll by
renaming it. It then lets the user select an AIM connection setting for the
current Windows user.

This is an installed compatibility workflow. It does not make AIM portable,
does not redistribute AIM, and applies no Wine-side changes.

Run from an elevated Windows PowerShell session. The installer is interactive.
#>
[CmdletBinding(SupportsShouldProcess = $true, DefaultParameterSetName = 'Install')]
param(
    [Parameter(ParameterSetName = 'Install')]
    [ValidateSet('Prompt', 'RealRetroLabz', 'Keep', 'Custom')]
    [string]$ServerMode = 'Prompt',

    [Parameter(ParameterSetName = 'Install')]
    [string]$ServerHost,

    [Parameter(ParameterSetName = 'Install')]
    [int]$ServerPort = 5190,

    [Parameter(ParameterSetName = 'Install')]
    [ValidateNotNullOrEmpty()]
    [string]$InstallerCache = (Join-Path $env:LOCALAPPDATA 'AIM59-Compat\installers'),

    [Parameter(ParameterSetName = 'Install')]
    [ValidateNotNullOrEmpty()]
    [string]$InstallerPath,

    [ValidateNotNullOrEmpty()]
    [string]$AimDirectory,

    [Parameter(Mandatory = $true, ParameterSetName = 'Rollback')]
    [switch]$Rollback
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$InstallerPageUrl = 'https://www.oldversion.com/software/aol-instant-messenger/aol-instant-messenger-5-9-3861/'
$InstallerFileName = 'aim593861.exe'
$InstallerSize = 8715352
$InstallerSha256 = '018438bf22672ee119e864d78f838a538ed067bb76296957a00e0c1080979af1'
$DisabledAimApiName = 'aimapi.dll.aim59-disabled'
$AimRegistryServerKey = 'HKCU:\Software\America Online\AOL Instant Messenger (TM)\CurrentVersion\Server'
$DefaultServerHost = 'aim.realretrolabz.com'
$DefaultServerPort = 5190

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-HtmlAttribute {
    param(
        [Parameter(Mandatory = $true)][string]$Html,
        [Parameter(Mandatory = $true)][string]$Name
    )

    $escapedName = [regex]::Escape($Name)
    $pattern = '(?is)\b' + $escapedName + '\s*=\s*(?:"(?<value>[^"]*)"|''(?<value>[^'']*)''|(?<value>[^\s>]+))'
    $match = [regex]::Match($Html, $pattern)
    if (-not $match.Success) {
        return $null
    }
    return [System.Net.WebUtility]::HtmlDecode($match.Groups['value'].Value)
}

function Get-OldVersionDownloadForm {
    param([Parameter(Mandatory = $true)][string]$Html)

    $forms = [regex]::Matches($Html, '(?is)<form\b(?<attributes>[^>]*)>(?<body>.*?)</form>')
    foreach ($form in $forms) {
        $action = Get-HtmlAttribute -Html $form.Groups['attributes'].Value -Name 'action'
        if ([string]::IsNullOrWhiteSpace($action) -or $action -notmatch '/software/download/') {
            continue
        }
        $inputs = [regex]::Matches($form.Groups['body'].Value, '(?is)<input\b(?<attributes>[^>]*)>')
        foreach ($input in $inputs) {
            $name = Get-HtmlAttribute -Html $input.Groups['attributes'].Value -Name 'name'
            if ($name -eq 'csrfmiddlewaretoken') {
                $token = Get-HtmlAttribute -Html $input.Groups['attributes'].Value -Name 'value'
                if (-not [string]::IsNullOrWhiteSpace($token)) {
                    return [pscustomobject]@{ Action = $action; CsrfToken = $token }
                }
            }
        }
    }
    throw 'OldVersion download form was not found; the site may have changed.'
}

function Assert-InstallerIdentity {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Installer was not downloaded: $Path"
    }
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.Length -ne $InstallerSize) {
        throw "Installer size mismatch: expected $InstallerSize bytes, got $($item.Length)."
    }
    $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $InstallerSha256) {
        throw "Installer checksum mismatch: expected $InstallerSha256, got $actualHash."
    }
}

function Get-VerifiedInstaller {
    param(
        [Parameter(Mandatory = $true)][string]$CacheDirectory,
        [string]$SuppliedInstallerPath
    )

    if (-not [string]::IsNullOrWhiteSpace($SuppliedInstallerPath)) {
        $resolvedPath = [System.IO.Path]::GetFullPath($SuppliedInstallerPath)
        Assert-InstallerIdentity -Path $resolvedPath
        Write-Host "Using verified local installer: $resolvedPath"
        return $resolvedPath
    }

    $installerPath = Join-Path $CacheDirectory $InstallerFileName
    if (Test-Path -LiteralPath $installerPath -PathType Leaf) {
        try {
            Assert-InstallerIdentity -Path $installerPath
            Write-Host "Using verified cached installer: $installerPath"
            return $installerPath
        }
        catch {
            Remove-Item -LiteralPath $installerPath -Force
        }
    }

    New-Item -ItemType Directory -Path $CacheDirectory -Force | Out-Null
    $page = Invoke-WebRequest -Uri $InstallerPageUrl -SessionVariable oldVersionSession -Headers @{ 'User-Agent' = 'aim59-compat/0.2' }
    $form = Get-OldVersionDownloadForm -Html $page.Content
    $downloadUri = [Uri]::new([Uri]$InstallerPageUrl, $form.Action).AbsoluteUri
    $temporaryPath = "$installerPath.part"

    try {
        Invoke-WebRequest -Uri $downloadUri -Method Post -WebSession $oldVersionSession -Headers @{
            'Referer' = $InstallerPageUrl
            'User-Agent' = 'aim59-compat/0.2'
        } -Body @{ csrfmiddlewaretoken = $form.CsrfToken } -OutFile $temporaryPath
        Move-Item -LiteralPath $temporaryPath -Destination $installerPath -Force
        Assert-InstallerIdentity -Path $installerPath
    }
    catch {
        Remove-Item -LiteralPath $temporaryPath -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $installerPath -Force -ErrorAction SilentlyContinue
        throw
    }
    return $installerPath
}

function Find-AimDirectory {
    param([string]$RequestedDirectory)

    if (-not [string]::IsNullOrWhiteSpace($RequestedDirectory)) {
        $candidates = @($RequestedDirectory)
    }
    else {
        $candidates = @(
            (Join-Path ${env:ProgramFiles(x86)} 'AIM'),
            (Join-Path $env:ProgramFiles 'AIM')
        ) | Select-Object -Unique
    }
    $matches = @($candidates | Where-Object {
        Test-Path -LiteralPath (Join-Path $_ 'aim.exe') -PathType Leaf
    })
    if ($matches.Count -ne 1) {
        throw "Expected exactly one AIM directory containing aim.exe; found $($matches.Count). Use -AimDirectory to specify it."
    }
    return $matches[0]
}

function Stop-Aim {
    Get-Process -Name 'aim' -ErrorAction SilentlyContinue | Stop-Process -Force
}

function Disable-AimApi {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $original = Join-Path $Directory 'aimapi.dll'
    $disabled = Join-Path $Directory $DisabledAimApiName
    if (Test-Path -LiteralPath $original -PathType Leaf) {
        if (Test-Path -LiteralPath $disabled -PathType Leaf) {
            throw "Both aimapi.dll and $DisabledAimApiName exist. Resolve this manually; no file was changed."
        }
        Rename-Item -LiteralPath $original -NewName $DisabledAimApiName
        Write-Host "Disabled: $original"
        return
    }
    if (Test-Path -LiteralPath $disabled -PathType Leaf) {
        Write-Host "Already disabled: $disabled"
        return
    }
    throw "aimapi.dll was not found in $Directory"
}

function Restore-AimApi {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $original = Join-Path $Directory 'aimapi.dll'
    $disabled = Join-Path $Directory $DisabledAimApiName
    if (Test-Path -LiteralPath $original -PathType Leaf) {
        throw "aimapi.dll already exists in $Directory; no file was changed."
    }
    if (-not (Test-Path -LiteralPath $disabled -PathType Leaf)) {
        throw "No AIM59-disabled aimapi.dll was found in $Directory."
    }
    Rename-Item -LiteralPath $disabled -NewName 'aimapi.dll'
    Write-Host "Restored: $original"
}

function Set-AimServer {
    param(
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port
    )

    New-Item -Path $AimRegistryServerKey -Force | Out-Null
    New-ItemProperty -Path $AimRegistryServerKey -Name 'Host' -PropertyType String -Value $HostName -Force | Out-Null
    New-ItemProperty -Path $AimRegistryServerKey -Name 'Port' -PropertyType DWord -Value $Port -Force | Out-Null
    Write-Host "Configured AIM server: $HostName`:$Port"
}

function Read-ServerPort {
    param([Parameter(Mandatory = $true)][string]$Prompt)

    $enteredPort = Read-Host $Prompt
    if ([string]::IsNullOrWhiteSpace($enteredPort)) {
        return $DefaultServerPort
    }
    [int]$parsedPort = 0
    if (-not [int]::TryParse($enteredPort, [ref]$parsedPort) -or $parsedPort -lt 1 -or $parsedPort -gt 65535) {
        throw 'Server port must be a whole number from 1 through 65535.'
    }
    return $parsedPort
}

function Get-AimServerChoice {
    param(
        [Parameter(Mandatory = $true)][string]$Mode,
        [string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port
    )

    switch ($Mode) {
        'RealRetroLabz' {
            return [pscustomobject]@{ Apply = $true; Host = $DefaultServerHost; Port = $DefaultServerPort }
        }
        'Keep' {
            return [pscustomobject]@{ Apply = $false; Host = $null; Port = $null }
        }
        'Custom' {
            if ([string]::IsNullOrWhiteSpace($HostName)) {
                throw 'ServerMode Custom requires -ServerHost.'
            }
            if ($Port -lt 1 -or $Port -gt 65535) {
                throw 'ServerPort must be a whole number from 1 through 65535.'
            }
            return [pscustomobject]@{ Apply = $true; Host = $HostName; Port = $Port }
        }
        'Prompt' {
            Write-Host ''
            Write-Host 'AIM server choice:'
            Write-Host "  1. Use $DefaultServerHost`:$DefaultServerPort"
            Write-Host '  2. Keep AIM default (login.oscar.aol.com:5190)'
            Write-Host '  3. Enter another host and port'
            $choice = Read-Host 'Choice [1]'
            switch ($choice) {
                '' { return [pscustomobject]@{ Apply = $true; Host = $DefaultServerHost; Port = $DefaultServerPort } }
                '1' { return [pscustomobject]@{ Apply = $true; Host = $DefaultServerHost; Port = $DefaultServerPort } }
                '2' { return [pscustomobject]@{ Apply = $false; Host = $null; Port = $null } }
                '3' {
                    $customHost = Read-Host 'Server host'
                    if ([string]::IsNullOrWhiteSpace($customHost)) {
                        throw 'Server host cannot be empty.'
                    }
                    $customPort = Read-ServerPort -Prompt "Server port [$DefaultServerPort]"
                    return [pscustomobject]@{ Apply = $true; Host = $customHost; Port = $customPort }
                }
                default { throw "Unknown AIM server choice: $choice" }
            }
        }
    }
}

if (-not (Test-IsAdministrator)) {
    throw 'Run this script from an elevated Windows PowerShell session (Run as administrator).'
}

if ($Rollback) {
    $resolvedAimDirectory = Find-AimDirectory -RequestedDirectory $AimDirectory
    Stop-Aim
    if ($PSCmdlet.ShouldProcess($resolvedAimDirectory, 'Restore aimapi.dll')) {
        Restore-AimApi -Directory $resolvedAimDirectory
    }
    Write-Host 'AIM59 compatibility rollback completed. The AIM server preference was left unchanged.'
    exit 0
}

$installer = Get-VerifiedInstaller -CacheDirectory $InstallerCache -SuppliedInstallerPath $InstallerPath
Write-Host "Starting the AIM installer: $installer"
$installerProcess = Start-Process -FilePath $installer -Wait -PassThru
if ($installerProcess.ExitCode -ne 0) {
    throw "AIM installer exited with code $($installerProcess.ExitCode)."
}

$resolvedAimDirectory = Find-AimDirectory -RequestedDirectory $AimDirectory
$serverChoice = Get-AimServerChoice -Mode $ServerMode -HostName $ServerHost -Port $ServerPort
Stop-Aim
if ($PSCmdlet.ShouldProcess($resolvedAimDirectory, 'Disable aimapi.dll and apply the selected AIM server choice')) {
    Disable-AimApi -Directory $resolvedAimDirectory
    if ($serverChoice.Apply) {
        Set-AimServer -HostName $serverChoice.Host -Port $serverChoice.Port
    }
    else {
        Write-Host 'Left the existing AIM server preference unchanged.'
    }
}

Write-Host "AIM 5.9.3861 is installed and patched. Launch: $(Join-Path $resolvedAimDirectory 'aim.exe')"
