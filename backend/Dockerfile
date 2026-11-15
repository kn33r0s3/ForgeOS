FROM dhi.io/python:3.13-debian13-dev AS dependencies

WORKDIR /tmp/build
COPY requirements.txt requirements-optional.txt ./
RUN python -m pip install --no-cache-dir --target /tmp/deps -r requirements.txt
ARG INSTALL_OPTIONAL_AI=false
RUN if [ "$INSTALL_OPTIONAL_AI" = "true" ]; then \
      python -m pip install --no-cache-dir --target /tmp/deps -r requirements-optional.txt; \
    fi

FROM dhi.io/python:3.13-debian13

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/.deps:/app/backend \
    PATH=/app/backend/.deps/bin:$PATH

WORKDIR /app/backend
COPY --from=dependencies --chown=65532:65532 /tmp/deps /app/backend/.deps
COPY --chown=65532:65532 . .

EXPOSE 8000
HEALTHCHECK --interval=8s --timeout=5s --start-period=20s --retries=8 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
