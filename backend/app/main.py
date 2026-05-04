"""
FastAPI application entry point.

Startup sequence:
  1. Connect to PostgreSQL, MongoDB, Redis, InfluxDB
  2. Run DB migrations
  3. Start worker pool (drains ring buffer)
  4. Mount routers

Shutdown sequence:
  1. Stop worker pool gracefully
  2. Close all DB connections
"""

from __future__ import annotations
from contextlib import asynccontextmanager
import structlog
import asyncpg
import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.core.ring_buffer import SignalRingBuffer
from app.core.debounce import DebounceEngine
from app.db.postgres import WorkItemRepository
from app.db.mongo import SignalRepository
from app.db.cache import DashboardCache
from app.db.timeseries import TimeseriesRepository
from app.services.incident_service import IncidentService
from app.workers.signal_worker import WorkerPool
from app.api import signals, incidents, health

logger = structlog.get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────
    logger.info("app.startup", env=settings.model_dump(exclude={"influx_token"}))

    # PostgreSQL
    pg_pool = await asyncpg.create_pool(
        settings.postgres_dsn,
        min_size=5,
        max_size=20,
        command_timeout=30,
    )

    # MongoDB
    mongo_client = AsyncIOMotorClient(settings.mongo_uri)

    # Redis
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

    # InfluxDB
    tsdb = TimeseriesRepository()

    # Repos
    pg_repo = WorkItemRepository(pg_pool)
    mongo_repo = SignalRepository(mongo_client, settings.mongo_db)
    cache = DashboardCache(redis_client)
    debounce = DebounceEngine(redis_client)

    # Migrate / ensure indexes
    await pg_repo.migrate()
    await mongo_repo.ensure_indexes()

    # Ring buffer
    buffer = SignalRingBuffer(capacity=settings.ring_buffer_capacity)

    # Service
    incident_svc = IncidentService(pg_repo, mongo_repo, cache, tsdb)

    # Worker pool
    pool = WorkerPool(
        buffer=buffer,
        debounce=debounce,
        pg_repo=pg_repo,
        mongo_repo=mongo_repo,
        cache=cache,
        tsdb=tsdb,
        worker_count=settings.worker_count,
    )
    await pool.start()

    # Attach to app state for dependency injection via request.app.state
    app.state.pg_pool = pg_pool
    app.state.mongo_client = mongo_client
    app.state.redis_client = redis_client
    app.state.pg_repo = pg_repo
    app.state.mongo_repo = mongo_repo
    app.state.cache = cache
    app.state.tsdb = tsdb
    app.state.buffer = buffer
    app.state.incident_service = incident_svc
    app.state.worker_pool = pool

    logger.info("app.ready")
    yield

    # ── Shutdown ─────────────────────────────
    logger.info("app.shutdown")
    await pool.stop()
    await pg_pool.close()
    mongo_client.close()
    await redis_client.aclose()
    await tsdb.close()
    logger.info("app.shutdown_complete")


# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── App factory ───────────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title="Incident Management System",
        version="1.0.0",
        description="Mission-critical IMS with real-time signal ingestion and incident lifecycle management",
        lifespan=lifespan,
    )

    # CORS (allow React dev server)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting middleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Routers
    app.include_router(signals.router)
    app.include_router(incidents.router)
    app.include_router(health.router)

    @app.get("/")
    async def root():
        return {"service": "IMS", "version": "1.0.0", "docs": "/docs"}

    return app


app = create_app()