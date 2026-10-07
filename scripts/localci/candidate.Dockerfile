# Candidate sandbox image for localci `pytest`/`trusted_pytest`/`contained_steps` checks (isolation "container").
# Built once on the runner host; the plan records the resulting image ID and a run refuses a retagged image:
#   docker build -t localci-candidate:1 - < scripts/localci/candidate.Dockerfile
# Nothing from the host is mounted into it: the runner streams the candidate tree in and copies the junit out.
# What ubuntu-latest gives the contained contexts' jobs, offline. The base IS ubuntu 24.04, so the CLI tools the corpora call
# (jq, curl, crontab, shellcheck, tmux, zsh, ...) are the hosted runner's versions, not another distribution's. Python 3.12
# (the organ/guard/Merah Putih setup-python pin) is the default, also at /usr/bin/python3 where wrappers under test call it;
# 3.11 sits beside it for the jobs that pin 3.11 (antidotes: the runner puts it first on PATH, as setup-python does).
# A contained job's steps run in a BARE venv of that interpreter, as setup-python's is: every package a step `pip install`s comes
# offline from /opt/wheels (PIP_FIND_LINKS), so a step sees only what earlier steps installed. The interpreters themselves keep
# pytest/PyYAML for the older `pytest`/`trusted_pytest` kinds.
# The sandbox user (65534) gets the hosted runner user's passwd shape: name runner, HOME /home/runner, login shell bash.
# no-new-privileges strips crontab's setgid: the spool dir is made traversable so `crontab -l` answers "no crontab", as hosted.
ARG PY312=3.12.15
ARG PY311=3.11.17
FROM python:${PY311}-slim-bookworm AS py311
FROM python:${PY312}-slim-bookworm AS py312
FROM ubuntu:24.04
ARG PY312
ARG PY311
COPY --from=py312 /usr/local /usr/local
COPY --from=py311 /usr/local /opt/py311
ENV PYTHON_VERSION=${PY312} LOCALCI_PYTHONS="${PY311}=/opt/py311/bin" LANG=C.UTF-8
RUN apt-get update -qq \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends ca-certificates tzdata libssl3t64 libsqlite3-0 \
      libffi8 libbz2-1.0 liblzma5 libreadline8t64 libncursesw6 zlib1g libuuid1 libgdbm6t64 libgdbm-compat4t64 libexpat1 libnsl2 \
      libtirpc3t64 git zsh tmux locales procps curl jq shellcheck sqlite3 xxd lsof netcat-openbsd rsync zip unzip uuid-runtime \
      expect openssh-client file bc cron >/dev/null \
 && locale-gen it_IT.UTF-8 en_US.UTF-8 >/dev/null \
 && chmod o+x /var/spool/cron/crontabs \
 && rm -rf /var/lib/apt/lists/* \
 && test ! -e /usr/bin/python3 && ln -s /usr/local/bin/python3 /usr/bin/python3 \
 && install -d -o 65534 -g 65534 -m 0755 /home/runner && usermod -l runner -d /home/runner -s /bin/bash nobody \
 && test "$(python3 -c 'import platform; print(platform.python_version())')" = "$PYTHON_VERSION" \
 && test "$(/opt/py311/bin/python3.11 -c 'import platform; print(platform.python_version())')" = "$PY311" \
 && for py in /usr/local/bin/python3 /opt/py311/bin/python3.11; do \
      "$py" -m pip install --no-cache-dir -q --disable-pip-version-check pytest==9.0.3 PyYAML==6.0.3 || exit 1; \
      "$py" -m pip download --no-cache-dir -q --disable-pip-version-check -d /opt/wheels pytest PyYAML==6.0.3 pytest-xdist==3.8.0 \
        httpx==0.28.1 fastapi asyncpg ruff detect-secrets || exit 1; \
    done \
 && sed -i '1s|^#!/usr/local/bin/python3.11$|#!/opt/py311/bin/python3.11|' $(grep -l '^#!/usr/local/bin/python3.11$' /opt/py311/bin/*) \
 && ! grep -l '^#!/usr/local/bin/python3' /opt/py311/bin/* \
 && /opt/py311/bin/pip --version >/dev/null \
 && for py in python3 /opt/py311/bin/python3.11; do "$py" -c "import ssl, sqlite3, ctypes, lzma, bz2, readline, uuid, yaml, pytest" || exit 1; \
      rm -rf /tmp/v && "$py" -m venv /tmp/v && PIP_NO_INDEX=1 PIP_FIND_LINKS=/opt/wheels /tmp/v/bin/pip install -q pytest pytest-xdist==3.8.0 \
        PyYAML==6.0.3 httpx==0.28.1 fastapi asyncpg ruff detect-secrets && /tmp/v/bin/python -c "import xdist, httpx, fastapi, asyncpg" || exit 1; \
    done && rm -rf /tmp/v
