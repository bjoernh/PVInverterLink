# Application Monitoring Architecture

## Overview

This document describes the comprehensive monitoring and observability stack for the Deye Hard solar inverter management system. The setup is designed for a single engineer managing 100 users with 120 inverters on self-hosted Docker infrastructure.

**Selected Stack: SignOz + Prometheus + PostgreSQL Exporter**

```
┌─────────────────────────────────────────────────────────────┐
│ Application Layer                                           │
├─────────────────────────────────────────────────────────────┤
│ • FastAPI Backend (Python)                                  │
│ • Rust Collector (TCP server receiving inverter data)       │
│ • PostgreSQL + TimescaleDB                                  │
└────────────────────┬────────────────────┬───────────────────┘
                     │                    │
      ┌──────────────▼──────┐  ┌──────────▼──────────┐
      │ OpenTelemetry SDK   │  │ Prometheus Exporter  │
      │ (Python + Rust)     │  │ (PostgreSQL)         │
      └──────────────┬──────┘  └──────────┬──────────┘
                     │                    │
      ┌──────────────▼────────────────────▼──────────┐
      │ SignOz (OTEL Collector)                      │
      │ • Traces (distributed tracing)               │
      │ • Metrics (OpenTelemetry + Prometheus)       │
      │ • Logs (structured & JSON)                   │
      │ • Alerting rules (email-based)               │
      └──────────────┬────────────────────────────────┘
                     │
      ┌──────────────▼────────────────────────────────┐
      │ Unified Dashboard (Grafana inside SignOz)     │
      │ • Request latency & errors                    │
      │ • Data collector performance                  │
      │ • DB health & storage                         │
      │ • Alert management & delivery                 │
      └────────────────────────────────────────────────┘
```

## Why SignOz?

| Criteria | SignOz | Prometheus+Loki+Tempo | ELK |
|----------|--------|----------------------|-----|
| Setup Complexity | ⭐⭐ Simple | ⭐⭐⭐⭐ Complex | ⭐⭐⭐⭐⭐ Very Complex |
| Unified UI | ✅ Yes (traces + metrics + logs) | ❌ Multiple components | ⚠️ Possible |
| Learning Curve | ⭐⭐ Gentle | ⭐⭐⭐ Moderate | ⭐⭐⭐⭐ Steep |
| Resource Usage | ~1.5GB RAM | ~1.5GB RAM | ~3GB+ RAM |
| For 1 Engineer | ✅ Perfect | ⚠️ Maintenance overhead | ❌ Too heavy |
| Open Source | ✅ Yes | ✅ Yes | ✅ Yes |
| Self-Hosted | ✅ Yes | ✅ Yes | ✅ Yes |

---

## Architecture Components

### 1. SignOz (OpenTelemetry Collector & Visualization)

**What it does:**
- Ingests OpenTelemetry data (traces, metrics, logs) from Python/Rust services
- Provides unified dashboard for observability
- Handles alerting and notifications
- Stores time-series data efficiently

**Container composition:**
```
signoz/
├── otel-collector      # Receives OTel data
├── query-service       # Query API
├── frontend            # Web UI / Grafana
└── timescaledb         # Storage backend (same tech as your app!)
```

**Why ideal for your stack:**
- Native TimescaleDB storage (same DB engine you already use)
- Built on proven CNCF standards (OpenTelemetry)
- Web UI is excellent for debugging
- No separate Grafana setup needed

---

### 2. FastAPI Instrumentation (Python)

**Current state:** Basic structlog setup, no observability

**What we'll add:**
```python
# OpenTelemetry auto-instrumentation packages
- opentelemetry-api
- opentelemetry-sdk
- opentelemetry-exporter-otlp
- opentelemetry-exporter-prometheus
- opentelemetry-instrumentation-fastapi
- opentelemetry-instrumentation-sqlalchemy
- opentelemetry-instrumentation-requests
- opentelemetry-instrumentation-aiohttp
```

