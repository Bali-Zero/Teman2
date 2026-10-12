FROM postgres:17

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-17-postgis-3 \
        postgresql-17-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*

ARG DOCKERFILE_SHA
LABEL nuzantara.dockerfile.sha256="${DOCKERFILE_SHA}"
