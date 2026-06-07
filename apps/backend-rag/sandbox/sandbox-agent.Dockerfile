# sandbox-agent image — P3 Tier-1, where the LLM agent runs (FASE-1 SOTA meta-dev-loop).
# Spec: research/operations/specs/P3-test-prod-sandbox.md §3.1.
#
# This container sits ONLY on sandbox_internal (internal:true). It physically has
# no route outside; all outbound is forced through egress-proxy via HTTP(S)_PROXY
# (set in docker-compose.sandbox.yml). The confinement is the Docker network
# topology — NOT iptables-in-the-container — so it is not bypassable by root here.
#
# Minimal: httpx for the G1/G1-DLP gate probes; the agent's real toolchain is
# layered on top in later iterations. Build context = repo root (../..).
FROM python:3.11-slim

WORKDIR /work

# httpx for the gate probes (test_*_domain). pip/git for the agent's read-only pulls.
RUN pip install --no-cache-dir "httpx>=0.27" \
    && apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# No write tokens are ever baked in (spec §3.2 P0 #3): the agent can pull, not push.
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Kept alive by the compose `command: ["sleep", "infinity"]` for `docker compose exec`.
CMD ["sleep", "infinity"]
