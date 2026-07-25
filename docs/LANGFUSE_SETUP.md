# Langfuse v4 Self-Hosted Setup Guide

## Overview

Langfuse v4 has been added to the Docker Compose stack as a complete observability platform for the Social Support Application. It runs as 6 containers on the `xd_backend` network.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Langfuse v4 Stack                         │
├─────────────────────────────────────────────────────────────┤
│  langfuse-web (port 4000)                                   │
│    └─ Web UI and API                                        │
│                                                              │
│  langfuse-worker (port 3030)                                │
│    └─ Background worker for async processing                │
│                                                              │
│  langfuse-postgres (port 5433)                              │
│    └─ Dedicated PostgreSQL 17 for metadata                  │
│    └─ Separate from app DB (port 5432)                      │
│                                                              │
│  langfuse-clickhouse (ports 8123, 9000)                     │
│    └─ ClickHouse 25.12 for observation data                 │
│    └─ Pinned to avoid 26.x breaking changes                 │
│                                                              │
│  langfuse-redis (port 6379)                                 │
│    └─ Redis 7 for cache and queue                           │
│                                                              │
│  langfuse-minio (ports 9090, 9091)                          │
│    └─ MinIO for S3-compatible event/media storage           │
│    └─ Console at http://localhost:9091                      │
└─────────────────────────────────────────────────────────────┘
```

## Initial Setup

### 1. Generate Required Secrets

Copy `.env.example` to `.env` and generate secure values for:

```bash
# Generate NEXTAUTH_SECRET
openssl rand -base64 32

# Generate SALT
openssl rand -base64 16

# Generate ENCRYPTION_KEY
openssl rand -hex 32

# Generate database passwords (use strong random values)
openssl rand -base64 24
```

### 2. Required Environment Variables

All Langfuse variables are prefixed with `LANGFUSE_` to avoid conflicts:

**Authentication & Security:**
- `LANGFUSE_NEXTAUTH_SECRET` - Session encryption key
- `LANGFUSE_SALT` - Password hashing salt
- `LANGFUSE_ENCRYPTION_KEY` - Data encryption key (64 hex chars)

**PostgreSQL (Dedicated Instance):**
- `LANGFUSE_POSTGRES_PASSWORD` - Password for langfuse user
- `LANGFUSE_DATABASE_URL` - Connection string: `postgresql://langfuse:<password>@langfuse-postgres:5432/langfuse`

**ClickHouse:**
- `LANGFUSE_CLICKHOUSE_PASSWORD` - ClickHouse user password

**Redis:**
- `LANGFUSE_REDIS_AUTH` - Redis authentication password

**MinIO/S3:**
- `LANGFUSE_S3_SECRET_ACCESS_KEY` - MinIO secret key (min 8 chars)

### 3. Start the Stack

```bash
# Start all services
docker compose up -d

# Check status (wait 1-2 minutes for all services to become healthy)
docker compose ps

# View logs
docker compose logs -f langfuse-web
```

### 4. Access Langfuse

1. Open http://localhost:4000
2. Create your first admin account (first user becomes admin)
3. Create a project
4. Generate API keys from project settings
5. Update `.env` with the generated keys:
   ```
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```

## Port Summary

| Service | Host Port | Container Port | Purpose |
|---------|-----------|----------------|---------|
| langfuse-web | 4000 | 3000 | Web UI |
| langfuse-worker | 3030 | 3030 | Worker API |
| langfuse-postgres | 5433 | 5432 | PostgreSQL |
| langfuse-clickhouse | 8123 | 8123 | HTTP API |
| langfuse-clickhouse | 9000 | 9000 | Native protocol |
| langfuse-redis | 6379 | 6379 | Redis |
| langfuse-minio | 9090 | 9000 | S3 API |
| langfuse-minio | 9091 | 9001 | Console |

**Note:** All ports bind to `127.0.0.1` (localhost only) for security.

## Resource Allocation

Total resources reserved for Langfuse stack:
- **Memory:** ~5.3 GB (reservations) / ~8.3 GB (limits)
- **CPU:** ~3.1 cores (reservations) / ~6.3 cores (limits)

Adjust in `docker-compose.yml` if needed for your environment.

## Integration with Application

The application connects to Langfuse via the Python SDK:

```python
from langfuse import Langfuse

langfuse = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "http://localhost:4000")
)
```

## Troubleshooting

### Services not starting
- Check all required environment variables are set in `.env`
- Run `docker compose logs <service-name>` to see errors
- Wait 1-2 minutes for all services to pass health checks

### Port conflicts
- Langfuse uses dedicated ports (4000, 5433, 8123, 9000, 6379, 9090, 9091)
- If conflicts occur, update port mappings in `docker-compose.yml`

### ClickHouse issues
- ClickHouse is pinned to version 25.12 to avoid breaking changes in 26.x
- If you see ClickHouse errors, check logs: `docker compose logs langfuse-clickhouse`

### Database connection issues
- Langfuse uses a dedicated PostgreSQL instance on port 5433
- App database remains on port 5432
- Verify `LANGFUSE_DATABASE_URL` in `.env` matches the connection string

## Maintenance

### Backups
```bash
# Backup Langfuse PostgreSQL
docker exec xd_langfuse_postgres pg_dump -U langfuse langfuse > langfuse_backup.sql

# Backup MinIO data
docker run --rm -v xd_langfuse_minio_data:/data -v $(pwd):/backup alpine tar czf /backup/minio_backup.tar.gz /data
```

### Updates
```bash
# Update Langfuse images
docker compose pull langfuse-web langfuse-worker
docker compose up -d langfuse-web langfuse-worker
```

### Cleanup
```bash
# Stop Langfuse stack only
docker compose stop langfuse-web langfuse-worker langfuse-postgres langfuse-clickhouse langfuse-redis langfuse-minio

# Remove volumes (DESTRUCTIVE - deletes all Langfuse data)
docker compose down -v langfuse-postgres langfuse-clickhouse langfuse-redis langfuse-minio
```

## References

- [Langfuse v4 Documentation](https://langfuse.com/docs)
- [Langfuse Self-Hosting Guide](https://langfuse.com/self-hosting)
- [Langfuse v4 Release Notes](https://langfuse.com/changelog)
- Tech Stack Design: `docs/superpowers/specs/2026-07-25-tech-stack-design.md`
