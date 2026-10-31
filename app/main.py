import time
import random
import json
import logging
import sys
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response


app = FastAPI(
    title="Observability Training API",
    description="Application used for the Observability course",
    version="2.0.0",
)


# --------------------------------------------------
# Logging Directory
# --------------------------------------------------

LOG_DIR = "/logs"

os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIR,
    "application.log"
)


# --------------------------------------------------
# Structured JSON Logging
# --------------------------------------------------

class JsonFormatter(logging.Formatter):

    def format(self, record):

        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "order-service",
            "environment": "training",
        }

        if hasattr(record, "http_method"):
            log_record["http_method"] = record.http_method

        if hasattr(record, "http_path"):
            log_record["http_path"] = record.http_path

        if hasattr(record, "http_status"):
            log_record["http_status"] = record.http_status

        if hasattr(record, "duration_ms"):
            log_record["duration_ms"] = record.duration_ms

        if hasattr(record, "dependency"):
            log_record["dependency"] = record.dependency

        return json.dumps(log_record)


# --------------------------------------------------
# Console Handler
# --------------------------------------------------

console_handler = logging.StreamHandler(sys.stdout)

console_handler.setFormatter(
    JsonFormatter()
)


# --------------------------------------------------
# File Handler
# --------------------------------------------------

file_handler = logging.FileHandler(
    LOG_FILE
)

file_handler.setFormatter(
    JsonFormatter()
)


# --------------------------------------------------
# Application Logger
# --------------------------------------------------

logger = logging.getLogger(
    "observability-app"
)

logger.setLevel(logging.INFO)

logger.handlers.clear()

logger.addHandler(
    console_handler
)

logger.addHandler(
    file_handler
)

logger.propagate = False


# --------------------------------------------------
# Prometheus Metrics
# --------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "http_status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)


# --------------------------------------------------
# HTTP Request Instrumentation
# --------------------------------------------------

@app.middleware("http")
async def observe_requests(
    request: Request,
    call_next
):

    start_time = time.perf_counter()

    response = None

    try:

        response = await call_next(request)

        return response

    finally:

        duration_seconds = (
            time.perf_counter()
            - start_time
        )

        duration_ms = round(
            duration_seconds * 1000,
            2
        )

        status_code = (
            response.status_code
            if response
            else 500
        )

        endpoint = request.url.path

        method = request.method

        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            http_status=str(status_code),
        ).inc()

        REQUEST_LATENCY.labels(
            method=method,
            endpoint=endpoint,
        ).observe(
            duration_seconds
        )

        logger.info(
            "HTTP request completed",
            extra={
                "http_method": method,
                "http_path": endpoint,
                "http_status": status_code,
                "duration_ms": duration_ms,
            },
        )


# --------------------------------------------------
# Application Endpoints
# --------------------------------------------------

@app.get("/")
def root():

    return {
        "application": "observability-training-api",
        "message": "Welcome to the Observability Training API",
    }


@app.get("/health")
def health():

    return {
        "status": "UP"
    }


@app.get("/orders")
def get_orders():

    orders = [
        {
            "id": 1,
            "customer": "Alice",
            "amount": 250
        },
        {
            "id": 2,
            "customer": "Bob",
            "amount": 450
        },
        {
            "id": 3,
            "customer": "Charlie",
            "amount": 150
        },
    ]

    return {
        "count": len(orders),
        "orders": orders,
    }


@app.get("/orders/{order_id}")
def get_order(
    order_id: int
):

    if order_id <= 0:

        raise HTTPException(
            status_code=400,
            detail="Order ID must be greater than zero",
        )

    return {
        "id": order_id,
        "customer": "Training Customer",
        "amount": 500,
        "status": "CREATED",
    }


@app.post("/orders")
def create_order():

    return {
        "message": "Order created successfully",
        "order_id": random.randint(
            1000,
            9999
        ),
    }


# --------------------------------------------------
# Simulation Endpoints
# --------------------------------------------------

@app.get("/simulate/slow")
def simulate_slow():

    time.sleep(3)

    return {
        "message": "Slow response completed",
        "delay_seconds": 3,
    }


@app.get("/simulate/error")
def simulate_error():

    logger.error(
        "Simulated application error"
    )

    raise HTTPException(
        status_code=500,
        detail="Simulated internal server error",
    )


@app.get("/simulate/downstream-error")
def simulate_downstream_error():

    logger.error(
        "Simulated downstream dependency failure",
        extra={
            "dependency": "payment-service",
        },
    )

    raise HTTPException(
        status_code=503,
        detail="Downstream dependency unavailable",
    )


# --------------------------------------------------
# Prometheus Metrics
# --------------------------------------------------

@app.get("/metrics")
def metrics():

    return Response(
        content=generate_latest(),
        media_type="text/plain",
    )