<#
.SYNOPSIS
Collects read-only AIM 5.9 discovery data at a named Windows checkpoint.

.DESCRIPTION
Writes a targeted JSON snapshot to an explicitly selected, empty output
directory.  It never installs or launches AIM, changes the registry, registers
DLLs, applies compatibility settings, or copies AIM program files.  The
Compare parameter set reads two existing snapshots and writes a focused diff.

Raw snapshots can contain machine paths, account names, AIM metadata, and
registry preferences.  Keep them on the private evidence volume, never in the
project checkout.
#>
[CmdletBinding(DefaultParameterSetName = 'Collect')]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateNotNullOrEmpty()]
    [string]$OutputDirectory,

    [Parameter(Mandatory = $true, ParameterSetName = 'Collect')]
    [ValidateSet(
        '00-clean',
        '10-after-install',
        '20-after-first-launch',
        '30-after-aim-exit',
        '40-after-uninstall-or-restore'
    )]
    [string]$Checkpoint,

    [Parameter(Mandatory = $true, ParameterSetName = 'Compare')]
    [ValidateNotNullOrEmpty()]
    [string]$BaselineDirectory,

    [Parameter(Mandatory = $true, ParameterSetName = 'Compare')]
    [ValidateNotNullOrEmpty()]
    [string]$ComparisonDirectory
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:CollectionErrors = [System.Collections.Generic.List[object]]::new()
$script:CandidateDirectories = [System.Collections.Generic.List[object]]::new()
$script:CandidateDirectoryIndex = @{}

