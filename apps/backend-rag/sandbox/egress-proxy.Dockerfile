# egress-proxy image — P3 Tier-1 network chokepoint (FASE-1 SOTA meta-dev-loop).
# Spec: research/operations/specs/P3-test-prod-sandbox.md §3.2.
#
# Build context MUST be the repo root (see docker-compose.sandbox.yml: context ../..)
# because it needs both scripts/_redact_pii.py AND agent-library/config/redaction-rules.yaml,
# laid out so the redactor's DEFAULT_CONFIG_PATH (__file__.parent.parent/agent-library/
# config/redaction-rules.yaml) resolves: /app/scripts/_redact_pii.py -> /app/agent-library/...
FROM python:3.11-slim

WORKDIR /app

# Only dependency the redactor needs beyond stdlib (see _redact_pii.py imports: yaml).
RUN pip install --no-cache-dir "pyyaml>=6"

# Hosted P2 redactor + its config, in the relative layout DEFAULT_CONFIG_PATH expects.
COPY scripts/_redact_pii.py /app/scripts/_redact_pii.py
COPY agent-library/config/redaction-rules.yaml /app/agent-library/config/redaction-rules.yaml

# The proxy itself.
COPY apps/backend-rag/sandbox/egress_proxy.py /app/egress_proxy.py

ENV REDACTOR_PATH=/app/scripts/_redact_pii.py \
    PROXY_PORT=8888 \
    PROXY_LOG_LEVEL=INFO

EXPOSE 8888
CMD ["python3", "/app/egress_proxy.py"]
