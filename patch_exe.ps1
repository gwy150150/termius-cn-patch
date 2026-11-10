# Termius Chinese patch - update the embedded ASAR integrity hash inside Termius.exe.
# Only 64 ASCII bytes at a fixed offset are changed; all other bytes stay untouched.
param(
    [Parameter(Mandatory = $true)][ValidateSet('install', 'restore')][string]$Mode,
    [Parameter(Mandatory = $true)][string]$PatchJson,
    [Parameter(Mandatory = $true)][string]$ExePath
)

$ErrorActionPreference = 'Stop'
$meta = Get-Content -Raw -Encoding UTF8 $PatchJson | ConvertFrom-Json
$offset = [int64]$meta.exe_offset
$oldBytes = [System.Text.Encoding]::ASCII.GetBytes([string]$meta.old_hash)
$newBytes = [System.Text.Encoding]::ASCII.GetBytes([string]$meta.new_hash)

if ($oldBytes.Length -ne 64 -or $newBytes.Length -ne 64) {
    throw 'Invalid hash length in patch.json'
}
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Executable not found: $ExePath"
}

$fs = [System.IO.File]::Open($ExePath, [System.IO.FileMode]::Open,
                            [System.IO.FileAccess]::ReadWrite,
                            [System.IO.FileShare]::ReadWrite)
try {
    $buf = New-Object byte[] 64
    $fs.Position = $offset
    if ($fs.Read($buf, 0, 64) -ne 64) { throw 'Failed to read 64 bytes at offset' }
    $current = [System.Text.Encoding]::ASCII.GetString($buf)

    if ($Mode -eq 'install') {
        if ($current -eq $meta.new_hash) {
            Write-Host 'exe already patched, nothing to do.'
        } elseif ($current -eq $meta.old_hash) {
            $fs.Position = $offset
            $fs.Write($newBytes, 0, 64)
            $fs.Flush($true)
            Write-Host 'exe integrity hash updated.'
        } else {
            throw "Unexpected bytes at offset $offset - Termius version mismatch. Aborted."
        }
    } else {
        if ($current -eq $meta.old_hash) {
            Write-Host 'exe already original, nothing to do.'
        } elseif ($current -eq $meta.new_hash) {
            $fs.Position = $offset
            $fs.Write($oldBytes, 0, 64)
            $fs.Flush($true)
            Write-Host 'exe integrity hash restored.'
        } else {
            throw "Unexpected bytes at offset $offset - Termius version mismatch. Aborted."
        }
    }
} finally {
    $fs.Close()
}
