# Generate screenshots of the main pages (simplified: use curl headers only)
Write-Host "=== Frontend Page Access Report ===" -ForegroundColor Cyan

$pages = @(
    @{ name = "Home"; url = "http://localhost:5173/" },
    @{ name = "Books list (API root"; url = "http://localhost:8000/api/books?page=1&per_page=5" },
    @{ name = "Recommend page"; url = "http://localhost:5173/#/recommend" },
    @{ name = "Profile"; url = "http://localhost:5173/#/profile" },
    @{ name = "Search"; url = "http://localhost:5173/#/search" }
)

foreach ($p in $pages) {
    try {
        $r = Invoke-WebRequest -Uri $p.url -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -eq 200) {
            Write-Host "[$($p.name)]: HTTP 200 ($($r.Content.Length) bytes)" -ForegroundColor Green
        } else {
            Write-Host "[$($p.name)]: HTTP $($r.StatusCode" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[$($p.name)]: FAIL ($_)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Page access report complete ===" -ForegroundColor Cyan
