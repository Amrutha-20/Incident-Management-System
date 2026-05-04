# 📘 Prompts.md --- Design, Specs & Development Process

This document captures all **prompts, specifications, architectural
decisions, and planning steps** used to build the **Incident Management
System (IMS)**.

It reflects the **engineering thought process, tradeoffs, and system
design decisions** followed from problem definition to implementation.

------------------------------------------------------------------------

## 1. Problem Definition

**Prompt**

    Design a high-throughput backend system that:
    - Ingests real-time signals (10k+/sec)
    - Avoids duplicate incident creation
    - Handles database slowness gracefully
    - Provides strong consistency for incidents
    - Exposes observability metrics

**Outcome** - Defined system goals: scalability, reliability,
consistency

------------------------------------------------------------------------

## 2. High-Level Architecture

**Prompt**

    Design an event-driven system with:
    - Non-blocking ingestion API
    - Asynchronous processing
    - Backpressure handling
    - Multi-database architecture

**Outcome** - FastAPI ingestion layer\
- Ring buffer for decoupling\
- Async worker pool\
- Polyglot persistence

------------------------------------------------------------------------

## 3. Backpressure Strategy

**Prompt**

    How should the system behave when incoming traffic exceeds processing capacity?
    Queue indefinitely or drop requests?

**Decision** - Use bounded ring buffer (50,000 capacity) - Drop requests
with HTTP 503

**Reasoning** - Prevents memory overflow\
- Avoids cascading failures

**Tradeoff** - Prefer controlled data loss over system crash

------------------------------------------------------------------------

## 4. Concurrency & Race Conditions

**Prompt**

    Multiple workers may attempt to create the same incident.
    How do we ensure exactly one Work Item per component?

**Solution**

    SET debounce:lock:{component_id} NX EX 10

**Outcome** - Eliminates duplicate incidents\
- Ensures deterministic behavior

------------------------------------------------------------------------

## 5. Debounce Design

**Prompt**

    How do we group multiple signals into a single incident window?

**Solution** - Time-based debounce (10 seconds)\
- Redis counters with TTL

**Outcome** - Multiple signals → Single Work Item\
- Full audit preserved in MongoDB

------------------------------------------------------------------------

## 6. Worker Architecture

**Prompt**

    How do we process signals asynchronously without blocking the API?

**Solution** - Fixed async worker pool (4 workers)\
- Continuous buffer draining

**Responsibilities** - Apply debounce logic\
- Persist data\
- Update cache\
- Emit metrics

------------------------------------------------------------------------

## 7. Database Design (Polyglot Persistence)

**Prompt**

    Should we use a single database or multiple specialized databases?

**Decision**

  Use Case              Database
  --------------------- ------------
  Transactions          PostgreSQL
  High-volume logs      MongoDB
  Cache + locks         Redis
  Time-series metrics   InfluxDB

**Reasoning** - Each database is optimized for its workload

------------------------------------------------------------------------

## 8. API Design

**Prompt**

    Design REST APIs for ingestion, incident management, and observability

**Endpoints** - `/api/v1/signals`\
- `/api/v1/incidents`\
- `/health`

------------------------------------------------------------------------

## 9. Observability

**Prompt**

    What metrics are required to monitor system health?

**Metrics** - signals/sec\
- buffer utilization\
- dropped signals\
- database health

**Exposure** - `/health` endpoint\
- structured logs

------------------------------------------------------------------------

## 10. Design Patterns

**Prompt**

    How can we make the system extensible and maintainable?

**Patterns Used** - Strategy Pattern → Alerting system\
- State Pattern → Incident lifecycle\
- Repository Pattern → Data abstraction\
- Object Pool → DB connection pooling

------------------------------------------------------------------------

## 11. Failure Simulation

**Prompt**

    How do we validate system behavior under failure conditions?

**Approach** - Simulate: - High load bursts\
- DB failures\
- Cache delays

------------------------------------------------------------------------

## 12. Performance Optimization

**Prompt**

    How do we achieve high throughput and low latency?

**Techniques** - O(1) ring buffer operations\
- Async I/O\
- Redis caching\
- Batch ingestion APIs
