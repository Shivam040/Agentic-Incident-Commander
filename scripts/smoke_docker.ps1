$ErrorActionPreference = "Stop"

Write-Host "[1/7] Validating Compose configuration..."
docker compose config | Out-Null
if ($LASTEXITCODE -ne 0) { throw "docker compose config failed" }

Write-Host "[2/7] Building image..."
docker compose build
if ($LASTEXITCODE -ne 0) { throw "docker compose build failed" }

Write-Host "[3/7] Starting container..."
docker compose up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

Write-Host "[4/7] Waiting for /health..."
$deadline = (Get-Date).AddMinutes(2)
$healthy = $false
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 5
        if ($health.status -eq "ok") {
            $healthy = $true
            break
        }
    }
    catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $healthy) {
    docker compose logs --tail=100
    throw "Container did not become healthy within 2 minutes"
}

Write-Host "[5/7] Verifying /metrics..."
$metrics = Invoke-WebRequest -Uri "http://localhost:8000/metrics" -TimeoutSec 10 -UseBasicParsing
if ($metrics.StatusCode -ne 200) { throw "/metrics did not return HTTP 200" }
if ($metrics.Content -notmatch "incident_commander_") {
    throw "Expected incident_commander Prometheus metrics were not found"
}

Write-Host "[6/7] Verifying container hardening..."
$containerId = (docker compose ps -q incident-commander).Trim()
if (-not $containerId) { throw "incident-commander container not found" }

$user = (docker inspect --format '{{.Config.User}}' $containerId).Trim()
$readOnly = (docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' $containerId).Trim()
$capDrop = (docker inspect --format '{{json .HostConfig.CapDrop}}' $containerId).Trim()
$securityOpt = (docker inspect --format '{{json .HostConfig.SecurityOpt}}' $containerId).Trim()

if (-not $user) { throw "Container is using the default/root user" }
if ($readOnly -ne "true") { throw "Root filesystem is not read-only" }
if ($capDrop -notmatch "ALL") { throw "Linux capabilities were not dropped" }
if ($securityOpt -notmatch "no-new-privileges") { throw "no-new-privileges is not enabled" }

Write-Host "[7/7] Verifying container -> host Ollama connectivity..."
docker compose exec -T incident-commander python -c "import json, os, urllib.request; base=os.environ['OLLAMA_BASE_URL'].rstrip('/'); data=json.load(urllib.request.urlopen(base + '/api/tags', timeout=10)); names=[m.get('name','') for m in data.get('models',[])]; print('Ollama models visible from container:', names); assert any(n.startswith('qwen3:4b') for n in names), 'qwen3:4b not visible'; assert any(n.startswith('nomic-embed-text') for n in names), 'nomic-embed-text not visible'"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Container health is good, but host Ollama was not reachable."
    Write-Host "Ensure Ollama is running and Docker can access it through host.docker.internal:11434."
    throw "Ollama connectivity check failed"
}

Write-Host ""
Write-Host "Stage 4C Docker hardening smoke test: PASS"
Write-Host "Verified: build, healthcheck, Prometheus endpoint, non-root user, read-only root filesystem, dropped capabilities, no-new-privileges, and host Ollama connectivity."
