---
name: process-management
description: Targeted process management for starting, stopping, and restarting application processes and Docker infrastructure. Covers safe kill patterns (by port, PID, process group), protected service discovery, Docker compose management, FastAPI/Streamlit/Ollama restart sequences, pre-kill verification, and error recovery. Use when restarting the backend or frontend, managing Docker services, killing processes, debugging process issues, or starting/stopping application components.
---

# Process Management

## Core Safety Constraint

**NEVER use blanket process termination** (`taskkill /IM python.exe /F`, `killall python`, `Get-Process python | Stop-Process`). Always use targeted termination affecting only the specific process you started.

## Protected Services Registry

These services MUST NOT be killed or restarted by agents.

### Infrastructure Services (Docker Containers)

All infrastructure runs as Docker containers with the `xd_` prefix. Use `docker compose` commands to manage them, NEVER direct process kills.

| Service | Container Name | Ports | Purpose |
|---------|---------------|-------|---------|
| PostgreSQL | xd_postgres | 5432 | Primary application database |
| Neo4j | xd_neo4j | 7474, 7687 | Graph database (family relationships, document lineage) |
| Qdrant | xd_qdrant | 6333, 6334 | Vector database (document embeddings) |
| Langfuse Web | xd_langfuse_web | 4000 | LLM observability UI |
| Langfuse Worker | xd_langfuse_worker | 3030 | LLM observability background worker |
| Langfuse PostgreSQL | xd_langfuse_postgres | 5433 | Langfuse metadata database |
| ClickHouse | xd_langfuse_clickhouse | 8123, 9000 | Analytics database for Langfuse |
| Redis | xd_langfuse_redis | 6379 | Cache and queue for Langfuse |
| MinIO | xd_langfuse_minio | 9090, 9091 | S3-compatible storage for Langfuse |

### External Services (Host Processes)

| Service | Port | Purpose | Notes |
|---------|------|---------|-------|
| Ollama | 11434 | Local LLM and embeddings | Runs natively on host, managed by Ollama service |
| Proxy Server | Various | Network proxy | CANNOT be stopped - runs as system service |
| **DashScope Proxy** | **8899** | **Alibaba Cloud LLM API proxy** | **Discovered dynamically by port (8899) and script name (`dashscope_proxy.py`). CANNOT be stopped** |

### Application Processes (Agents CAN Manage)

These are the ONLY processes agents should start/stop/restart:

| Process | Typical Port | How to Manage |
|---------|-------------|---------------|
| FastAPI Backend | 8000 | Kill by port or PID |
| Streamlit Frontend | 8501 | Kill by port or PID |
| Test scripts | Ephemeral | Kill by PID or process group |

## Required Kill Patterns

### Kill by Port (preferred for dev servers)

```powershell
# Find and kill only the process using your app's port
$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
if ($pid) { Stop-Process -Id $pid -Force }
```

```bash
# Linux/macOS equivalent
lsof -ti:8000 | xargs kill -9
```

### Kill by PID

```powershell
# Track the PID when you start the process
$proc = Start-Process -FilePath "python" -ArgumentList "app.py" -PassThru
# Later, kill only that specific process
Stop-Process -Id $proc.Id -Force
```

### Kill by Process Group

```powershell
# Start in a new process group, then kill the group
$proc = Start-Process -FilePath "python" -ArgumentList "app.py" -PassThru
# Kill the entire group (includes child processes)
taskkill /PID $proc.Id /T /F
```

### PID File Pattern

```powershell
# On start: write PID to file
$proc = Start-Process -FilePath "python" -ArgumentList "app.py" -PassThru
$proc.Id | Out-File -FilePath ".app.pid"

# On stop: read PID and kill only that process
if (Test-Path ".app.pid") {
    $pid = Get-Content ".app.pid"
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Remove-Item ".app.pid"
}
```

## Protected Service Discovery

For protected services like the DashScope proxy, agents MUST dynamically discover the PID rather than relying on a hardcoded value. Three-layer identification:

