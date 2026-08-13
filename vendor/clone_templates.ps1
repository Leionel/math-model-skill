param(
    [string]$Destination = "vendor/upstream",
    [switch]$Refresh,
    [switch]$IncludeLargeReferences
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$targetRoot = Join-Path $root $Destination
New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null

$sources = @(
    # The three user-nominated Overleaf gallery pages are recorded in
    # template_sources.json. Gallery projects are copied into an authenticated
    # Overleaf account and do not expose an anonymous Git clone. These two
    # repositories are explicitly compatibility sources, not byte-identical
    # exports of those pages.
    @{
        Name = "CUMCMThesis"
        Url = "https://github.com/latexstudio/CUMCMThesis.git"
        Commit = "90d3e854534ae7dc605dfe9296785f8c17e56e22"
    },
    @{
        Name = "mcmthesis"
        Url = "https://github.com/latexstudio-org/mcmthesis.git"
        Commit = "8ac05e2c3a9ef5880a15e3a3a18762a546c10b69"
    },
    @{
        Name = "pandoc-latex-template"
        Url = "https://github.com/Wandmalfarbe/pandoc-latex-template.git"
        Commit = "93cc5b8e08c658da012d7609491ae72b1aff72fc"
    },
    @{
        Name = "SciencePlots"
        Url = "https://github.com/garrettj403/SciencePlots.git"
        Commit = "b9b16959570bd2fbc9ff5118bacc423c3bddd592"
    },
    @{
        Name = "scientific-visualization-book"
        Url = "https://github.com/rougier/scientific-visualization-book.git"
        Commit = "62fa569f30333c817c13e4dc757877c1192fd15a"
    },
    @{
        Name = "python-graph-gallery"
        Url = "https://github.com/holtzy/The-Python-Graph-Gallery.git"
        Commit = "566349bf2b3cf0531fa6fd5de0810c8e075f8638"
    }
)

$largeSparsePatterns = @{
    "scientific-visualization-book" = @(
        "README.md",
        "LICENSE.txt",
        "code/**/*.py",
        "rst/**/*.rst",
        "rst2latex.py"
    )
    "python-graph-gallery" = @(
        "README.md",
        "LICENSE*",
        "gallery/**/*.py",
        "content/**/*.py",
        "scripts/**/*.py",
        "datasets/**/*.csv",
        "datasets/**/*.json"
    )
}

foreach ($source in $sources) {
    if (-not $IncludeLargeReferences -and $source.Name -in @("scientific-visualization-book", "python-graph-gallery")) {
        Write-Host "$($source.Name): skipped (pass -IncludeLargeReferences to clone)"
        continue
    }
    $target = Join-Path $targetRoot $source.Name
    if (Test-Path -LiteralPath $target) {
        if (-not $Refresh) {
            $actual = (& git -C $target rev-parse HEAD).Trim()
            if ($LASTEXITCODE -ne 0 -or $actual -ne $source.Commit) {
                throw "$($source.Name) exists at an unexpected commit: $actual"
            }
            Write-Host "$($source.Name): already locked at $actual"
            continue
        }
        & git -C $target -c http.sslBackend=openssl fetch --depth 1 origin $source.Commit
        if ($LASTEXITCODE -ne 0) { throw "fetch failed for $($source.Name)" }
    }
    else {
        & git -c http.sslBackend=openssl clone --filter=blob:none --no-checkout $source.Url $target
        if ($LASTEXITCODE -ne 0) { throw "clone failed for $($source.Name)" }
        & git -C $target -c http.sslBackend=openssl fetch --depth 1 origin $source.Commit
        if ($LASTEXITCODE -ne 0) { throw "fetch failed for $($source.Name)" }
    }
    if ($largeSparsePatterns.ContainsKey($source.Name)) {
        & git -C $target sparse-checkout init --no-cone
        if ($LASTEXITCODE -ne 0) { throw "sparse-checkout init failed for $($source.Name)" }
        & git -C $target sparse-checkout set --no-cone $largeSparsePatterns[$source.Name]
        if ($LASTEXITCODE -ne 0) { throw "sparse-checkout set failed for $($source.Name)" }
    }
    # A partial clone may fetch promised blobs during checkout. Keep the same
    # OpenSSL backend here as in clone/fetch so Windows Schannel credentials do
    # not make a valid local reference look like a failed checkout.
    & git -C $target -c http.sslBackend=openssl checkout --detach $source.Commit
    if ($LASTEXITCODE -ne 0) { throw "checkout failed for $($source.Name)" }
    $actual = (& git -C $target rev-parse HEAD).Trim()
    if ($actual -ne $source.Commit) { throw "$($source.Name) lock verification failed" }
    Write-Host "$($source.Name): locked at $actual"
}
