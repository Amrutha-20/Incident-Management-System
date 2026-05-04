# Incident Management System (IMS)

A mission-critical, production-grade Incident Management System built to monitor a distributed stack (APIs, MCP Hosts, Distributed Caches, Async Queues, RDBMS, and NoSQL stores) and manage failure mediation workflows end-to-end.

---

## Architecture Diagram
```mermaid
flowchart TD
    A[Signal Producers] --> B[POST /api/v1/signals]
    B --> C[Rate Limiter (slowapi)]
    C --> D[Ring Buffer (In-Memory)]

    D --> E[Worker Pool (4 Async Tasks)]

    E --> F[Debounce Engine (Redis-backed)]
    E --> G[Redis SETNX Lock]

    G --> H[Work Item per Component/Window]

    F --> I[MongoDB (Raw Signals / Audit Log)]
    H --> J[PostgreSQL (Work Items + RCA)]
    H --> K[Redis (Hot Cache for Dashboard)]
    H --> L[InfluxDB (Time-series / MTTR)]

    style D fill:#e3f2fd
    style E fill:#e8f5e9
    style G fill:#fff3e0
    style F fill:#f3e5f5


## Backpressure Strategy

When the ring buffer is full (default: 50,000 signals):
- New signals are **dropped** with HTTP 503 (not queued forever)
- The caller receives a clear error and must retry with backoff
- Drop count is tracked in `buffer.stats.total_dropped`
- Buffer utilization is exposed on `/health`

This prevents unbounded memory growth and cascading failures when the persistence layer is slow.

## Debounce Race Condition Handling

Two workers could simultaneously check "does a Work Item exist for CACHE_CLUSTER_01?" and both decide to create one. This is prevented by:

1. `SET debounce:lock:{component_id} NX EX 10` — atomic Redis SETNX
2. Only the winner proceeds to create; losers retry the GET after 50ms
3. The Work Item ID is stored in Redis with TTL=10s immediately after creation
4. All subsequent signals in the window find the ID and just append


## Design Patterns Used

- **Strategy** — `app/core/alerting.py` — pluggable alert backends per component type
- **State** — `app/core/state_machine.py` — enforces valid status transitions
- **Repository** — `app/db/postgres.py`, `mongo.py` — data access layer separation
- **Object Pool** — asyncpg connection pool, motor async client



---

## Setup Instructions

### Prerequisites
- Docker Desktop 24+ (running)
- Node.js 20+ (for local frontend dev)
- Python 3.12+ (for local testing)

### 1. Clone / download the project

```bash
cd "D:\Incident Management System"
```

### 2. Start all services with Docker Compose

```powershell
docker compose up --build
```

This starts 6 containers in dependency order:
1. `postgres` — waits for healthcheck
2. `mongo` — waits for healthcheck
3. `redis` — waits for healthcheck
4. `influxdb` — waits for healthcheck
5. `backend` — starts after all DBs are healthy
6. `frontend` — starts after backend

### 3. Verify everything is running

```powershell
docker compose ps
curl http://localhost:8000/health
```

### 4. Open the dashboard
http://localhost:5173      ← React frontend
http://localhost:8000/docs ← Swagger API docs
http://localhost:8000/health ← Health check

### 5. Seed failure scenario data

```powershell
cd backend
pip install httpx
python scripts/seed_failure_scenario.py --url http://localhost:8000
```

### 6. Run unit tests

```powershell
cd backend
venv\Scripts\activate
pytest tests/test_core.py -v
```

### 7. Run frontend locally (recommended for development)

```powershell
cd frontend
npm install
npm run dev
```

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Liveness check + throughput metrics |
| `POST` | `/api/v1/signals` | Ingest single signal |
| `POST` | `/api/v1/signals/batch` | Ingest up to 500 signals |
| `GET` | `/api/v1/signals/{work_item_id}` | Raw signals from MongoDB |
| `GET` | `/api/v1/incidents` | List active incidents (Redis cached) |
| `GET` | `/api/v1/incidents/{id}` | Full detail + signals + RCA |
| `PATCH` | `/api/v1/incidents/{id}/status` | State machine transition |

---

## How Backpressure is Handled

The system uses a **bounded in-memory ring buffer** as the primary backpressure mechanism:

1. **Ingest API** accepts signals at up to 10,000/sec and immediately enqueues them into the ring buffer (O(1) operation — never blocks the HTTP layer)
2. **Ring buffer** has a fixed capacity of 50,000 signals. When full, new signals are **dropped** and the caller receives HTTP 503 with a retry hint
3. **Worker pool** (4 async tasks) drains the buffer continuously and persists to all storage sinks
4. **Drop counter** is tracked in `buffer.stats.total_dropped` and exposed on `/health`
5. **Buffer utilization** is reported every 5 seconds to stdout and to InfluxDB

This ensures the HTTP layer never blocks or crashes even if PostgreSQL, MongoDB, or Redis are slow or temporarily unavailable.

Fast producers → [Ring Buffer 50k] → Slow workers → DBs
↓ (when full)
DROP + HTTP 503
(caller retries)

---

## Debounce Race Condition Handling

If 100 signals arrive for `CACHE_CLUSTER_01` within 10 seconds, only **1 Work Item** is created:

1. First signal increments Redis counter `debounce:count:CACHE_CLUSTER_01` (atomic INCR)
2. Worker attempts `SET debounce:lock:CACHE_CLUSTER_01 NX EX 10` — only one wins
3. Winner creates the Work Item in PostgreSQL and stores the ID in Redis with 10s TTL
4. All subsequent signals find the existing Work Item ID in Redis and just append their signal_id
5. All 100 raw signals are stored in MongoDB linked to the single Work Item

---

## Observability

- **Throughput metrics** printed to stdout every 5 seconds:
[THROUGHPUT] signals/sec=245.3 | enqueued=12450 | dropped=0 | processed=12448 | buffer=24.9%

- **`/health` endpoint** returns real-time stats:
  - `signals_per_sec` — rolling 5-second window
  - `buffer_utilization_pct` — current ring buffer usage
  - `active_work_items` — count from PostgreSQL
  - `checks` — per-dependency liveness (postgres, mongodb, redis, ring_buffer)

---

## Useful Commands

```powershell
# Start everything
docker compose up --build

# Stop everything (keep data)
docker compose down

# Stop and wipe all data
docker compose down -v

# View backend logs live
docker compose logs -f backend

# View throughput metrics
docker compose logs -f backend | Select-String "THROUGHPUT"

# Rebuild only backend
docker compose build --no-cache backend
docker compose up backend

# Shell into backend container
docker exec -it incidentmanagementsystem-backend-1 bash

# Shell into PostgreSQL
docker exec -it incidentmanagementsystem-postgres-1 psql -U ims -d ims_db

# Run tests
cd backend
venv\Scripts\activate
pytest tests/test_core.py -v
```


## Submission Checklist

- [x] `/backend` — FastAPI Python backend
- [x] `/frontend` — React + Vite dashboard
- [x] `docker-compose.yml` — One-command setup
- [x] `README.md` — Architecture diagram, setup, backpressure explanation
- [x] `scripts/seed_failure_scenario.py` — RDBMS + MCP failure simulation
- [x] `tests/test_core.py` — Unit tests for state machine + RCA + ring buffer
- [x] Rate limiting on ingest API
- [x] Debounce engine with Redis atomic locks
- [x] State machine with RCA gate
- [x] Strategy pattern for alerting
- [x] MTTR auto-calculation on close
- [x] `/health` endpoint with throughput metrics
- [x] Backpressure via ring buffer with drop counter