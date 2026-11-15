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

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor


# ==================================================
# OpenTelemetry Configuration
# ==================================================

resource = Resource.create(
    {
        "service.name": "order-service",
        "service.version": "3.0.0",
        "deployment.environment.name": "training",
    }
)


tracer_provider = TracerProvider(
    resource=resource
)


otlp_exporter = OTLPSpanExporter(
    endpoint="http://otel-collector:4316",
    insecure=True,
)


span_processor = BatchSpanProcessor(
    otlp_exporter
)


tracer_provider.add_span_processor(
    span_processor
)


trace.set_tracer_provider(
    tracer_provider
)


tracer = trace.get_tracer(
    "observability-training-api"
)


# ==================================================
# FastAPI
# ==================================================

app = FastAPI(
    title="Observability Training API",
    description="Application used for OpenTelemetry training",
    version="3.0.0",
)


# ==================================================
# OpenTelemetry Automatic Instrumentation
# ==================================================

FastAPIInstrumentor.instrument_app(
    app
)

RequestsInstrumentor().instrument()


# ==================================================
# Logging
# ==================================================

LOG_DIR = "/logs"

os.makedirs(
    LOG_DIR,
    exist_ok=True
)

LOG_FILE = os.path.join(
    LOG_DIR,
    "application.log"
)


class JsonFormatter(logging.Formatter):

    def format(self, record):

        current_span = trace.get_current_span()

        span_context = current_span.get_span_context()

        trace_id = ""

        span_id = ""

        if span_context.is_valid:

            trace_id = format(
                span_context.trace_id,
                "032x"
            )

            span_id = format(
                span_context.span_id,
                "016x"
            )

        log_record = {

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "level":
                record.levelname,

            "logger":
                record.name,

            "message":
                record.getMessage(),

            "service":
                "order-service",

            "environment":
                "training",

            "trace_id":
                trace_id,

            "span_id":
                span_id,
        }


        if hasattr(
            record,
            "http_method"
        ):

            log_record[
                "http_method"
            ] = record.http_method


        if hasattr(
            record,
            "http_path"
        ):

            log_record[
                "http_path"
            ] = record.http_path


        if hasattr(
            record,
            "http_status"
        ):

            log_record[
                "http_status"
            ] = record.http_status


        if hasattr(
            record,
            "duration_ms"
        ):

            log_record[
                "duration_ms"
            ] = record.duration_ms


        if hasattr(
            record,
            "dependency"
        ):

            log_record[
                "dependency"
            ] = record.dependency


        return json.dumps(
            log_record
        )


console_handler = logging.StreamHandler(
    sys.stdout
)

console_handler.setFormatter(
    JsonFormatter()
)


file_handler = logging.FileHandler(
    LOG_FILE
)

file_handler.setFormatter(
    JsonFormatter()
)


logger = logging.getLogger(
    "observability-app"
)

logger.setLevel(
    logging.INFO
)

logger.handlers.clear()

logger.addHandler(
    console_handler
)

logger.addHandler(
    file_handler
)

logger.propagate = False


# ==================================================
# Prometheus Metrics
# ==================================================

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    [
        "method",
        "endpoint",
        "http_status"
    ],
)


REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    [
        "method",
        "endpoint"
    ],
)


# ==================================================
# HTTP Logging Middleware
# ==================================================

@app.middleware("http")
async def observe_requests(
    request: Request,
    call_next
):

    start_time = time.perf_counter()

    response = None

    try:

        response = await call_next(
            request
        )

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
            http_status=str(
                status_code
            ),
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
                "http_method":
                    method,

                "http_path":
                    endpoint,

                "http_status":
                    status_code,

                "duration_ms":
                    duration_ms,
            },
        )


# ==================================================
# Root
# ==================================================

@app.get("/")
def root():

    return {
        "application":
            "observability-training-api",

        "version":
            "3.0.0",

        "message":
            "OpenTelemetry tracing enabled",
    }


# ==================================================
# Health
# ==================================================

@app.get("/health")
def health():

    return {
        "status": "UP"
    }


# ==================================================
# Orders
# ==================================================

@app.get("/orders")
def get_orders():

    with tracer.start_as_current_span(
        "fetch-orders"
    ):

        time.sleep(
            0.1
        )

        orders = [

            {
                "id": 1,
                "customer": "Alice",
                "amount": 250,
            },

            {
                "id": 2,
                "customer": "Bob",
                "amount": 450,
            },

            {
                "id": 3,
                "customer": "Charlie",
                "amount": 150,
            },
        ]

        return {
            "count":
                len(orders),

            "orders":
                orders,
        }