**Metrics to capture:**
- HTTP request duration (latency percentiles: p50, p95, p99)
- HTTP error rates (by endpoint, status code)
- Request throughput (requests/sec)
- Request payload sizes
- Database query duration
- Database connection pool usage
- Custom: Measurement ingestion rate (msgs/sec)
- Custom: Authentication failures
- Custom: JWT token refresh failures

**Traces to capture:**
- Full request lifecycle (entry → DB → response)
- Backend API calls to `/influx_token`
- Database operations (with query context)
- Error stack traces with context

**Logs to capture:**
- Replace structlog with OpenTelemetry-native JSON logging
- Include trace context in all logs (trace_id, span_id)
- Structured fields: user_id, inverter_id, request_id
- Levels: DEBUG, INFO, WARNING, ERROR with proper context

**Example instrumented endpoint:**
```python
from opentelemetry import metrics, trace

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# Automatic via decorator:
@app.get("/api/measurements")
async def get_measurements(current_user: User = Depends(current_active_user)):
    # Span automatically created: name="GET /api/measurements"
    # Metrics tracked: duration, error rate
    # Logs include: trace_id, span_id, user_id
    pass
```

---

### 3. Rust Collector Instrumentation

**Current state:** Basic tracing with `tracing` crate (good foundation!)

**What we'll extend:**
```toml
# Add to Cargo.toml
opentelemetry = { version = "0.20", features = ["rt-tokio"] }
opentelemetry-otlp = { version = "0.13", features = ["http-proto"] }
tracing-opentelemetry = "0.21"
opentelemetry-prometheus = "0.13"  # For Prometheus metrics export
```

**Metrics to capture:**
- TCP connections: accepted, active, dropped
- Messages: received/sec, parsed/sec
- Parsing errors: by control code (0x4110, 0x4210, etc.)
- Packet validation failures
- Backend authentication failures
- InfluxDB write latency
- Per-logger data freshness (last_message_timestamp)

**Traces to capture:**
- Connection lifecycle (accept → read → parse → respond → close)
- Message processing (decode → validate → store)
- Backend API calls (token refresh, logger lookup)
- Error context (which control code failed, why)

**Logs to capture:**
- Replace emoji-based logs with structured OpenTelemetry logs
- Fields: logger_serial, remote_addr, control_code, packet_size, duration_ms
- Levels: DEBUG (protocol details), INFO (connections), WARN (errors), ERROR (failures)

**Example instrumented span:**
```rust
// Current:
info!("Client connected from {}", remote_addr);

// Will become (with OTel context):
let span = tracer.start("connection.handle");
span.set_attribute("remote_addr", remote_addr.to_string());
span.set_attribute("timestamp", SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs());
```

---

### 4. PostgreSQL Monitoring (Prometheus Exporter)

**What it does:**
- Exposes PostgreSQL metrics as Prometheus format
- Scrapped by SignOz Prometheus backend

**Container:**
```yaml
postgres-exporter:
  image: prometheuscommunity/postgres-exporter:latest
  environment:
    DATA_SOURCE_NAME: "postgresql://deyehard:password@db:5432/deyehard?sslmode=disable"
```

**Metrics to capture:**
- Connection stats (active, idle, total)
- Cache hit ratio (for tuning)
- Transaction rates (commits/sec, rollbacks/sec)
- Lock waits (debugging contention)
- Replication lag (if applicable)
- Disk usage (table, index, total)
- Slow query detection (queries > 1s)

**Custom TimescaleDB metrics (SQL queries):**
```sql
-- Chunk compression stats
SELECT
  schemaname,
  tablename,
  compressed_chunks,
  uncompressed_chunks
FROM timescaledb_information.chunks;

-- Retention policy status
SELECT tablename, oldest_data_time FROM timescaledb_information.hypertables;

-- Data growth rate
SELECT
  schemaname,
  tablename,
  pg_size_pretty(total_bytes) as size
FROM pg_tables_size
WHERE schemaname NOT IN ('pg_catalog', 'information_schema');
```

---

## Observability Signals Mapping

### What to Monitor & Why

#### FastAPI Backend

