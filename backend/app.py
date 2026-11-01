import os
import time
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import psycopg2
from prometheus_client import Counter, Histogram, generate_latest

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REQUEST_COUNT = Counter('backend_requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_LATENCY = Histogram('backend_request_latency_seconds', 'Request latency')

def get_db():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'db'),
        database=os.getenv('DB_NAME', 'appdb'),
        user=os.getenv('DB_USER', 'appuser'),
        password=os.getenv('DB_PASSWORD', 'apppassword')
    )

def init_db(retries=15, delay=2):
    for attempt in range(retries):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            cur.close()
            conn.close()
            logger.info("Database initialized successfully")
            return
        except psycopg2.OperationalError as e:
            logger.warning(f"Database not ready (attempt {attempt + 1}/{retries}): {e}")
            time.sleep(delay)
    raise Exception("Could not connect to database after multiple retries")

@app.route('/notes', methods=['GET'])
@REQUEST_LATENCY.time()
def get_notes():
    REQUEST_COUNT.labels(method='GET', endpoint='/notes').inc()
    logger.info("Fetching all notes")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, content, created_at FROM notes ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    notes = [{"id": r[0], "content": r[1], "created_at": r[2].isoformat()} for r in rows]
    return jsonify(notes)

@app.route('/notes', methods=['POST'])
@REQUEST_LATENCY.time()
def add_note():
    REQUEST_COUNT.labels(method='POST', endpoint='/notes').inc()
    data = request.get_json()
    content = data.get('content', '').strip()
    if not content:
        return jsonify({"error": "content required"}), 400
    logger.info(f"Adding note: {content[:50]}")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO notes (content) VALUES (%s) RETURNING id, created_at", (content,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"id": row[0], "content": content, "created_at": row[1].isoformat()}), 201

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': 'text/plain'}

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)