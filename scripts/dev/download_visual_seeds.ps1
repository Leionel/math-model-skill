[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)

$ErrorActionPreference = 'Stop'
$root = Join-Path $RepositoryRoot 'assets\figure-gallery\_external-seeds'

$files = @(
    @{ Path = 'concept-board-contact-sheet.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/concept-board/contact-sheet.png' },
    @{ Path = 'research-framework\preview.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/concept-board/research-framework/research-framework.png' },
    @{ Path = 'research-framework\source.drawio'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/concept-board/research-framework/research-framework.drawio' },
    @{ Path = 'model-pipeline\preview.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/concept-board/model-pipeline/model-pipeline.png' },
    @{ Path = 'model-pipeline\comparison.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/concept-board/model-pipeline/comparison.png' },
    @{ Path = 'model-pipeline\source.drawio'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/concept-board/model-pipeline/model-pipeline.drawio' },
    @{ Path = 'contextforge\reference.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/contextforge/reference.png' },
    @{ Path = 'contextforge\preview.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/contextforge/contextforge.png' },
    @{ Path = 'contextforge\comparison.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/contextforge/comparison.png' },
    @{ Path = 'contextforge\source.drawio'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/contextforge/contextforge.drawio' },
    @{ Path = 'skillcircuit\reference.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/skillcircuit/reference.png' },
    @{ Path = 'skillcircuit\preview.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/skillcircuit/skillcircuit.png' },
    @{ Path = 'skillcircuit\comparison.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/skillcircuit/comparison.png' },
    @{ Path = 'skillcircuit\module-qa-contact-sheet.png'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/skillcircuit/module-qa-contact-sheet.png' },
    @{ Path = 'skillcircuit\source.drawio'; Url = 'https://raw.githubusercontent.com/ai-jiaqian/drawio-figure-replicator/main/examples/skillcircuit/skillcircuit.drawio' }
)

foreach ($entry in $files) {
    $target = Join-Path $root $entry.Path
    New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
    if ((Test-Path -LiteralPath $target) -and (Get-Item -LiteralPath $target).Length -gt 0) {
        continue
    }
    & curl.exe --fail --location --retry 2 --retry-delay 1 --output $target $entry.Url
    if ($LASTEXITCODE -ne 0) {
        throw "download failed: $($entry.Url)"
    }
    if (-not (Test-Path -LiteralPath $target) -or (Get-Item -LiteralPath $target).Length -eq 0) {
        throw "download produced an empty file: $target"
    }
}

Write-Output "Downloaded $($files.Count) visual seed assets to $root"