| Signal | Metric | Alert Threshold | Action |
|--------|--------|-----------------|--------|
| **API Health** | HTTP error rate | > 5% | Page oncall engineer |
| **API Performance** | p99 latency | > 1000ms | Investigate slow queries |
| **Auth Failures** | Failed JWT refreshes | > 10/min | Check auth backend |
| **Data Ingestion** | Measurement throughput | < 1 msg/sec (expected: 5-10/sec) | Check collectors |
| **Database** | Connection pool usage | > 80% | Scale up pool |
| | Slow queries | > 1s duration | Analyze with traces |
| **Sessions** | Expired sessions | Spikes > 2x normal | Check if auth changed |

#### Rust Collector

| Signal | Metric | Alert Threshold | Action |
|--------|--------|-----------------|--------|
| **TCP Server** | Active connections | 0 for > 5min | Collector down |
| **Message Rate** | Packets received/sec | 0 for > 10min | No data from inverters |
| **Errors** | Parsing failures | > 5% of packets | Check protocol version |
| **Backend Auth** | Token refresh failures | > 3 in 5min | Check backend connectivity |
| **Storage** | InfluxDB write latency | > 5s | Check InfluxDB health |
| **Data Freshness** | Last message per logger | > 1 hour | Logger not reporting |

#### PostgreSQL

| Signal | Metric | Alert Threshold | Action |
|--------|--------|-----------------|--------|
| **Connectivity** | Active connections | > 80% of max | Scale pool |
| **Storage** | Disk usage | > 80% | Plan expansion |
| **Compression** | Uncompressed chunks | > 10% of total | Manual compression |
| **Performance** | Cache hit ratio | < 99% | Tune query or cache |
| **Replication** | Data freshness | > 5min | Check network |

---

## Logging Strategy: OpenTelemetry-Native

### Current State
- **FastAPI**: structlog with console renderer (development-only format)
- **Rust Collector**: tracing with emoji-based logs

### Target State
```
All logs → OpenTelemetry SDK → SignOz → Structured JSON storage
         ↓
    Searchable by trace_id, span_id, user_id, inverter_id, etc.
```

### Log Structure

#### FastAPI Logs (OTel format)
```json
{
  "timestamp": "2025-10-22T14:23:45.123Z",
  "level": "INFO",
  "logger": "solar_backend.api.measurements",
  "message": "Measurement stored successfully",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "0af7651916cd43dd",
  "user_id": "user-123",
  "inverter_id": "inverter-456",
  "measurement_count": 42,
  "duration_ms": 145
}
```

#### Rust Collector Logs (OTel format)
```json
{
  "timestamp": "2025-10-22T14:23:45.123Z",
  "level": "INFO",
  "target": "solarman_collector::server::connection",
  "message": "Packet processed successfully",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "0af7651916cd43dd",
  "logger_serial": 4142050081,
  "control_code": "0x4210",
  "remote_addr": "192.168.1.100:54321",
  "packet_size": 256,
  "duration_ms": 2
}
```

### Log Levels & Usage

| Level | FastAPI | Rust Collector |
|-------|---------|-----------------|
| **DEBUG** | ORM queries, middleware execution | Protocol parsing, frame details |
| **INFO** | Request start/end, important state changes | Client connect/disconnect, data received |
| **WARN** | Deprecated usage, fallback code paths | Malformed packets, backend unavailable |
| **ERROR** | Unhandled exceptions, DB errors | Connection drops, storage failures |

---

## Alert Configuration

### Alert Rules (Email-based)

All alerts sent via email configured in SignOz. Email notifications configured via SMTP.

#### Tier 1: Critical (Page immediately)
```
1. Collector receiving 0 messages for 10+ minutes
   → Indicates data loss from all inverters
   → Action: SSH into collector, check TCP connection, restart if needed

2. FastAPI error rate > 10% for 5 minutes
   → Indicates service degradation
   → Action: Check error logs, restart if needed

3. Database connection pool > 90% usage
   → Indicates resource exhaustion
   → Action: Restart service to recycle connections

4. Disk usage > 95%
   → Indicates storage running out
   → Action: Archive old data or expand disk
```