1. **Port-based**: The service listens on a known port (8899 for DashScope)
2. **Command-line based**: The process runs a specific script (`dashscope_proxy.py`)
3. **PID file**: The service writes its own PID to a known file on startup

### Dynamic Discovery Script

```powershell
# MANDATORY: Discover protected service PIDs dynamically before any kill
function Get-ProtectedPIDs {
    $protectedPIDs = @()

    # Layer 1: Port-based discovery (DashScope proxy on port 8899)
    $portPID = (Get-NetTCPConnection -LocalPort 8899 -ErrorAction SilentlyContinue).OwningProcess
    if ($portPID) { $protectedPIDs += $portPID }

    # Layer 2: Command-line based discovery
    $processes = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'"
    foreach ($proc in $processes) {
        if ($proc.CommandLine -match 'dashscope_proxy\.py') {
            $protectedPIDs += $proc.ProcessId
        }
    }

    # Layer 3: PID file (if exists)
    $pidFile = ".protected_pids"
    if (Test-Path $pidFile) {
        $filePID = Get-Content $pidFile | Where-Object { $_ -match '^\d+$' } | Select-Object -First 1
        if ($filePID) { $protectedPIDs += [int]$filePID }
    }

    return ($protectedPIDs | Sort-Object -Unique)
}

# MANDATORY pre-kill check
$protectedPIDs = Get-ProtectedPIDs
if ($protectedPIDs -contains $TargetPID) {
    Write-Error "ABORT: PID $TargetPID is a protected service. Do not kill."
    exit 1
}
```

### PID File Convention (for services that self-register)

Protected services should write their PID to `.protected_pids` on startup:

```powershell
# Service startup script writes its own PID
$PID | Out-File -FilePath ".protected_pids" -Encoding utf8
```

If the `.protected_pids` file doesn't exist or the PID is stale, the port and command-line discovery layers will still catch the service.

## Docker Service Management

### Check Service Status

```powershell
# List all project containers
docker compose ps

# Check specific service
docker compose ps postgres
docker compose ps neo4j
```

### Restart Infrastructure Services

```powershell
# Restart a single service (safe)
docker compose restart postgres
docker compose restart neo4j

# Stop and start (preserves data)
docker compose stop qdrant
docker compose start qdrant

# Full restart of all infrastructure
docker compose down
docker compose up -d
```

### View Logs

```powershell
# Follow logs for a service
docker compose logs -f postgres
docker compose logs -f langfuse-web

# Last 100 lines
docker compose logs --tail=100 neo4j
```

### NEVER Do This with Docker

```powershell
# WRONG - kills container AND removes volumes (data loss!)
docker compose down -v

# WRONG - kills ALL docker containers on the system
docker kill $(docker ps -q)
docker stop $(docker ps -q)

# WRONG - removes all docker resources
docker system prune -a --volumes
```

## Application Process Management

### FastAPI Backend (Port 8000)

```powershell
# Find and kill only the FastAPI process
$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
if ($pid) { Stop-Process -Id $pid -Force }

# Then restart with stderr logging (critical for debugging)
Start-Process -FilePath ".\.venv\Scripts\python.exe" `
  -ArgumentList "-m", "uvicorn", "src.main:app", "--reload", "--port", "8000" `
  -RedirectStandardError "backend_stderr.log" `
  -RedirectStandardOutput "backend_stdout.log" `
  -WindowStyle Hidden

# Verify it's running
Test-NetConnection -ComputerName localhost -Port 8000
```

**Important:** Always redirect stderr when starting the backend. Silent crashes are impossible to debug without logs. Check `backend_stderr.log` for stack traces, validation errors, and LLM API failures.

### Streamlit Frontend (Port 8501)

```powershell
# Find and kill only the Streamlit process
$pid = (Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue).OwningProcess
if ($pid) { Stop-Process -Id $pid -Force }

# Then restart
.\.venv\Scripts\streamlit.exe run ui/streamlit_app.py --server.port 8501
```

### Ollama (Port 11434)

Ollama runs as a native service. To restart:

