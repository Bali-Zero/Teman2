#!/bin/sh
# Fixed sudo target. No caller-selected command, path, config, or environment.
set -eu
[ "$#" -eq 0 ] || { printf '%s\n' 'consul_broker_arguments_forbidden' >&2; exit 64; }
[ "$(/usr/bin/id -un)" = '_nuz_consul' ] || { printf '%s\n' 'consul_broker_identity_required' >&2; exit 77; }
cd /
exec /usr/bin/env -i HOME=/var/empty PATH=/usr/bin:/bin LANG=C.UTF-8 \
    /usr/local/lib/nuzantara-consul/current/python/bin/python3 -I -S -B \
    /usr/local/lib/nuzantara-consul/current/entry.py