function Test-PathIsWithin {
    param(
        [Parameter(Mandatory = $true)][string]$Child,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $childFull = [System.IO.Path]::GetFullPath($Child).TrimEnd('\')
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\')
    if ($childFull.Equals($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    return $childFull.StartsWith(
        $parentFull + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Find-RepositoryRoot {
    $current = Get-Item -LiteralPath $PSScriptRoot -Force
    while ($null -ne $current) {
        if (Test-Path -LiteralPath (Join-Path $current.FullName '.git') -PathType Container) {
            return $current.FullName
        }
        $current = $current.Parent
    }
    return $null
}

function Initialize-OutputDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    $scriptRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
    if (Test-PathIsWithin -Child $fullPath -Parent $scriptRoot) {
        throw "OutputDirectory must be outside the collector directory: $scriptRoot"
    }
    $repositoryRoot = Find-RepositoryRoot
    if (
        ($null -ne $repositoryRoot) -and
        (Test-PathIsWithin -Child $fullPath -Parent $repositoryRoot)
    ) {
        throw "OutputDirectory must be outside the repository: $repositoryRoot"
    }

    if (Test-Path -LiteralPath $fullPath) {
        if (-not (Test-Path -LiteralPath $fullPath -PathType Container)) {
            throw "OutputDirectory exists but is not a directory: $fullPath"
        }
        if ($null -ne (Get-ChildItem -LiteralPath $fullPath -Force | Select-Object -First 1)) {
            throw "OutputDirectory must be new or empty: $fullPath"
        }
    }
    else {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
    return $fullPath
}

function Write-OutputArtifact {
    param(
        [Parameter(Mandatory = $true)][string]$OutputRoot,
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)]$Contents
    )

    $destination = [System.IO.Path]::GetFullPath((Join-Path $OutputRoot $Name))
    if (-not (Test-PathIsWithin -Child $destination -Parent $OutputRoot)) {
        throw "Refusing to write outside OutputDirectory: $destination"
    }
    [System.IO.File]::WriteAllText(
        $destination,
        $Contents,
        [System.Text.UTF8Encoding]::new($false)
    )
}

function Add-CollectionError {
    param(
        [Parameter(Mandatory = $true)][string]$Area,
        [Parameter(Mandatory = $true)]$Exception
    )

    $script:CollectionErrors.Add([pscustomobject]@{
        area = $Area
        message = $Exception.Exception.Message
    }) | Out-Null
}

function Invoke-CollectionSection {
    param(
        [Parameter(Mandatory = $true)][string]$Area,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    try {
        return & $Action
    }
    catch {
        Add-CollectionError -Area $Area -Exception $_
        return $null
    }
}

function Get-ElevationState {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    finally {
        $identity.Dispose()
    }
}

function Get-SystemSnapshot {
    $operatingSystem = Get-CimInstance -ClassName Win32_OperatingSystem
    $computerSystem = Get-CimInstance -ClassName Win32_ComputerSystem
    return [pscustomobject]@{
        caption = $operatingSystem.Caption
        version = $operatingSystem.Version
        buildNumber = $operatingSystem.BuildNumber
        osArchitecture = $operatingSystem.OSArchitecture
        is64BitOperatingSystem = [Environment]::Is64BitOperatingSystem
        systemType = $computerSystem.SystemType
        hypervisorPresent = $computerSystem.HypervisorPresent
        isElevated = Get-ElevationState
        powershellVersion = $PSVersionTable.PSVersion.ToString()
    }
}

function Get-AimProcesses {
    $processes = Get-CimInstance -ClassName Win32_Process -Filter "Name = 'aim.exe'"
    return @(
        $processes | ForEach-Object {
            [pscustomobject]@{
                processId = $_.ProcessId
                parentProcessId = $_.ParentProcessId
                name = $_.Name
                executablePath = $_.ExecutablePath
            }
        } | Sort-Object processId
    )
}

function Convert-RegistryValueForOutput {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][Microsoft.Win32.RegistryValueKind]$Kind
    )

    switch ($Kind) {
        'Binary' {
            if ($Value -is [byte[]]) {
                return [pscustomobject]@{ byteLength = $Value.Length }
            }
            return [pscustomobject]@{ byteLength = $null }
        }
        'MultiString' {
            return @($Value | ForEach-Object { [string]$_ })
        }
        default {
            return $Value
        }
    }
}

function Get-SafeRegistryValues {
    param([Parameter(Mandatory = $true)][Microsoft.Win32.RegistryKey]$Key)

    $values = [System.Collections.Generic.List[object]]::new()
    foreach ($name in @($Key.GetValueNames() | Sort-Object)) {
        $kind = $Key.GetValueKind($name)
        $value = $Key.GetValue(
            $name,
            $null,
            [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
        )
        $values.Add([pscustomobject]@{
            name = if ($name.Length -eq 0) { '(Default)' } else { $name }
            kind = $kind.ToString()
            value = Convert-RegistryValueForOutput -Value $value -Kind $kind
        }) | Out-Null
    }
    return @($values)
}

function Get-RegistryDirectKey {
    param(
        [Parameter(Mandatory = $true)][Microsoft.Win32.RegistryKey]$BaseKey,
        [Parameter(Mandatory = $true)][string]$SubKey
    )

    $key = $BaseKey.OpenSubKey($SubKey, $false)
    if ($null -eq $key) {
        return [pscustomobject]@{ key = $SubKey; present = $false; values = @() }
    }
    try {
        return [pscustomobject]@{
            key = $SubKey
            present = $true
            values = @(Get-SafeRegistryValues -Key $key)
        }
    }
    finally {
        $key.Dispose()
    }
}

function Test-AimMarker {
    param([AllowNull()][object]$Value)

    if ($null -eq $Value) {
        return $false
    }
    $text = [string]$Value
    return $text -match '(?i)(?:\baim(?:\d+)?\b|\baol\b|america online|\\(?:aim|aol)(?:\\|$)|(?:^|[\\/])aimapi\.dll(?:$|\s)|(?:^|[\\/])sb\.dll(?:$|\s))'
}

function Get-MatchingRegistryValues {
    param(
        [Parameter(Mandatory = $true)][Microsoft.Win32.RegistryKey]$BaseKey,
        [Parameter(Mandatory = $true)][string]$SubKey
    )

    $key = $BaseKey.OpenSubKey($SubKey, $false)
    if ($null -eq $key) {
        return [pscustomobject]@{ key = $SubKey; present = $false; values = @() }
    }
    try {
        $matching = [System.Collections.Generic.List[object]]::new()
        foreach ($name in @($key.GetValueNames() | Sort-Object)) {
            $kind = $key.GetValueKind($name)
            $value = $key.GetValue(
                $name,
                $null,
                [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
            )
            if ((Test-AimMarker $name) -or (Test-AimMarker $value)) {
                $matching.Add([pscustomobject]@{
                    name = if ($name.Length -eq 0) { '(Default)' } else { $name }
                    kind = $kind.ToString()
                    value = Convert-RegistryValueForOutput -Value $value -Kind $kind
                }) | Out-Null
            }
        }
        return [pscustomobject]@{
            key = $SubKey
            present = $true
            values = @($matching)
        }
    }
    finally {
        $key.Dispose()
    }
}

function Get-AimUninstallEntries {
    param([Parameter(Mandatory = $true)][Microsoft.Win32.RegistryKey]$BaseKey)

    $uninstallPath = 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    $uninstallKey = $BaseKey.OpenSubKey($uninstallPath, $false)
    if ($null -eq $uninstallKey) {
        return @()
    }
    try {
        $entries = [System.Collections.Generic.List[object]]::new()
        foreach ($subKeyName in @($uninstallKey.GetSubKeyNames() | Sort-Object)) {
            $subKey = $uninstallKey.OpenSubKey($subKeyName, $false)
            if ($null -eq $subKey) {
                continue
            }
            try {
                $displayName = $subKey.GetValue('DisplayName', $null)
                if (Test-AimMarker $displayName) {
                    $entries.Add([pscustomobject]@{
                        key = "$uninstallPath\\$subKeyName"
                        values = @(Get-SafeRegistryValues -Key $subKey)
                    }) | Out-Null
                }
            }
            finally {
                $subKey.Dispose()
            }
        }
        return @($entries)
    }
    finally {
        $uninstallKey.Dispose()
    }
}

function Get-AimClassKeys {
    param([Parameter(Mandatory = $true)][Microsoft.Win32.RegistryKey]$BaseKey)

    $classesPath = 'SOFTWARE\Classes'
    $classesKey = $BaseKey.OpenSubKey($classesPath, $false)
    if ($null -eq $classesKey) {
        return @()
    }
    try {
        $results = [System.Collections.Generic.List[object]]::new()
        foreach ($subKeyName in @($classesKey.GetSubKeyNames() | Sort-Object)) {
            if (-not (Test-AimMarker $subKeyName)) {
                continue
            }
            $key = $classesKey.OpenSubKey($subKeyName, $false)
            if ($null -eq $key) {
                continue
            }
            try {
                $results.Add([pscustomobject]@{
                    key = "$classesPath\\$subKeyName"
                    values = @(Get-SafeRegistryValues -Key $key)
                }) | Out-Null
            }
            finally {
                $key.Dispose()
            }
        }
        return @($results)
    }
    finally {
        $classesKey.Dispose()
    }
}

function Get-AimComServers {
    param([Parameter(Mandatory = $true)][Microsoft.Win32.RegistryKey]$BaseKey)

    $clsidPath = 'SOFTWARE\Classes\CLSID'
    $clsidKey = $BaseKey.OpenSubKey($clsidPath, $false)
    if ($null -eq $clsidKey) {
        return @()
    }
    try {
        $results = [System.Collections.Generic.List[object]]::new()
        foreach ($clsid in @($clsidKey.GetSubKeyNames() | Sort-Object)) {
            $classKey = $clsidKey.OpenSubKey($clsid, $false)
            if ($null -eq $classKey) {
                continue
            }
            try {
                foreach ($serverName in @('InprocServer32', 'LocalServer32')) {
                    $serverKey = $classKey.OpenSubKey($serverName, $false)
                    if ($null -eq $serverKey) {
                        continue
                    }
                    try {
                        $serverPath = $serverKey.GetValue(
                            '',
                            $null,
                            [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames
                        )
                        if (Test-AimMarker $serverPath) {
                            $results.Add([pscustomobject]@{
                                clsid = $clsid
                                serverKey = "$clsidPath\\$clsid\\$serverName"
                                serverPath = $serverPath
                            }) | Out-Null
                        }
                    }
                    finally {
                        $serverKey.Dispose()
                    }
                }
            }
            finally {
                $classKey.Dispose()
            }
        }
        return @($results)
    }
    finally {
        $clsidKey.Dispose()
    }
}

function Get-RegistryViewSnapshot {
    param(
        [Parameter(Mandatory = $true)][Microsoft.Win32.RegistryHive]$Hive,
        [Parameter(Mandatory = $true)][Microsoft.Win32.RegistryView]$View
    )

    $baseKey = [Microsoft.Win32.RegistryKey]::OpenBaseKey($Hive, $View)
    try {
        return [pscustomobject]@{
            hive = $Hive.ToString()
            view = if ($View -eq [Microsoft.Win32.RegistryView]::Registry64) {
                'Registry64 (64-bit view)'
            }
            else {
                'Registry32 (32-bit/WOW64 view)'
            }
            aimKeys = @(
                Get-RegistryDirectKey -BaseKey $baseKey -SubKey 'SOFTWARE\America Online\AIM'
                Get-RegistryDirectKey -BaseKey $baseKey -SubKey 'SOFTWARE\AOL\AIM'
                Get-RegistryDirectKey -BaseKey $baseKey -SubKey 'SOFTWARE\AIM'
            )
            appPaths = @(
                Get-RegistryDirectKey -BaseKey $baseKey -SubKey 'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\aim.exe'
            )
            appCompat = @(
                Get-MatchingRegistryValues -BaseKey $baseKey -SubKey 'SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers'
                Get-MatchingRegistryValues -BaseKey $baseKey -SubKey 'SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Compatibility Assistant\Store'
            )
            uninstallEntries = @(Get-AimUninstallEntries -BaseKey $baseKey)
            classKeys = @(Get-AimClassKeys -BaseKey $baseKey)
            comServers = @(Get-AimComServers -BaseKey $baseKey)
        }
    }
    finally {
        $baseKey.Dispose()
    }
}

function Add-CandidateDirectory {
    param(
        [AllowNull()][string]$Path,
        [Parameter(Mandatory = $true)][string]$Source
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return
    }
    $candidate = [Environment]::ExpandEnvironmentVariables($Path.Trim(' ', '"'))
    if ($candidate -match '(?i)^(.+\.(exe|dll|ocm))(?:\s.*)?$') {
        $candidate = Split-Path -Path $matches[1] -Parent
    }
    try {
        $candidate = [System.IO.Path]::GetFullPath($candidate)
    }
    catch {
        return
    }
    $key = $candidate.TrimEnd('\\').ToLowerInvariant()
    if ($script:CandidateDirectoryIndex.ContainsKey($key)) {
        $script:CandidateDirectoryIndex[$key].sources.Add($Source) | Out-Null
        return
    }
    $entry = [pscustomobject]@{
        path = $candidate
        sources = [System.Collections.Generic.List[string]]::new()
    }
    $entry.sources.Add($Source) | Out-Null
    $script:CandidateDirectoryIndex[$key] = $entry
    $script:CandidateDirectories.Add($entry) | Out-Null
}

function Get-StringsFromObject {
    param([AllowNull()]$Value)

    if ($null -eq $Value) {
        return @()
    }
    if ($Value -is [string]) {
        return @($Value)
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $result = [System.Collections.Generic.List[string]]::new()
        foreach ($entry in $Value.GetEnumerator()) {
            foreach ($text in Get-StringsFromObject $entry.Value) {
                $result.Add($text) | Out-Null
            }
        }
        return @($result)
    }
    if ($Value -is [System.Collections.IEnumerable]) {
        $result = [System.Collections.Generic.List[string]]::new()
        foreach ($entry in $Value) {
            foreach ($text in Get-StringsFromObject $entry) {
                $result.Add($text) | Out-Null
            }
        }
        return @($result)
    }
    if ($Value -is [pscustomobject]) {
        $result = [System.Collections.Generic.List[string]]::new()
        foreach ($property in $Value.PSObject.Properties) {
            foreach ($text in Get-StringsFromObject $property.Value) {
                $result.Add($text) | Out-Null
            }
        }
        return @($result)
    }
    return @([string]$Value)
}

function Add-RegistryCandidateDirectories {
    param([AllowNull()]$RegistryViews)

    foreach ($text in Get-StringsFromObject $RegistryViews) {
        $expanded = [Environment]::ExpandEnvironmentVariables($text)
        if (
            (Test-AimMarker $expanded) -and
            ($expanded -match '(?i)^(?:[a-z]:\\|\\\\)')
        ) {
            Add-CandidateDirectory -Path $expanded -Source 'targeted registry value'
        }
    }
}

function Get-CandidateInstallationPaths {
    $programFiles = @(
        [Environment]::GetEnvironmentVariable('ProgramFiles'),
        [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($base in $programFiles) {
        Add-CandidateDirectory -Path (Join-Path $base 'AIM') -Source 'standard Program Files location'
        Add-CandidateDirectory -Path (Join-Path $base 'America Online\AIM') -Source 'standard Program Files location'
    }
    return @(
        $script:CandidateDirectories | Sort-Object path | ForEach-Object {
            [pscustomobject]@{
                path = $_.path
                exists = Test-Path -LiteralPath $_.path -PathType Container
                sources = @($_.sources | Sort-Object -Unique)
            }
        }
    )
}

function Get-FileMetadata {
    param([Parameter(Mandatory = $true)][string]$Path)

    $item = Get-Item -LiteralPath $Path -Force
    $hash = Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256
    $version = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($item.FullName)
    return [pscustomobject]@{
        path = $item.FullName
        name = $item.Name
        size = $item.Length
        sha256 = $hash.Hash.ToLowerInvariant()
        peVersion = [pscustomobject]@{
            fileVersion = $version.FileVersion
            productVersion = $version.ProductVersion
            fileDescription = $version.FileDescription
            originalFilename = $version.OriginalFilename
        }
    }
}

function Get-AimFileInventory {
    param([AllowNull()]$Installations)

    $inventory = [System.Collections.Generic.List[object]]::new()
    foreach ($installation in @($Installations | Where-Object { $_.exists })) {
        try {
            $files = Get-ChildItem -LiteralPath $installation.path -File -Recurse -Force |
                Where-Object { $_.Extension -match '(?i)^\.(exe|dll|ocm)$' } |
                Sort-Object FullName
            foreach ($file in $files) {
                $inventory.Add((Get-FileMetadata -Path $file.FullName)) | Out-Null
            }
        }
        catch {
            Add-CollectionError -Area "file inventory for $($installation.path)" -Exception $_
        }
    }
    return @($inventory)
}

function Get-XpcsPathReferences {
    param([Parameter(Mandatory = $true)][string]$Path)

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $pathPattern = '(?i)(?:[a-z]:\\|\\\\)[^\x00-\x1f"<>|?*]+'
    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($encoding in @(
        [System.Text.Encoding]::GetEncoding(1252),
        [System.Text.Encoding]::Unicode,
        [System.Text.Encoding]::BigEndianUnicode
    )) {
        $text = $encoding.GetString($bytes)
        foreach ($match in [regex]::Matches($text, $pathPattern)) {
            $reference = $match.Value.TrimEnd(' ', '.', ';', ',', ')', ']')
            if ($reference.Length -gt 0) {
                $seen.Add($reference) | Out-Null
            }
        }
    }
    return @($seen | Sort-Object)
}

function Get-XpcsInventory {
    param([AllowNull()]$Installations)

    $results = [System.Collections.Generic.List[object]]::new()
    foreach ($installation in @($Installations | Where-Object { $_.exists })) {
        try {
            $files = Get-ChildItem -LiteralPath $installation.path -File -Recurse -Force -Filter 'Xpcs Registry.dat'
            foreach ($file in $files) {
                $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
                $results.Add([pscustomobject]@{
                    path = $file.FullName
                    size = $file.Length
                    sha256 = $hash.Hash.ToLowerInvariant()
                    absolutePathReferences = @(Get-XpcsPathReferences -Path $file.FullName)
                }) | Out-Null
            }
        }
        catch {
            Add-CollectionError -Area "Xpcs Registry.dat scan for $($installation.path)" -Exception $_
        }
    }
    return @($results)
}

function Get-AppDataCandidates {
    $roots = @(
        [Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData),
        [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $paths = [System.Collections.Generic.List[object]]::new()
    foreach ($root in $roots) {
        foreach ($suffix in @('AIM', 'America Online\AIM')) {
            $path = Join-Path $root $suffix
            $paths.Add([pscustomobject]@{
                path = $path
                exists = Test-Path -LiteralPath $path -PathType Container
            }) | Out-Null
        }
    }
    return @($paths | Sort-Object path -Unique)
}

function Get-SystemRuntimeInventory {
    $windowsDirectory = [Environment]::GetFolderPath([Environment+SpecialFolder]::Windows)
    $locations = @(
        [pscustomobject]@{ component = 'mfc40.dll'; architecture = '64-bit system directory'; path = Join-Path $windowsDirectory 'System32\mfc40.dll' },
        [pscustomobject]@{ component = 'mfc40.dll'; architecture = '32-bit/WOW64 system directory'; path = Join-Path $windowsDirectory 'SysWOW64\mfc40.dll' },
        [pscustomobject]@{ component = 'regsvr32.exe'; architecture = '64-bit system directory'; path = Join-Path $windowsDirectory 'System32\regsvr32.exe' },
        [pscustomobject]@{ component = 'regsvr32.exe'; architecture = '32-bit/WOW64 system directory'; path = Join-Path $windowsDirectory 'SysWOW64\regsvr32.exe' }
    )
    $results = [System.Collections.Generic.List[object]]::new()
    foreach ($location in $locations) {
        $entry = [ordered]@{
            component = $location.component
            architecture = $location.architecture
            path = $location.path
            present = Test-Path -LiteralPath $location.path -PathType Leaf
        }
        if ($entry.present) {
            $entry.metadata = Get-FileMetadata -Path $location.path
        }
        $results.Add([pscustomobject]$entry) | Out-Null
    }
    return @($results)
}

function Get-DiscoveryJsonPath {
    param([Parameter(Mandatory = $true)][string]$Directory)

    $path = Join-Path ([System.IO.Path]::GetFullPath($Directory)) 'discovery.json'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Discovery snapshot not found: $path"
    }
    return $path
}

function Get-FlatEntries {
    param(
        [AllowNull()]$Value,
        [Parameter(Mandatory = $true)][string]$Prefix
    )

    if ($null -eq $Value) {
        return @("$Prefix=<null>")
    }
    if ($Value -is [string] -or $Value -is [ValueType]) {
        return @("$Prefix=$($Value | ConvertTo-Json -Compress)")
    }
    if ($Value -is [System.Collections.IDictionary]) {
        $entries = [System.Collections.Generic.List[string]]::new()
        foreach ($key in @($Value.Keys | Sort-Object)) {
            foreach ($entry in Get-FlatEntries -Value $Value[$key] -Prefix "$Prefix.$key") {
                $entries.Add($entry) | Out-Null
            }
        }
        return @($entries)
    }
    if ($Value -is [System.Collections.IEnumerable]) {
        $entries = [System.Collections.Generic.List[string]]::new()
        $index = 0
        foreach ($item in $Value) {
            foreach ($entry in Get-FlatEntries -Value $item -Prefix "$Prefix[$index]") {
                $entries.Add($entry) | Out-Null
            }
            $index++
        }
        if ($index -eq 0) {
            $entries.Add("$Prefix=[]") | Out-Null
        }
        return @($entries)
    }
    if ($Value -is [pscustomobject]) {
        $entries = [System.Collections.Generic.List[string]]::new()
        foreach ($property in $Value.PSObject.Properties) {
            foreach ($entry in Get-FlatEntries -Value $property.Value -Prefix "$Prefix.$($property.Name)") {
                $entries.Add($entry) | Out-Null
            }
        }
        return @($entries)
    }
    return @("$Prefix=$($Value | ConvertTo-Json -Compress)")
}

function New-DiscoveryComparison {
    param(
        [Parameter(Mandatory = $true)]$Baseline,
        [Parameter(Mandatory = $true)]$Comparison
    )

    $sections = @('processes', 'registryViews', 'candidateInstallations', 'appDataCandidates', 'fileInventory', 'xpcsRegistry', 'runtimes')
    $changes = [System.Collections.Generic.List[object]]::new()
    foreach ($section in $sections) {
        $before = @(Get-FlatEntries -Value $Baseline.$section -Prefix $section | Sort-Object)
        $after = @(Get-FlatEntries -Value $Comparison.$section -Prefix $section | Sort-Object)
        foreach ($difference in @(Compare-Object -ReferenceObject $before -DifferenceObject $after)) {
            $changes.Add([pscustomobject]@{
                section = $section
                change = if ($difference.SideIndicator -eq '=>') { 'added after baseline' } else { 'removed after baseline' }
                detail = $difference.InputObject
            }) | Out-Null
        }
    }
    return [pscustomobject]@{
        schema = 'aim59.windows.discovery-comparison/v1'
        generatedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
        baselineCheckpoint = $Baseline.checkpoint
        comparisonCheckpoint = $Comparison.checkpoint
        changes = @($changes)
    }
}

$outputRoot = Initialize-OutputDirectory -Path $OutputDirectory

if ($PSCmdlet.ParameterSetName -eq 'Compare') {
    $baselinePath = Get-DiscoveryJsonPath -Directory $BaselineDirectory
    $comparisonPath = Get-DiscoveryJsonPath -Directory $ComparisonDirectory
    $baseline = Get-Content -LiteralPath $baselinePath -Raw | ConvertFrom-Json
    $comparison = Get-Content -LiteralPath $comparisonPath -Raw | ConvertFrom-Json
    $result = New-DiscoveryComparison -Baseline $baseline -Comparison $comparison
    Write-OutputArtifact -OutputRoot $outputRoot -Name 'comparison.json' -Contents ($result | ConvertTo-Json -Depth 20)
    $summary = "AIM59 discovery comparison`r`nBaseline: $($result.baselineCheckpoint)`r`nComparison: $($result.comparisonCheckpoint)`r`nChanges: $($result.changes.Count)`r`n"
    Write-OutputArtifact -OutputRoot $outputRoot -Name 'comparison-summary.txt' -Contents $summary
    Write-Host "Comparison written to $outputRoot"
    exit 0
}

$system = Invoke-CollectionSection -Area 'Windows identity' -Action { Get-SystemSnapshot }
$processes = Invoke-CollectionSection -Area 'AIM processes' -Action { Get-AimProcesses }
$registryViews = Invoke-CollectionSection -Area 'targeted registry views' -Action {
    @(
        Get-RegistryViewSnapshot -Hive ([Microsoft.Win32.RegistryHive]::LocalMachine) -View ([Microsoft.Win32.RegistryView]::Registry64)
        Get-RegistryViewSnapshot -Hive ([Microsoft.Win32.RegistryHive]::LocalMachine) -View ([Microsoft.Win32.RegistryView]::Registry32)
        Get-RegistryViewSnapshot -Hive ([Microsoft.Win32.RegistryHive]::CurrentUser) -View ([Microsoft.Win32.RegistryView]::Registry64)
        Get-RegistryViewSnapshot -Hive ([Microsoft.Win32.RegistryHive]::CurrentUser) -View ([Microsoft.Win32.RegistryView]::Registry32)
    )
}
$candidateInstallations = Invoke-CollectionSection -Area 'candidate installation paths' -Action {
    Add-RegistryCandidateDirectories -RegistryViews $registryViews
    foreach ($process in @($processes)) {
        if ($null -ne $process -and -not [string]::IsNullOrWhiteSpace($process.executablePath)) {
            Add-CandidateDirectory -Path $process.executablePath -Source 'running aim.exe'
        }
    }
    Get-CandidateInstallationPaths
}
$fileInventory = Invoke-CollectionSection -Area 'AIM file metadata' -Action {
    Get-AimFileInventory -Installations $candidateInstallations
}
$xpcsRegistry = Invoke-CollectionSection -Area 'Xpcs Registry.dat path references' -Action {
    Get-XpcsInventory -Installations $candidateInstallations
}
$appDataCandidates = Invoke-CollectionSection -Area 'candidate AppData paths' -Action {
    Get-AppDataCandidates
}
$runtimes = Invoke-CollectionSection -Area 'mfc40 runtime' -Action {
    Get-SystemRuntimeInventory
}

$snapshot = [pscustomobject]@{
    schema = 'aim59.windows.discovery/v1'
    checkpoint = $Checkpoint
    collectedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
    system = $system
    processes = @($processes)
    registryViews = @($registryViews)
    candidateInstallations = @($candidateInstallations)
    appDataCandidates = @($appDataCandidates)
    fileInventory = @($fileInventory)
    xpcsRegistry = @($xpcsRegistry)
    runtimes = @($runtimes)
    errors = @($script:CollectionErrors)
}
Write-OutputArtifact -OutputRoot $outputRoot -Name 'discovery.json' -Contents ($snapshot | ConvertTo-Json -Depth 20)
$summary = "AIM59 Windows discovery snapshot`r`nCheckpoint: $Checkpoint`r`nCollection errors: $($script:CollectionErrors.Count)`r`nRaw evidence location: $outputRoot`r`n"
Write-OutputArtifact -OutputRoot $outputRoot -Name 'collection-summary.txt' -Contents $summary

if ($script:CollectionErrors.Count -gt 0) {
    Write-Warning "Snapshot is partial; see $outputRoot\\discovery.json before comparing checkpoints."
    exit 2
}
Write-Host "Snapshot written to $outputRoot"
exit 0
