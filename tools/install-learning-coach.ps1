[CmdletBinding()]
param(
    [string]$SourceDir = "",
    [string]$CodexHome = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)
    return [System.IO.Path]::GetFullPath($PathValue)
}

function Remove-PycacheDirs {
    param([Parameter(Mandatory = $true)][string]$RootPath)
    if (-not (Test-Path -LiteralPath $RootPath)) {
        return
    }

    Get-ChildItem -LiteralPath $RootPath -Recurse -Directory -Force |
        Where-Object { $_.Name -eq "__pycache__" } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force
        }
}

function Mirror-Directory {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )

    New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
    robocopy $SourcePath $TargetPath /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD __pycache__ | Out-Null
    $code = $LASTEXITCODE
    if ($code -gt 7) {
        throw "镜像复制失败，robocopy 退出码：$code"
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-FullPath (Join-Path $scriptDir "..")

if (-not $SourceDir) {
    $SourceDir = Join-Path $repoRoot ".agents\skills\learning-coach"
}
if (-not $CodexHome) {
    $CodexHome = Join-Path $HOME ".codex"
}

$sourceDirFull = Resolve-FullPath $SourceDir
$codexHomeFull = Resolve-FullPath $CodexHome
$skillsRoot = Join-Path $codexHomeFull "skills"
$targetDir = Join-Path $skillsRoot "learning-coach"

if (-not (Test-Path -LiteralPath $sourceDirFull)) {
    throw "找不到 skill 源目录：$sourceDirFull"
}

New-Item -ItemType Directory -Path $skillsRoot -Force | Out-Null

$backupDir = ""
$movedAway = $false
if (Test-Path -LiteralPath $targetDir) {
    if (-not $Force) {
        Write-Host "目标目录已存在：$targetDir"
        Write-Host "如需覆盖，请重新执行并加上 -Force。"
        exit 1
    }

    try {
        $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $backupDir = "$targetDir.backup.$timestamp"
        Move-Item -LiteralPath $targetDir -Destination $backupDir
        $movedAway = $true
        Write-Host "已备份旧版本到：$backupDir"
    }
    catch {
        $backupDir = ""
        Write-Host "旧版本目录正在被占用，改为原地同步覆盖。"
    }
}

if ($movedAway -or -not (Test-Path -LiteralPath $targetDir)) {
    Copy-Item -LiteralPath $sourceDirFull -Destination $targetDir -Recurse -Force
}
else {
    Mirror-Directory -SourcePath $sourceDirFull -TargetPath $targetDir
}

Remove-PycacheDirs -RootPath $targetDir

Write-Host ""
Write-Host "安装完成。"
Write-Host "skill 目录：$targetDir"
if ($backupDir) {
    Write-Host "旧版本备份：$backupDir"
}
Write-Host ""
Write-Host "推荐下一步："
Write-Host "1. 在 Codex 里直接说：使用 `$learning-coach 帮我开始一个新的学习项目"
Write-Host "2. 或手动运行：python `"$targetDir\\scripts\\learn.py`""
