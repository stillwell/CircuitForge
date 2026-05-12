# CircuitForge — multi-stage Docker build
# Stage 1: build wheels for fast cold starts; Stage 2: minimal runtime.

FROM python:3.12-slim AS build

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip wheel --no-cache-dir --wheel-dir=/wheels \
        -r requirements.txt flask flask-cors gunicorn "qrcode[pil]"

# ----------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="CircuitForge"
LABEL org.opencontainers.image.description="Open-source EDA suite — schematic, SPICE, PCB"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/stillwell/circuitforge"

RUN apt-get update && apt-get install -y --no-install-recommends \
        qrencode \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 circuitforge \
    && useradd --system --uid 1000 --gid 1000 --no-create-home \
               --shell /usr/sbin/nologin circuitforge

WORKDIR /opt/circuitforge
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY circuitforge ./circuitforge
COPY images ./images
COPY run_cloud.py run_web.py main.py setup.py requirements.txt README.md ./
COPY examples ./examples
COPY docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh
RUN chmod +x /usr/local/bin/api-entrypoint.sh

RUN mkdir -p /opt/circuitforge/data && chown -R circuitforge:circuitforge /opt/circuitforge

USER circuitforge
ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080

EXPOSE 8080 5000

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/api-entrypoint.sh"]
CMD ["api"]
