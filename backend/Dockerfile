FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/.deps:/app/backend \
    PATH=/app/backend/.deps/bin:$PATH

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install into an explicit application-local target instead of a venv or the
# image's global site-packages. This is the same constrained-environment path
# used by verification and makes dependency resolution deterministic.
COPY requirements.txt requirements-optional.txt ./
RUN python -m pip install --no-cache-dir --target /app/backend/.deps -r requirements.txt
ARG INSTALL_OPTIONAL_AI=false
RUN if [ "$INSTALL_OPTIONAL_AI" = "true" ]; then \
      python -m pip install --no-cache-dir --target /app/backend/.deps -r requirements-optional.txt; \
    fi

COPY . .

EXPOSE 8000
HEALTHCHECK --interval=8s --timeout=5s --start-period=20s --retries=8 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
