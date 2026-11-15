import time
import random
import logging

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import Response


app = FastAPI(
    title="Observability Training API",
    description="Application used for the Observability course",
    version="1.0.0",
)


# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("observability-app")


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
        {"id": 1, "customer": "Alice", "amount": 250},
        {"id": 2, "customer": "Bob", "amount": 450},
        {"id": 3, "customer": "Charlie", "amount": 150},
    ]

    return {
        "count": len(orders),
        "orders": orders,
    }


@app.get("/orders/{order_id}")
def get_order(order_id: int):
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
        "order_id": random.randint(1000, 9999),
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
    logger.error("Simulated application error")

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
# Prometheus Metrics Endpoint
# --------------------------------------------------

@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type="text/plain",
    )