```powershell
# Restart Ollama service (Windows)
Restart-Service Ollama

# Or via Ollama CLI
ollama stop <model>
ollama serve  # if not running as service
```

## Mandatory Pre-Kill Verification

Before killing ANY Python process, agents MUST run this verification check. This is non-negotiable.

### Safe Kill Pattern (with verification)

```powershell
# Step 1: Identify target PID
$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess

# Step 2: VERIFY it's not protected using dynamic discovery
$protectedPIDs = Get-ProtectedPIDs
if ($protectedPIDs -contains $pid) {
    Write-Error "ABORT: PID $pid is a protected service. Do not kill."
    exit 1
}

# Step 3: Kill only after verification
if ($pid) { Stop-Process -Id $pid -Force }
```

### Rule: If PID matches any protected service, ABORT immediately

Protected services are discovered dynamically via:
1. Port binding (e.g., port 8899 for DashScope)
2. Command-line pattern (e.g., `dashscope_proxy.py`)
3. PID file (`.protected_pids`)

If any verification check reveals a protected PID, the agent must:
1. Stop immediately
2. Report to the user
3. NOT proceed with the kill

## Safe Restart Sequence

When you need to restart the application during debugging:

1. **Identify what you're restarting**: Is it the FastAPI backend (port 8000) or Streamlit frontend (port 8501)?
2. **Kill only that process**: Use port-based killing (see patterns above)
3. **Restart the app**: Use the appropriate command
4. **Verify it's running**: Check the port is listening
5. **NEVER touch infrastructure**: Docker services are managed separately

```powershell
# 1. Kill only the app process you're debugging
$pid = (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess
if ($pid) { Stop-Process -Id $pid -Force }

# 2. Restart the app
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload --port 8000

# 3. Verify it's running
Test-NetConnection -ComputerName localhost -Port 8000
```

## Prohibited Actions

### NEVER Kill by Process Name

```powershell
# WRONG - kills ALL python processes including proxy, other apps
taskkill /IM python.exe /F
taskkill /IM python3.exe /F
Get-Process python | Stop-Process -Force
```

### NEVER Kill Docker Containers Directly

```powershell
# WRONG - bypasses docker compose, may corrupt data
docker kill xd_postgres
docker rm -f xd_neo4j
```

### NEVER Kill System Services

```powershell
# WRONG - kills proxy, system services, other apps
Get-Process | Where-Object {$_.ProcessName -like "*python*"} | Stop-Process
taskkill /IM ollama.exe /F
```

## Error Recovery

If you accidentally kill an infrastructure process:

1. **Stop immediately** - don't compound the error
2. **Report what happened** - tell the user which service was affected
3. **Check if Docker auto-restarted it**: `docker compose ps`
4. **If not, restart the service**: `docker compose restart <service-name>`
5. **Verify it's healthy**: Check logs and health endpoint
6. **Update this skill** if new patterns emerge

### DashScope Proxy Recovery

If the DashScope proxy is accidentally killed:
1. Report immediately - the proxy must be restarted manually by the user
2. The proxy should write its new PID to `.protected_pids` on startup
3. Do NOT attempt to restart the proxy yourself - it requires manual intervention

#### Proxy Self-Registration (for the user to add to dashscope_proxy.py)

To make the proxy write its PID on startup, add this to the beginning of `dashscope_proxy.py`:

```python
import os
import sys

# Write PID to protected_pids file
pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".protected_pids")
with open(pid_file, "w") as f:
    f.write(str(os.getpid()))
```

Or, if starting the proxy manually, redirect the PID:

```powershell
# Start proxy and write PID
$proc = Start-Process -FilePath "python" -ArgumentList "dashscope_proxy.py" -PassThru
$proc.Id | Out-File -FilePath ".protected_pids" -Encoding utf8
```

### Quick Recovery Commands

```powershell
# Check which services are down
docker compose ps

# Restart a specific service
docker compose restart postgres

# Check service logs for errors
docker compose logs --tail=50 postgres

# Verify service health
docker compose ps  # should show "healthy" or "running"
```
