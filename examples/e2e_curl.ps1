# End-to-end smoke test through the gateway (PowerShell).
# Prereqs (local dev): `just backends` in one terminal, `just gateway` in another.
# Prereqs (docker):    `just docker-up`
# Run: powershell -ExecutionPolicy Bypass -File examples\e2e_curl.ps1

$ErrorActionPreference = "Continue"
$Gateway     = if ($env:GATEWAY)     { $env:GATEWAY }     else { "http://localhost:8080" }
$AdminToken  = if ($env:ADMIN_TOKEN) { $env:ADMIN_TOKEN } else { "admin-dev-token" }

function Section($n, $title) { Write-Host "`n== $n. $title" -ForegroundColor Cyan }

Section 1 "Health"
Invoke-RestMethod "$Gateway/health" | ConvertTo-Json

Section 2 "Metrics (first 15 lines)"
(Invoke-WebRequest "$Gateway/metrics").Content -split "`n" | Select-Object -First 15

Section 3 "Issue a JWT with users:read scope"
$tokenBody = @{ sub = "user-1"; scopes = @("users:read"); ttl_seconds = 3600 } | ConvertTo-Json
$tokenResp = Invoke-RestMethod -Method Post -Uri "$Gateway/mock-auth/token" `
    -ContentType "application/json" -Body $tokenBody
$Token = $tokenResp.access_token
Write-Host "TOKEN=$($Token.Substring(0, 40))..."

Section 4 "Public echo (no auth required)"
Invoke-WebRequest "$Gateway/echo/hello" | Select-Object -ExpandProperty Content

Section 5 "Users API without token -> expect 401"
try { Invoke-WebRequest "$Gateway/api/users/42" -SkipHttpErrorCheck | ForEach-Object { "status=$($_.StatusCode)" } }
catch { "status=$($_.Exception.Response.StatusCode.value__)" }

Section 6 "Users API with valid token -> expect 200"
Invoke-WebRequest "$Gateway/api/users/42" -Headers @{ Authorization = "Bearer $Token" } `
    -SkipHttpErrorCheck | Select-Object StatusCode, Content

Section 7 "Token with wrong scope -> expect 403"
$badBody = @{ sub = "user-2"; scopes = @("other:scope") } | ConvertTo-Json
$badTok  = (Invoke-RestMethod -Method Post -Uri "$Gateway/mock-auth/token" `
    -ContentType "application/json" -Body $badBody).access_token
$r = Invoke-WebRequest "$Gateway/api/users/42" -Headers @{ Authorization = "Bearer $badTok" } -SkipHttpErrorCheck
"status=$($r.StatusCode)"

Section 8 "Rate limit — 25 rapid requests (capacity=20)"
1..25 | ForEach-Object {
    $r = Invoke-WebRequest "$Gateway/echo/burst" -SkipHttpErrorCheck
    Write-Host -NoNewline "$($r.StatusCode) "
}
Write-Host ""

Section 9 "Inspect rate-limit headers"
$r = Invoke-WebRequest "$Gateway/echo/x" -SkipHttpErrorCheck
$r.Headers.GetEnumerator() | Where-Object { $_.Key -like "X-RateLimit*" }

Section 10 "Slow backend timeout"
$r = Invoke-WebRequest "$Gateway/slow/anything?delay=45" -SkipHttpErrorCheck
"status=$($r.StatusCode)"

Section 11 "Flaky backend / circuit breaker probe"
1..15 | ForEach-Object {
    $r = Invoke-WebRequest "$Gateway/flaky/x" -SkipHttpErrorCheck
    Write-Host -NoNewline "$($r.StatusCode) "
}
Write-Host ""

Section 12 "Admin: list routes"
(Invoke-RestMethod "$Gateway/admin/routes" -Headers @{ "x-admin-token" = $AdminToken }).Count

Section 13 "Admin: add + delete a temporary route"
$route = @{
    id = "tmp"; path = "/tmp/*"; methods = @("GET")
    target = "http://localhost:9001"
    middlewares = @(); middleware_config = @{}
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri "$Gateway/admin/routes" `
    -Headers @{ "x-admin-token" = $AdminToken } -ContentType "application/json" -Body $route
Invoke-RestMethod -Method Delete -Uri "$Gateway/admin/routes/tmp" `
    -Headers @{ "x-admin-token" = $AdminToken }

Section 14 "Admin: reload"
Invoke-RestMethod -Method Post -Uri "$Gateway/admin/reload" -Headers @{ "x-admin-token" = $AdminToken }

Section 15 "Request-ID propagation"
$r = Invoke-WebRequest "$Gateway/echo/x" -Headers @{ "x-request-id" = "trace-abc-123" } -SkipHttpErrorCheck
$r.Headers.GetEnumerator() | Where-Object { $_.Key -eq "X-Request-ID" }