# ==================================================
# Order By ID
# ==================================================

@app.get(
    "/orders/{order_id}"
)
def get_order(
    order_id: int
):

    if order_id <= 0:

        raise HTTPException(
            status_code=400,
            detail=
                "Order ID must be greater than zero",
        )


    with tracer.start_as_current_span(
        "order-processing"
    ) as span:

        span.set_attribute(
            "order.id",
            order_id
        )

        time.sleep(
            0.1
        )

        return {

            "id":
                order_id,

            "customer":
                "Training Customer",

            "amount":
                500,

            "status":
                "CREATED",
        }


# ==================================================
# Simulated Database
# ==================================================

def simulate_database_query():

    with tracer.start_as_current_span(
        "database-query"
    ) as span:

        span.set_attribute(
            "db.system",
            "postgresql"
        )

        span.set_attribute(
            "db.operation.name",
            "SELECT"
        )

        span.set_attribute(
            "db.collection.name",
            "orders"
        )

        time.sleep(
            0.2
        )

        return {
            "database":
                "postgresql",

            "records":
                3,
        }


# ==================================================
# Simulated Payment Service
# ==================================================

def simulate_payment_service(
    slow=False
):

    with tracer.start_as_current_span(
        "payment-service"
    ) as span:

        span.set_attribute(
            "service.name",
            "payment-service"
        )

        span.set_attribute(
            "dependency.type",
            "downstream-http"
        )


        if slow:

            span.set_attribute(
                "simulation",
                "slow-payment"
            )

            time.sleep(
                3
            )

        else:

            time.sleep(
                0.2
            )


        return {
            "status":
                "APPROVED"
        }


# ==================================================
# Distributed Trace Demo
# ==================================================

@app.get(
    "/orders/{order_id}/checkout"
)
def checkout_order(
    order_id: int
):

    with tracer.start_as_current_span(
        "checkout-order"
    ) as span:

        span.set_attribute(
            "order.id",
            order_id
        )


        database_result = (
            simulate_database_query()
        )


        payment_result = (
            simulate_payment_service()
        )


        return {

            "order_id":
                order_id,

            "database":
                database_result,

            "payment":
                payment_result,

            "status":
                "COMPLETED",
        }


# ==================================================
# Slow Checkout
# ==================================================

@app.get(
    "/orders/{order_id}/checkout/slow"
)
def slow_checkout(
    order_id: int
):

    with tracer.start_as_current_span(
        "slow-checkout-order"
    ) as span:

        span.set_attribute(
            "order.id",
            order_id
        )

        database_result = (
            simulate_database_query()
        )

        payment_result = (
            simulate_payment_service(
                slow=True
            )
        )

        return {

            "order_id":
                order_id,

            "database":
                database_result,

            "payment":
                payment_result,

            "status":
                "COMPLETED",
        }


# ==================================================
# Error Scenario
# ==================================================

@app.get(
    "/simulate/error"
)
def simulate_error():

    with tracer.start_as_current_span(
        "error-operation"
    ) as span:

        span.set_attribute(
            "error.simulation",
            True
        )

        logger.error(
            "Simulated application error"
        )

        span.record_exception(
            Exception(
                "Simulated application error"
            )
        )

        span.set_status(
            trace.Status(
                trace.StatusCode.ERROR,
                "Simulated application error"
            )
        )

        raise HTTPException(
            status_code=500,
            detail=
                "Simulated internal server error",
        )


# ==================================================
# Downstream Error
# ==================================================

@app.get(
    "/simulate/downstream-error"
)
def simulate_downstream_error():

    with tracer.start_as_current_span(
        "downstream-payment-error"
    ) as span:

        span.set_attribute(
            "dependency",
            "payment-service"
        )

        span.set_status(
            trace.Status(
                trace.StatusCode.ERROR,
                "Payment service unavailable"
            )
        )

        logger.error(
            "Simulated downstream dependency failure",
            extra={
                "dependency":
                    "payment-service"
            },
        )

        raise HTTPException(
            status_code=503,
            detail=
                "Downstream dependency unavailable",
        )


# ==================================================
# Metrics
# ==================================================

@app.get("/metrics")
def metrics():

    return Response(
        content=
            generate_latest(),

        media_type=
            "text/plain",
    )