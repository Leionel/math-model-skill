[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
    [switch]$DocsOnly
)

$ErrorActionPreference = 'Stop'
$python = (Get-Command python -ErrorAction Stop).Source
$generator = Join-Path $RepositoryRoot 'scripts\figures\generate_drawio.py'
$drawio = 'D:\Program Files\draw.io\draw.io.exe'
if (-not (Test-Path -LiteralPath $drawio)) {
    throw "draw.io Desktop was not found: $drawio"
}

$variants = @(
    @{ Gallery = 'research-framework\01'; Archetype = 'research_framework' },
    @{ Gallery = 'research-framework\02'; Archetype = 'parallel_integration' },
    @{ Gallery = 'model-pipeline\01'; Archetype = 'computational_pipeline' },
    @{ Gallery = 'model-pipeline\02'; Archetype = 'method_architecture' },
    @{ Gallery = 'parallel-integration\01'; Archetype = 'parallel_integration' },
    @{ Gallery = 'parallel-integration\02'; Archetype = 'research_framework' },
    @{ Gallery = 'optimization-loop\01'; Archetype = 'iterative_optimization' },
    @{ Gallery = 'optimization-loop\02'; Archetype = 'computational_pipeline' },
    @{ Gallery = 'method-architecture\01'; Archetype = 'method_architecture' },
    @{ Gallery = 'method-architecture\02'; Archetype = 'parallel_integration' }
)

foreach ($variant in $variants) {
    $directory = Join-Path $RepositoryRoot (Join-Path 'assets\figure-gallery' $variant.Gallery)
    $spec = Join-Path $RepositoryRoot ("assets\drawio\archetypes\{0}\example_spec.json" -f $variant.Archetype)
    $source = Join-Path $directory 'figure.drawio'
    $svg = Join-Path $directory 'figure.svg'
    $preview = Join-Path $directory 'preview.png'
    New-Item -ItemType Directory -Force $directory | Out-Null
    if (-not $DocsOnly) {
        & $python $generator --project-root $RepositoryRoot --spec $spec --output $source --force --export-format svg --export-output $svg
        if ($LASTEXITCODE -ne 0) { throw "Draw.io SVG export failed: $($variant.Gallery)" }
        & $python $generator --project-root $RepositoryRoot --spec $spec --output $source --force --export-format png --export-output $preview
        if ($LASTEXITCODE -ne 0) { throw "Draw.io PNG export failed: $($variant.Gallery)" }
    }
    @(
        "# $($variant.Gallery)",
        '',
        '## Purpose',
        '',
        'Repository-owned composition variant for visual grammar study only.',
        '',
        '## Main message',
        '',
        'The current project must supply its own nodes, edges, labels, sources and result claims.',
        '',
        '## Visual references',
        '',
        'Primary: assets/figure-gallery/_external-seeds/.',
        '',
        'Borrow: hierarchy, grouping and reading order.',
        '',
        'Do not copy: labels, topology, icons or domain claims.',
        '',
        '## Output',
        '',
        '- figure.drawio',
        '- figure.svg',
        '- preview.png'
    ) | Set-Content -LiteralPath (Join-Path $directory 'brief.md') -Encoding utf8
    @(
        '# Notes',
        '',
        "Archetype source: assets/drawio/archetypes/$($variant.Archetype)/example_spec.json.",
        '',
        'This variant is one option, not a fixed layout. Choose it only after the actual',
        'figure brief has selected source evidence and a primary reader question.'
    ) | Set-Content -LiteralPath (Join-Path $directory 'notes.md') -Encoding utf8
}

Write-Output "Built $($variants.Count) local Draw.io gallery variants under assets\figure-gallery"