#### Tier 2: Warning (Check within 1 hour)
```
5. HTTP p99 latency > 2000ms for 10 minutes
   → Indicates slow queries or system load
   → Action: Review slow query logs, optimize queries

6. Measurement ingestion rate < 1 msg/sec for 30 minutes
   → Indicates degraded collector throughput
   → Action: Check if inverters are reporting, check network

7. Auth token refresh failures > 5 per minute for 5 minutes
   → Indicates backend connectivity issues
   → Action: Check backend service, check network

8. Database slow queries > 5 per minute
   → Indicates performance degradation
   → Action: Run EXPLAIN ANALYZE, add indexes
```

#### Tier 3: Info (Check daily in dashboard)
```
9. Inverter not reporting for > 1 hour (per inverter)
   → Indicates specific inverter offline
   → Action: Check inverter status, connectivity

10. Cache hit ratio < 98%
    → Indicates suboptimal caching
    → Action: Review frequently missed queries

11. Chunk compression lag > 7 days
    → Indicates compression not running
    → Action: Trigger manual compression
```

### Alert Delivery Configuration

**Email Setup (SMTP):**
```yaml
# In SignOz notification settings
Provider: SMTP
Host: mail.example.com
Port: 587
From: monitoring@yourcompany.com
TLS: Yes
```

**Alert Rules Creation Flow:**
1. Define alert condition (metric + threshold)
2. Set duration (how long before triggering)
3. Configure notification channel (email)
4. Set cooldown period (avoid alert spam, e.g., 30 min)
5. Test alert delivery

---

## Deployment Architecture

### Docker Compose Structure

```yaml
services:
  # Existing services
  backend:
    # FastAPI with OTel instrumentation
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: http://signoz-otel-collector:4317

  db:
    # PostgreSQL TimescaleDB (existing)

  # New monitoring services
  signoz:
    # SignOz frontend & query service

  signoz-otel-collector:
    # OpenTelemetry collector (ingest point)

  postgres-exporter:
    # Prometheus exporter for PostgreSQL

  # Collector (Rust) will also report OTel data
  collector:
    environment:
      OTEL_EXPORTER_OTLP_ENDPOINT: http://signoz-otel-collector:4317
```

### Infrastructure Requirements

**For 100 users / 120 inverters:**
- SignOz: 1 CPU core, 2GB RAM
- PostgreSQL Exporter: 0.1 CPU, 100MB RAM
- **Total overhead: ~2.5GB RAM, modest CPU**

---

## Dashboard Layout

### Home Dashboard (Overview)
```
┌─────────────────────────────────────────────────────┐
│ System Status Widget                                │
│ • Backend uptime | Collector uptime | DB uptime     │
│ • Data ingestion rate (msgs/sec)                    │
│ • Active users (last 24h)                           │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Request Performance (last 24h)                      │
│ • Request rate (graph)                              │
│ • Error rate (graph)                                │
│ • p50, p95, p99 latency (gauge)                     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Data Collector Health (last 1h)                     │
│ • TCP connections (gauge)                           │
│ • Packet rate (msgs/sec)                            │
│ • Parse errors (errors/min)                         │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Database Health                                     │
│ • Connections (gauge)                               │
│ • Queries/sec (graph)                               │
│ • Disk usage (progress bar)                         │
│ • Cache hit ratio (%)                               │
└─────────────────────────────────────────────────────┘
```

### FastAPI Details Dashboard
```
┌─────────────────────────────────────────────────────┐
│ Request Breakdown (by endpoint)                     │
│ • GET /api/dashboard: 150ms p95                     │
│ • POST /api/measurements: 45ms p95                  │
│ • GET /api/inverter/{id}: 200ms p95                 │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Error Analysis                                      │
│ • Top error types (table)                           │
│ • Error rate by endpoint (heatmap)                  │
│ • Error traces (click to see full trace)            │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Database Operations                                 │
│ • Query duration by operation (box plot)            │
│ • Slow queries (> 1s) (table)                       │
│ • Connection pool usage (gauge)                     │
└─────────────────────────────────────────────────────┘
```

