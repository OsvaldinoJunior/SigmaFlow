# SigmaFlow Production Deployment Guide
======================================

This guide covers deploying SigmaFlow to production environments.

## Prerequisites

- Docker 24+ and Docker Compose 2+
- PostgreSQL 16+ (managed or self-hosted)
- Redis 7+ (managed or self-hosted)
- SSL certificates (Let's Encrypt or commercial)
- Domain name configured with DNS

## Quick Start (Production)

### 1. Prepare Environment

```bash
# Clone repository
git clone https://github.com/OsvaldinoJunior/SigmaFlow.git
cd SigmaFlow

# Copy production environment template
cp .env.production.template .env.production

# Edit with your actual values (NEVER commit this file!)
# Required changes:
# - SECRET_KEY (generate with: openssl rand -base64 32)
# - DATABASE passwords
# - SMTP credentials
# - Webhook URLs
# - SSL certificate paths
nano .env.production
```

### 2. Generate SSL Certificates (Let's Encrypt example)

```bash
# Using certbot
sudo certbot certonly --standalone -d sigmaflow.example.com -d api.sigmaflow.example.com

# Copy certificates to nginx/certs/
mkdir -p certs
sudo cp /etc/letsencrypt/live/sigmaflow.example.com/fullchain.pem certs/sigmaflow.example.com.crt
sudo cp /etc/letsencrypt/live/sigmaflow.example.com/privkey.pem certs/sigmaflow.example.com.key
sudo cp /etc/letsencrypt/live/api.sigmaflow.example.com/fullchain.pem certs/api.sigmaflow.example.com.crt
sudo cp /etc/letsencrypt/live/api.sigmaflow.example.com/privkey.pem certs/api.sigmaflow.example.com.key

# Fix permissions
sudo chown -R $USER:$USER certs/
chmod 600 certs/*.key
chmod 644 certs/*.crt
```

### 3. Deploy

```bash
# Build and start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --build

# Check status
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production ps

# View logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production logs -f
```

### 4. Run Database Migrations

```bash
# Run alembic migrations
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production exec api alembic upgrade head
```

### 5. Verify Deployment

```bash
# Run health check
./scripts/health-check.sh

# Or manually
curl https://api.sigmaflow.example.com/health
curl https://sigmaflow.example.com
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
                        EXTERNAL TRAFFIC                           
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
                       NGINX REVERSE PROXY                         
              (SSL Termination, Rate Limiting, Routing)           
└─────────────────────────────────────────────────────────────────┘
              │                                        │
              ▼                                        ▼
┌─────────────────────────┐    ┌─────────────────────────────────┐
│    FRONTEND (Next.js)   │    │        API (FastAPI)            │
│    Port 3000            │    │        Port 8000                │
│    React 19 Dashboard   │    │    4 Workers + Health Check     │
└─────────────────────────┘    └─────────────────────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│      POSTGRES 16        │ │        REDIS 7          │ │   CELERY WORKERS (x2)   │
│      Port 5432          │ │        Port 6379        │ │   + BEAT SCHEDULER      │
│   Primary Database      │ │   Broker + Cache        │ │   Async Task Processing │
└─────────────────────────┘ └─────────────────────────┘ └─────────────────────────┘
```

## Service Configuration

### API Service
- **Workers**: 4 (configurable via `API_WORKERS`)
- **Memory Limit**: 2GB
- **CPU Limit**: 2 cores
- **Health Check**: `/health` every 30s

### Celery Workers
- **Replicas**: 2 (configurable via `WORKER_REPLICAS`)
- **Concurrency**: 4 per worker
- **Memory Limit**: 2GB each
- **Max Tasks Per Child**: 100 (prevents memory leaks)

### Celery Beat
- **Replicas**: 1 (singleton for scheduling)
- **Scheduler**: PersistentScheduler (survives restarts)

### Frontend
- **Mode**: Next.js Standalone
- **Memory Limit**: 512MB
- **Serves**: Static assets + SSR pages

### PostgreSQL
- **Memory Limit**: 1GB
- **Shared Buffers**: 256MB (configure in postgresql.conf if needed)
- **Max Connections**: 100

### Redis
- **Memory Limit**: 512MB
- **Policy**: allkeys-lru
- **Persistence**: AOF enabled

## Scaling Guidelines

### Horizontal Scaling

| Component | Scaling Strategy | Max Replicas |
|-----------|------------------|--------------|
| API | Add more containers behind nginx | 10+ |
| Workers | Increase `WORKER_REPLICAS` | 20+ |
| Frontend | Add more containers | 5+ |
| Beat | **Do not scale** (singleton) | 1 |

### Vertical Scaling

| Component | When to Scale Up |
|-----------|------------------|
| PostgreSQL | High CPU, slow queries, connection pooling exhausted |
| Redis | High memory usage, eviction rate > 0 |
| API | Consistently high CPU/memory, slow response times |
| Workers | Task queue backlog growing, tasks timing out |

## Monitoring & Observability

### Health Checks

```bash
# API Health
curl https://api.sigmaflow.example.com/health

# Response:
{
  "status": "healthy",
  "database": "connected",
  "version": "0.2.0"
}

# Frontend Health
curl https://sigmaflow.example.com

# Database
docker compose exec postgres pg_isready -U sigmaflow -d sigmaflow

# Redis
docker compose exec redis redis-cli ping
```

### Metrics (Prometheus)

If `METRICS_ENABLED=true`, metrics available at:
- API: `http://localhost:9090/metrics`
- Includes: request latency, error rates, DB pool usage, Celery queue depth

### Logs

```bash
# All services
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api

# Last 100 lines
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 api
```

### Log Aggregation

Configure Docker logging driver for centralized logging:
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "5"
```

For production, consider:
- **ELK Stack**: Filebeat → Logstash → Elasticsearch → Kibana
- **Loki/Grafana**: Promtail → Loki → Grafana
- **Datadog/New Relic**: Native Docker integrations

## Backup & Disaster Recovery

### Database Backup

```bash
# Daily backup script (add to cron)
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker compose exec -T postgres pg_dump -U sigmaflow sigmaflow | gzip > /backups/sigmaflow_${DATE}.sql.gz

# Keep last 30 days
find /backups -name "sigmaflow_*.sql.gz" -mtime +30 -delete
```

### Restore Database

```bash
# Stop services
docker compose -f docker-compose.yml -f docker-compose.prod.yml stop api worker beat

# Restore
gunzip -c /backups/sigmaflow_20240115_020000.sql.gz | docker compose exec -T postgres psql -U sigmaflow -d sigmaflow

# Restart services
docker compose -f docker-compose.yml -f docker-compose.prod.yml start api worker beat
```

### Volume Backup

```bash
# Backup volumes
docker run --rm -v sigmaflow_postgres_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/postgres_data_$(date +%Y%m%d).tar.gz -C /data .
docker run --rm -v sigmaflow_redis_data:/data -v $(pwd)/backups:/backup alpine tar czf /backup/redis_data_$(date +%Y%m%d).tar.gz -C /data .
```

## Security Checklist

- [ ] Strong `SECRET_KEY` (32+ random chars)
- [ ] Database passwords changed from defaults
- [ ] SSL certificates valid and auto-renewing
- [ ] `API_CORS_ORIGINS` restricted to your domains only
- [ ] Firewall: only ports 80, 443 open externally
- [ ] Database/Redis not exposed to internet
- [ ] Regular security updates (base images)
- [ ] `DEBUG=false` in production
- [ ] Rate limiting configured in nginx
- [ ] Audit logs enabled
- [ ] Secrets managed via Docker secrets or external vault

## Maintenance

### Update Application

```bash
# Pull latest code
git pull origin main

# Rebuild and deploy (zero-downtime with multiple replicas)
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d --no-deps api worker frontend

# Run migrations
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production exec api alembic upgrade head
```

### Database Maintenance

```bash
# Vacuum analyze (weekly)
docker compose exec postgres psql -U sigmaflow -d sigmaflow -c "VACUUM ANALYZE;"

# Reindex (monthly, during low traffic)
docker compose exec postgres psql -U sigmaflow -d sigmaflow -c "REINDEX DATABASE sigmaflow;"
```

### Certificate Renewal

```bash
# Add to cron (runs twice daily)
0 */12 * * * certbot renew --quiet --deploy-hook "cp /etc/letsencrypt/live/*/fullchain.pem /path/to/certs/ && cp /etc/letsencrypt/live/*/privkey.pem /path/to/certs/ && docker compose -f /path/to/docker-compose.prod.yml restart nginx"
```

## Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| API returns 502 | API container not healthy | Check `docker compose logs api`, verify DB/Redis connectivity |
| High memory usage | Memory leak in workers | Restart workers, check `CELERY_WORKER_MAX_TASKS_PER_CHILD` |
| Slow queries | Missing indexes | Run `EXPLAIN ANALYZE` on slow queries, add indexes via migration |
| Celery tasks stuck | Redis connection issues | Check Redis health, increase `CELERY_TASK_TIME_LIMIT` |
| Frontend not loading | Build failed or wrong API URL | Check `NEXT_PUBLIC_API_URL`, rebuild frontend |

### Debug Commands

```bash
# Enter API container
docker compose exec api bash

# Run Django-like shell
docker compose exec api python -c "from sigmaflow.core.database import get_async_session; import asyncio; ..."

# Check Celery status
docker compose exec worker celery -A sigmaflow.worker_fixed.celery_app inspect active
docker compose exec worker celery -A sigmaflow.worker_fixed.celery_app inspect stats

# Check database connections
docker compose exec postgres psql -U sigmaflow -d sigmaflow -c "SELECT count(*) FROM pg_stat_activity;"

# Check Redis info
docker compose exec redis redis-cli INFO memory
docker compose exec redis redis-cli INFO clients
```

## Support

- **Documentation**: https://docs.sigmaflow.example.com
- **Issues**: https://github.com/OsvaldinoJunior/SigmaFlow/issues
- **Email**: support@sigmaflow.example.com

## License

MIT License - see LICENSE file for details.