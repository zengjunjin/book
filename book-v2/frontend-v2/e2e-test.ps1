# Simple E2E smoke test using httpx - simulates the main user flows
# This tests both the API end-to-end and verifies the frontend is accessible
$ErrorActionPreference = "Continue"

Write-Host "=== E2E Smoke Test Suite ===" -ForegroundColor Cyan
Write-Host "Time: $(Get-Date)"
Write-Host ""

$frontendUrl = "http://localhost:5173/"
$backendUrl = "http://localhost:8000"

# 1. Check frontend is serving
Write-Host "[1] Frontend serve check"
try {
    $r = Invoke-WebRequest -Uri $frontendUrl -UseBasicParsing -TimeoutSec 10
    if ($r.StatusCode -eq 200) {
        Write-Host "  [PASS] Frontend served HTML ($($r.Content.Length) bytes)" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Status: $($r.StatusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}

# 2. Check frontend assets (JS/CSS) - Vite manifest might not exist, just test root HTML contains js/css
Write-Host "[2] Frontend asset check (JS/CSS in index.html)"
try {
    $html = Invoke-RestMethod -Uri $frontendUrl -UseBasicParsing -TimeoutSec 10 -Method Get
    if ($html -match '<script' -and $html -match 'vite|js') {
        Write-Host "  [PASS] HTML contains script tags" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] Could not detect JS in HTML" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}

# 3. Backend health
Write-Host "[3] Backend health"
try {
    $r = Invoke-RestMethod -Uri "$backendUrl/api/health" -UseBasicParsing -TimeoutSec 5
    if ($r.status -eq 'ok') {
        Write-Host "  [PASS] /api/health returns ok (v$($r.version))" -ForegroundColor Green
    } else {
        Write-Host "  [FAIL]" -ForegroundColor Red
    }
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}

# 4. Register + login flow
Write-Host "[4] Auth flow (register + login + get current user)"
$username = "e2e_$(Get-Date -Format 'HHmmssfff')"
$email = "$username@example.com"
$pwd = "Secure123!"

try {
    $body = @{ email = $email; username = $username; password = $pwd } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$backendUrl/api/auth/register" -Method Post -Body $body -ContentType "application/json" -UseBasicParsing
    Write-Host "  [PASS] Registered user: $username" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] register: $_" -ForegroundColor Red
    continue
}

try {
    $form = @{ username = $username; password = $pwd }
    $r = Invoke-RestMethod -Uri "$backendUrl/api/auth/login" -Method Post -Body $form -UseBasicParsing -ContentType "application/x-www-form-urlencoded"
    $token = $r.access_token
    Write-Host "  [PASS] Got access_token ($($token.Length) chars)" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] login: $_" -ForegroundColor Red
    $token = $null
}

if ($token) {
    try {
        $headers = @{ Authorization = "Bearer $token" }
        $r = Invoke-RestMethod -Uri "$backendUrl/api/auth/me" -Headers $headers -UseBasicParsing
        Write-Host "  [PASS] /api/auth/me -> $($r.email)" -ForegroundColor Green
    } catch {
        Write-Host "  [FAIL] get me: $_" -ForegroundColor Red
    }
}

# 5. Books browsing
Write-Host "[5] Books browsing"
try {
    $r = Invoke-RestMethod -Uri "$backendUrl/api/books?page=1&per_page=10" -UseBasicParsing
    Write-Host "  [PASS] /api/books -> total $($r.total) books" -ForegroundColor Green
    if ($r.books -and $r.books.Count -gt 0) {
        $bookId = $r.books[0].id
        Write-Host "     First book id: $bookId"

        try {
            $bookDetail = Invoke-RestMethod -Uri "$backendUrl/api/books/$bookId" -Headers $headers -UseBasicParsing
            Write-Host "     [PASS] /api/books/$bookId returned book '$($bookDetail.title)'" -ForegroundColor Green
        } catch {
            Write-Host "     [WARN] detail: $_" -ForegroundColor Yellow
        }
    }
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}

# 6. Recommendations
Write-Host "[6] Recommendations"
foreach ($path in @("hybrid/1", "explore/1", "evaluation/system")) {
    try {
        $r = Invoke-RestMethod -Uri "$backendUrl/api/recommend/$path" -Headers $headers -UseBasicParsing -TimeoutSec 15
        Write-Host "  [PASS] /api/recommend/$path -> OK" -ForegroundColor Green
    } catch {
        Write-Host "  [WARN] /api/recommend/$path -> $_" -ForegroundColor Yellow
    }
}

# 7. Text search
Write-Host "[7] Text search"
try {
    $r = Invoke-RestMethod -Uri "$backendUrl/api/books?search=harry" -UseBasicParsing
    Write-Host "  [PASS] Text search 'harry' returned $($r.books.Count) results" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}

# 8. Semantic search (BERT) - may take time
Write-Host "[8] Semantic search (BERT)"
try {
    $bookId = 5005  # a known book id for semantic-similar endpoint
    $r = Invoke-RestMethod -Uri "$backendUrl/api/books/$bookId/semantic-similar?top_k=3" -UseBasicParsing -TimeoutSec 120
    if ($r.semantic_similar_books -and $r.semantic_similar_books.Count -gt 0) {
        Write-Host "  [PASS] /api/books/$bookId/semantic-similar returned $($r.semantic_similar_books.Count) results" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] /api/books/$bookId/semantic-similar returned empty" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARN] /api/books/$bookId/semantic-similar: $_" -ForegroundColor Yellow
}

# 9. Rating submission
Write-Host "[9] Rating submission"
try {
    $body = @{ book_id = $bookId; rating = 8; review = "Great read" } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$backendUrl/api/ratings" -Method Post -Body $body -Headers $headers -ContentType "application/json" -UseBasicParsing
    Write-Host "  [PASS] /api/ratings POST -> success" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] /api/ratings: $_" -ForegroundColor Yellow
}

# 10. OpenAPI docs
Write-Host "[10] OpenAPI schema"
try {
    $r = Invoke-RestMethod -Uri "$backendUrl/openapi.json" -UseBasicParsing
    Write-Host "  [PASS] /openapi.json -> $($r.paths.Count) endpoints" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== E2E Test Complete ===" -ForegroundColor Cyan