### Collector Details Dashboard
```
┌─────────────────────────────────────────────────────┐
│ Per-Logger Status                                   │
│ • Logger ID | Conn Status | Last Message | Rate     │
│ • 4142050081 | ✅ Connected | 2 min ago | 0.3 msg/s │
│ • 4142050082 | ✅ Connected | 5 sec ago | 0.4 msg/s │
│ • 4142050083 | ❌ Offline | 45 min ago | 0 msg/s     │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ Message Processing (last 1h)                        │
│ • Message rate by type (stacked bar)                │
│ • Decode errors (by control code)                   │
│ • Backend auth failures (time series)               │
└─────────────────────────────────────────────────────┘
```

---

## Observability Best Practices

### Instrumentation Guidelines

**DO:**
```python
# Use structured context
tracer.current_span().set_attribute("user_id", user.id)
tracer.current_span().set_attribute("inverter_id", inverter.id)

# Use semantic attribute names (OpenTelemetry standard)
tracer.current_span().set_attribute("http.method", "POST")
tracer.current_span().set_attribute("http.target", "/api/measurements")
tracer.current_span().set_attribute("db.statement", "SELECT * FROM users WHERE id = ?")

# Record business metrics
meter.create_counter("measurements_processed_total", unit="1").add(1)
meter.create_histogram("measurement_batch_size", unit="1").record(42)
```

**DON'T:**
```python
# Avoid string interpolation in logs
logger.info(f"Processing measurement for user {user.id}")  # BAD

# Avoid PII in logs
logger.info(f"Email: {user.email}")  # BAD

# Avoid cardinality explosions (unbounded attribute values)
tracer.current_span().set_attribute("timestamp", time.time())  # BAD - each value unique
```

### High-Cardinality Attributes

**Cardinality matters for storage efficiency:**
- LOW cardinality = few unique values (OK to record)
  - `inverter.status` = "online" | "offline" | "error" (3 values)
  - `http.status_code` = 200 | 401 | 500 (few values)

- HIGH cardinality = many unique values (avoid)
  - `timestamp` = 1729614225, 1729614226, ... (infinite values)
  - `request_id` = UUID for each request (unbounded)

**Good attributes for spans:**
```
• user_id (bounded, < 100 in your case)
• inverter_id (bounded, < 120 in your case)
• control_code (bounded, ~6 message types)
• http_method + http_path (bounded, ~50 endpoints)
• error_type (bounded, ~10-20 error categories)
```

---

## Troubleshooting Guide

### SignOz UI not loading
```bash
# Check if containers are running
docker ps | grep signoz

# Check logs
docker logs signoz-query-service
docker logs signoz-otel-collector

# Verify network connectivity
docker exec signoz-query-service curl http://signoz-otel-collector:4317
```

### No traces appearing in SignOz
```
1. Check application logs for OTEL exporter errors
2. Verify OTEL_EXPORTER_OTLP_ENDPOINT is set correctly
3. Check SignOz collector logs: docker logs signoz-otel-collector
4. Verify network: docker network ls, docker network inspect
5. Check firewall: telnet signoz-otel-collector 4317
```

### Alerts not triggering
```
1. Verify condition is met (check metrics in SignOz)
2. Check SMTP configuration in SignOz UI
3. Test email delivery: send test alert
4. Check spam folder
5. Review alert cooldown period (might be preventing duplicates)
```

### High disk usage in SignOz
```
1. Check retention policy (default: 7 days data)
2. Query SignOz database for largest tables
3. Consider reducing trace sampling rate
4. Archive old data if needed
```

---

## Maintenance & Operations

### Daily Tasks
- Monitor dashboard for any anomalies
- Check critical alert threshold is reasonable
- Review error trends in traces

### Weekly Tasks
- Review slow query insights
- Check alert response procedures work
- Verify backups are running

### Monthly Tasks
- Analyze observability trends
- Fine-tune alert thresholds
- Review and update dashboards
- Plan capacity if trending up

### Quarterly Tasks
- Review OpenTelemetry instrumentation for gaps
- Update documentation with lessons learned
- Plan any infrastructure scaling

---

