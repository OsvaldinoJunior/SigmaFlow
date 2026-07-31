# SigmaFlow Load Tests
=====================

This directory contains load testing scripts for the SigmaFlow platform using both **k6** and **Locust**.

## Test Scenarios

### 1. Multi-Tenant Load (k6) - `sigmaflow-load-test.js`
Simulates realistic multi-tenant usage with:
- 5 tenants (ACME Corp, Globex Inc, Initech LLC, Umbrella Corp, Wayne Enterprises)
- 5 users per tenant (25 concurrent users base)
- Ramp-up from 0 to 50 users over ~6 minutes
- Sustained load at 50 users for 3 minutes
- Spike test to 100 users

Operations tested:
- User authentication (login)
- Project CRUD operations
- Dataset creation
- Pipeline execution triggers
- Insights retrieval
- Project listing

### 2. Detailed User Behavior (Locust) - `locustfile.py`
Two user classes:
- **SigmaFlowUser** (weight 10): Regular users performing DMAIC workflow
- **AdminUser** (weight 1): Admin users managing tenants

Operations weighted by realistic frequency:
- Read operations (list projects, plants, tenants): High weight (8-10)
- Write operations (create project, dataset): Medium weight (2-3)
- Pipeline execution: Low weight (1)
- Admin operations: Separate user class

## Running Tests

### k6 Tests
```bash
# Install k6
# macOS: brew install k6
# Linux: sudo apt-get install k6
# Docker: docker pull grafana/k6

# Run against local API
k6 run load-tests/sigmaflow-load-test.js \
  -e API_URL=http://localhost:8000/api/v1

# Run with more VUs
k6 run load-tests/sigmaflow-load-test.js \
  -e API_URL=http://staging.sigmaflow.example.com/api/v1 \
  --vus 50 --duration 10m

# Output to InfluxDB for Grafana visualization
k6 run load-tests/sigmaflow-load-test.js \
  -e API_URL=http://localhost:8000/api/v1 \
  --out influxdb=http://localhost:8086/k6
```

### Locust Tests
```bash
# Install locust
pip install locust

# Run web UI
locust -f load-tests/locustfile.py --host=http://localhost:8000/api/v1

# Run headless
locust -f load-tests/locustfile.py \
  --host=http://localhost:8000/api/v1 \
  --headless -u 50 -r 5 -t 5m \
  --html report.html --csv results

# Distributed mode (multiple workers)
# Master:
locust -f load-tests/locustfile.py --host=http://localhost:8000/api/v1 --master
# Workers:
locust -f load-tests/locustfile.py --host=http://localhost:8000/api/v1 --worker
```

## Prerequisites

Before running load tests, ensure:
1. **Database seeded** with test tenants, plants, and users
2. **API running** and accessible
3. **Test users exist** with known credentials (see test scripts for expected emails/passwords)

### Seed Test Data (example)
```python
# Run this script to create test users
# python seed_test_data.py

# Expected users per tenant:
# user1@tenant-acme.com ... user5@tenant-acme.com (password: TestPass123!)
# user1@tenant-globex.com ... user5@tenant-globex.com (password: TestPass123!)
# ... etc for all 5 tenants
# Admin: admin@sigmaflow.com (password: AdminPass123!)
```

## Key Metrics to Monitor

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| p95 Response Time | < 2s | > 5s |
| Error Rate | < 5% | > 10% |
| Login Success Rate | > 95% | < 90% |
| Project Creation Success | > 90% | < 80% |
| Pipeline Trigger Success | > 85% | < 75% |
| Insights Retrieval Success | > 90% | < 80% |

## CI/CD Integration

Add to GitHub Actions:
```yaml
- name: Run k6 Load Test
  uses: grafana/k6-action@v0.2.0
  with:
    filename: load-tests/sigmaflow-load-test.js
    env: API_URL=${{ secrets.STAGING_API_URL }}

- name: Run Locust Load Test
  run: |
    pip install locust
    locust -f load-tests/locustfile.py \
      --host=${{ secrets.STAGING_API_URL }} \
      --headless -u 30 -r 3 -t 3m \
      --csv=locust-results
```

## Test Data Requirements

The tests expect the following to exist in the database:

### Tenants
- `tenant-acme` (ACME Corp)
- `tenant-globex` (Globex Inc)
- `tenant-initech` (Initech LLC)
- `tenant-umbrella` (Umbrella Corp)
- `tenant-wayne` (Wayne Enterprises)

### Plants
- At least one plant per tenant with ID `plant-1`

### Users
- 5 users per tenant (user1-user5) with password `TestPass123!`
- 1 admin user (admin@sigmaflow.com) with password `AdminPass123!`

## Customizing Tests

### Adjust Load Profile (k6)
Modify the `stages` in the `ramp_up` scenario:
```javascript
stages: [
  { duration: '30s', target: 10 },
  { duration: '1m', target: 10 },
  { duration: '30s', target: 25 },
  { duration: '2m', target: 25 },
  { duration: '30s', target: 50 },
  { duration: '3m', target: 50 },
  { duration: '30s', target: 0 },
]
```

### Adjust User Behavior (Locust)
Modify task weights in `SigmaFlowUser` class:
```python
@task(10)  # Increase for more read-heavy
def get_projects(self):
    ...

@task(1)   # Decrease for less pipeline execution
def trigger_pipeline_run(self):
    ...
```

## Analyzing Results

### k6 Results
- JSON output: `k6 run --out json=results.json`
- InfluxDB + Grafana: Pre-built dashboards available
- HTML report: `k6 run --out html=report.html`

### Locust Results
- Web UI: Real-time charts at http://localhost:8089
- CSV export: `--csv=results` generates `results_stats.csv`, `results_failures.csv`
- HTML report: `--html=report.html`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 401 Unauthorized | Verify test users exist with correct passwords |
| 404 Not Found | Check API endpoint paths match current version |
| Connection refused | Ensure API is running and accessible |
| High error rate | Check database connections, reduce concurrent users |
| Slow responses | Profile API endpoints, check database indexes |