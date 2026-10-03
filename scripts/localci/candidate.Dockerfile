# Candidate sandbox image for localci `pytest`/`trusted_pytest` checks (isolation "container").
# Built once on the runner host; the plan records the resulting image ID and a run refuses a retagged image:
#   docker build -t localci-candidate:1 - < scripts/localci/candidate.Dockerfile
# Nothing from the host is mounted into it: the runner streams the candidate tree in and copies the junit out.
FROM python:3.11-slim
RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends git >/dev/null \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir -q pytest==9.0.3 PyYAML==6.0.3 detect-secrets==1.5.0