## Cost & Resource Analysis

### Docker Compose Resource Allocation

```yaml
services:
  signoz:
    resources:
      limits:
        cpus: '1.0'
        memory: 1G

  signoz-otel-collector:
    resources:
      limits:
        cpus: '0.5'
        memory: 512M

  postgres-exporter:
    resources:
      limits:
        cpus: '0.1'
        memory: 100M

# Total overhead: ~2.5GB RAM, 1.6 CPU cores
```

### Data Retention Costs

**For 100 users / 120 inverters with baseline load:**

| Signal | Volume/Day | 7-Day Storage | Notes |
|--------|-----------|---------------|-------|
| **Traces** | ~100K | ~50MB | 1 trace per HTTP request + internal spans |
| **Metrics** | ~1M points | ~10MB | 1 metric every 15 seconds |
| **Logs** | ~500K lines | ~100MB | Structured JSON logs |
| **Total** | ~160MB/day | ~1.1GB | Easily fits in standard Docker setup |

With 7-day retention (configurable), you'll use ~1.1GB for SignOz data. Your PostgreSQL data (measurements) will be much larger (GB+ scale).

---

## Security Considerations

### What NOT to Log
- Passwords, API keys, tokens
- Email addresses, phone numbers (PII)
- IP addresses (unless necessary)
- Full request/response bodies

### OpenTelemetry Security
- OTLP protocol runs on same Docker network (no external exposure)
- Credentials stored in environment variables, not logs
- Consider network policies if running Kubernetes

### Email Alert Security
- Use app-specific passwords (not account password)
- Consider sending to monitored email, not personal email
- Use TLS for SMTP connection
- Rate-limit to prevent alert spam

---

## References

### OpenTelemetry
- [OpenTelemetry Python Docs](https://opentelemetry.io/docs/instrumentation/python/)
- [OpenTelemetry Rust Docs](https://opentelemetry.io/docs/instrumentation/rust/)
- [Semantic Conventions](https://opentelemetry.io/docs/reference/specification/protocol/exporter/)

### SignOz
- [SignOz Documentation](https://signoz.io/docs/)
- [Deploy in Docker](https://signoz.io/docs/deployment/docker/)

### Prometheus
- [Prometheus Docs](https://prometheus.io/docs/)
- [PostgreSQL Exporter](https://github.com/prometheus-community/postgres_exporter)

### OpenTelemetry Best Practices
- [OpenTelemetry Best Practices](https://opentelemetry.io/docs/guides/getting-started/)
- [Semantic Conventions for HTTP](https://opentelemetry.io/docs/reference/specification/semantic-conventions/http/)
- [Sampling Strategies](https://opentelemetry.io/docs/reference/specification/protocol/exporter/)

---

## Quick Reference: Key Observability Terms

| Term | Meaning | Example |
|------|---------|---------|
| **Trace** | Request journey across services | Single HTTP request flow |
| **Span** | Single operation in a trace | "GET /api/measurements" |
| **Metric** | Quantitative measurement | "requests per second" |
| **Log** | Event record with timestamp | "User login successful" |
| **Attribute** | Key-value context in spans | user_id=123, inverter_id=456 |
| **Cardinality** | Number of unique values | user_id has cardinality=100 |
| **Instrumentation** | Adding observability code | Adding tracer.start_span() |
| **Sampling** | Recording subset of traces | Sample 1% of requests |
| **Alert** | Trigger based on metric | Page if error_rate > 5% |

---

## Checklist: Before Going to Production

- [ ] Alerts tested and email delivery verified
- [ ] Dashboard created and shared with team
- [ ] Runbooks written for each critical alert
- [ ] Data retention policy set (7 days minimum)
- [ ] SMTP credentials secured in environment variables
- [ ] Backup procedure documented
- [ ] Team trained on using dashboards
- [ ] Daily dashboard review scheduled in calendar
- [ ] SignOz admin credentials changed from default
- [ ] Network policies configured (if using Kubernetes)

---

**Document Version:** 1.0
**Last Updated:** October 2025
**Status:** Planning phase - Ready for implementation
