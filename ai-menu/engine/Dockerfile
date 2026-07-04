FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .  2>/dev/null || true

COPY . .
RUN pip install --no-cache-dir -e .
RUN pip install --no-cache-dir "httpx>=0.27,<1.0"

EXPOSE 8000

CMD ["python", "-m", "f2m_engine.cli", "serve-api", \
     "--dsn", "", \
     "--derived", "/app/data/derived", \
     "--host", "0.0.0.0", \
     "--port", "8000"]
