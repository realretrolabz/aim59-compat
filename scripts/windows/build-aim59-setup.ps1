<#
.SYNOPSIS
Builds the realretrolabz AIM Manager Windows Forms launcher into ignored build output.

.DESCRIPTION
Uses the C# compiler included with the installed .NET Framework. The compiled
EXE contains the experimental Windows installer and compatibility workflow.
#>
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$sourcePaths = @(
    (Join-Path $repositoryRoot 'windows\AIM59Setup\Program.cs'),
    (Join-Path $repositoryRoot 'windows\AIM59Setup\NativeWorkflow.cs')
)
$iconPath = Join-Path $repositoryRoot 'windows\AIM59Setup\assets\aim59-setup.ico'
$outputDirectory = Join-Path $repositoryRoot '.build\windows-exe'
$outputPath = Join-Path $outputDirectory 'rrlzAIM.exe'

foreach ($sourcePath in $sourcePaths) {
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "C# source file was not found: $sourcePath"
    }
}

if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
    throw "Windows icon was not found: $iconPath"
}

$compilerCandidates = @(
    (Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'),
    (Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe')
)
$compilerPath = $compilerCandidates | Where-Object {
    Test-Path -LiteralPath $_ -PathType Leaf
} | Select-Object -First 1

if ([string]::IsNullOrWhiteSpace($compilerPath)) {
    throw 'The .NET Framework C# compiler was not found. Run this command on Windows with .NET Framework 4.8 or later installed.'
}

$frameworkDirectory = Split-Path -Parent $compilerPath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

& $compilerPath `
    '/nologo' `
    '/target:winexe' `
    '/platform:anycpu' `
    '/optimize+' `
    '/debug-' `
    ("/out:$outputPath") `
    ("/win32icon:$iconPath") `
    ("/reference:$frameworkDirectory\System.dll") `
    ("/reference:$frameworkDirectory\System.Core.dll") `
    ("/reference:$frameworkDirectory\System.Drawing.dll") `
    ("/reference:$frameworkDirectory\System.Windows.Forms.dll") `
    $sourcePaths

if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
    throw 'rrlzAIM.exe was not built.'
}

Write-Host "Built: $outputPath"
