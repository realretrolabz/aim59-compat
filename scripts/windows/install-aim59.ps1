<#
.NOTES
ARCHIVED PROOF OF CONCEPT. This script records the validated native-Windows
workflow that preceded the self-contained rrlzAIM.exe implementation. It is
not invoked by the EXE or distributed as part of the active Windows workflow.

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
    [ValidateSet('Prompt', 'realretrolabz', 'Keep', 'Custom')]
    [string]$ServerMode = 'Prompt',

    [Parameter(ParameterSetName = 'Install')]
    [string]$ServerHost,

    [Parameter(ParameterSetName = 'Install')]
    [int]$ServerPort = 5190,

    [Parameter(ParameterSetName = 'Install')]
    [ValidateNotNullOrEmpty()]
    [string]$InstallerCache = (Join-Path $env:LOCALAPPDATA 'rrlzAIM\installers'),

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
$InstallerCompletionTimeoutSeconds = 900
$InstallerCompletionPollSeconds = 2
$InstallerFileSettleSeconds = 8

function Write-Status {
    param([Parameter(Mandatory = $true)][string]$Message)

    [Console]::Out.WriteLine($Message)
    [Console]::Out.Flush()
}

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

function Invoke-OldVersionDownload {
    param(
        [Parameter(Mandatory = $true)][Uri]$Uri,
        [Parameter(Mandatory = $true)][object]$Session,
        [Parameter(Mandatory = $true)][string]$CsrfToken,
        [Parameter(Mandatory = $true)][string]$DestinationPath
    )

    [byte[]]$requestBody = [Text.Encoding]::UTF8.GetBytes(
        'csrfmiddlewaretoken=' + [Uri]::EscapeDataString($CsrfToken)
    )
    [Net.HttpWebRequest]$request = [Net.HttpWebRequest]::Create($Uri)
    $request.Method = 'POST'
    $request.CookieContainer = $Session.Cookies
    $request.ContentType = 'application/x-www-form-urlencoded'
    $request.ContentLength = $requestBody.Length
    $request.Referer = $InstallerPageUrl
    $request.UserAgent = 'rrlzAIM/0.2'

    $requestStream = $null
    $response = $null
    $responseStream = $null
    $destinationStream = $null
    try {
        $requestStream = $request.GetRequestStream()
        $requestStream.Write($requestBody, 0, $requestBody.Length)
        $requestStream.Dispose()
        $requestStream = $null

        $response = $request.GetResponse()
        $responseStream = $response.GetResponseStream()
        $destinationStream = [IO.File]::Open(
            $DestinationPath,
            [IO.FileMode]::Create,
            [IO.FileAccess]::Write,
            [IO.FileShare]::None
        )

        [byte[]]$buffer = New-Object byte[] 65536
        [int64]$downloadedBytes = 0
        [int]$currentPercent = 0
        [int]$nextProgressPercent = 5
        Write-Status "Download progress: 0% (0 of $InstallerSize bytes)"

        while (($read = $responseStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $destinationStream.Write($buffer, 0, $read)
            $downloadedBytes += $read
            [int]$currentPercent = [Math]::Min(
                100,
                [Math]::Floor((100 * $downloadedBytes) / $InstallerSize)
            )
            if ($currentPercent -ge $nextProgressPercent) {
                Write-Status "Download progress: $currentPercent% ($downloadedBytes of $InstallerSize bytes)"
                $nextProgressPercent = $currentPercent + 5
            }
        }

        if ($downloadedBytes -eq $InstallerSize -and $currentPercent -lt 100) {
            Write-Status "Download progress: 100% ($downloadedBytes of $InstallerSize bytes)"
        }
        Write-Status "Download complete: $downloadedBytes bytes. Verifying identity."
    }
    finally {
        if ($null -ne $destinationStream) { $destinationStream.Dispose() }
        if ($null -ne $responseStream) { $responseStream.Dispose() }
        if ($null -ne $response) { $response.Dispose() }
        if ($null -ne $requestStream) { $requestStream.Dispose() }
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
        Write-Status "Using verified local installer: $resolvedPath"
        return $resolvedPath
    }

    $installerPath = Join-Path $CacheDirectory $InstallerFileName
    if (Test-Path -LiteralPath $installerPath -PathType Leaf) {
        try {
            Assert-InstallerIdentity -Path $installerPath
            Write-Status "Using verified cached installer: $installerPath"
            return $installerPath
        }
        catch {
            Remove-Item -LiteralPath $installerPath -Force
        }
    }

    New-Item -ItemType Directory -Path $CacheDirectory -Force | Out-Null
    $page = Invoke-WebRequest -Uri $InstallerPageUrl -SessionVariable oldVersionSession -Headers @{ 'User-Agent' = 'rrlzAIM/0.2' }
    $form = Get-OldVersionDownloadForm -Html $page.Content
    $downloadUri = [Uri]::new([Uri]$InstallerPageUrl, $form.Action).AbsoluteUri
    $temporaryPath = "$installerPath.part"

    try {
        Invoke-OldVersionDownload -Uri $downloadUri -Session $oldVersionSession -CsrfToken $form.CsrfToken -DestinationPath $temporaryPath
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

function Wait-For-AimInstallation {
    param(
        [string]$RequestedDirectory,
        [Parameter(Mandatory = $true)][System.Diagnostics.Process]$InstallerProcess
    )

    $deadline = (Get-Date).AddSeconds($InstallerCompletionTimeoutSeconds)
    $nextStatus = Get-Date
    $lastDiscoveryError = $null
    $lastFileSignature = $null
    $filesStableSince = $null

    while ((Get-Date) -lt $deadline) {
        if ($InstallerProcess.HasExited -and $InstallerProcess.ExitCode -ne 0) {
            throw "AIM installer exited with code $($InstallerProcess.ExitCode)."
        }

        try {
            $aimDirectory = Find-AimDirectory -RequestedDirectory $RequestedDirectory
            $aimExe = Get-Item -LiteralPath (Join-Path $aimDirectory 'aim.exe') -Force
            $aimApiPath = Join-Path $aimDirectory 'aimapi.dll'
            $aimApi = Get-Item -LiteralPath $aimApiPath -Force
            $fileSignature = "$($aimExe.Length):$($aimExe.LastWriteTimeUtc.Ticks):$($aimApi.Length):$($aimApi.LastWriteTimeUtc.Ticks)"
            if ($fileSignature -ne $lastFileSignature) {
                $lastFileSignature = $fileSignature
                $filesStableSince = Get-Date
            }
            elseif ($null -ne $filesStableSince -and ((Get-Date) - $filesStableSince).TotalSeconds -ge $InstallerFileSettleSeconds) {
                return $aimDirectory
            }
        }
        catch {
            $lastDiscoveryError = $_
            $lastFileSignature = $null
            $filesStableSince = $null
        }

        if ((Get-Date) -ge $nextStatus) {
            Write-Status 'Waiting for the AIM installer to create stable aim.exe and aimapi.dll files. The compatibility changes will run automatically afterwards.'
            $nextStatus = (Get-Date).AddSeconds(30)
        }
        Start-Sleep -Seconds $InstallerCompletionPollSeconds
    }

    $reason = if ($null -ne $lastDiscoveryError) { $lastDiscoveryError.Exception.Message } else { 'AIM was not found.' }
    throw "AIM installation was not detected within $InstallerCompletionTimeoutSeconds seconds. $reason"
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
        Write-Status "Disabled: $original"
        return
    }
    if (Test-Path -LiteralPath $disabled -PathType Leaf) {
        Write-Status "Already disabled: $disabled"
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
    Write-Status "Restored: $original"
}

function Set-AimServer {
    param(
        [Parameter(Mandatory = $true)][string]$HostName,
        [Parameter(Mandatory = $true)][int]$Port
    )

    New-Item -Path $AimRegistryServerKey -Force | Out-Null
    New-ItemProperty -Path $AimRegistryServerKey -Name 'Host' -PropertyType String -Value $HostName -Force | Out-Null
    New-ItemProperty -Path $AimRegistryServerKey -Name 'Port' -PropertyType DWord -Value $Port -Force | Out-Null
    Write-Status "Configured AIM server: $HostName`:$Port"
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
        'realretrolabz' {
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
            Write-Status 'AIM server choice:'
            Write-Status "  1. Use $DefaultServerHost`:$DefaultServerPort"
            Write-Status '  2. Keep AIM default (login.oscar.aol.com:5190)'
            Write-Status '  3. Enter another host and port'
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
    Write-Status 'AIM59 compatibility rollback completed. The AIM server preference was left unchanged.'
    exit 0
}

$installer = Get-VerifiedInstaller -CacheDirectory $InstallerCache -SuppliedInstallerPath $InstallerPath
Write-Status "Starting the AIM installer: $installer"
$installerProcess = Start-Process -FilePath $installer -PassThru
$resolvedAimDirectory = Wait-For-AimInstallation -RequestedDirectory $AimDirectory -InstallerProcess $installerProcess
$serverChoice = Get-AimServerChoice -Mode $ServerMode -HostName $ServerHost -Port $ServerPort
Stop-Aim
if ($PSCmdlet.ShouldProcess($resolvedAimDirectory, 'Disable aimapi.dll and apply the selected AIM server choice')) {
    Disable-AimApi -Directory $resolvedAimDirectory
    if ($serverChoice.Apply) {
        Set-AimServer -HostName $serverChoice.Host -Port $serverChoice.Port
    }
    else {
        Write-Status 'Left the existing AIM server preference unchanged.'
    }
}

Write-Status "AIM 5.9.3861 is installed and patched. Launch: $(Join-Path $resolvedAimDirectory 'aim.exe')"
