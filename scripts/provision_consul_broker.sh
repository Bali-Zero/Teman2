#!/bin/bash
# PRO-only, explicit provisioning. Default is a read-only plan.
# Reuses provision_zantara_codex.sh's separate-user/root-owned-code pattern;
# intentionally creates no daemon, scheduler, shared venv, or database grant.
set -euo pipefail
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
BASE=/usr/local/lib/nuzantara-consul
STATE=/var/db/nuzantara-consul
SERVICE=_nuz_consul
WRAPPER=/usr/local/libexec/nuzantara-consul-broker
MODE=--check
BUNDLE= EXPECTED= CONFIG= GRANT= GRANT_FILE=
die() { printf '%s\n' "$1" >&2; exit 1; }
verify_tree() {
    local root="$1" digest="$2" found expected_count
    [[ "$digest" =~ ^[a-f0-9]{64}$ ]] || die consul_release_id_invalid
    [ -f "$root/SHA256SUMS" ] && [ ! -L "$root" ] || die consul_release_missing
    [ "$(shasum -a 256 "$root/SHA256SUMS" | cut -d' ' -f1)" = "$digest" ] || die consul_release_manifest_digest
    [ -z "$(find "$root" -type l -print -quit)" ] || die consul_release_symlink
    [ -z "$(find "$root" ! -type d ! -type f -print -quit)" ] || die consul_release_special_file
    while IFS= read -r line; do
        [[ "$line" =~ ^[a-f0-9]{64}\ \ [A-Za-z0-9_./+-]+$ ]] || die consul_release_manifest_format
        item="${line:66}"
        case "/$item/" in //*|*/../*|*/./*) die consul_release_manifest_path ;; esac
    done < "$root/SHA256SUMS"
    [ -z "$(cut -c67- "$root/SHA256SUMS" | sort | uniq -d)" ] || die consul_release_duplicate_path
    found=$(find "$root" -type f ! -path "$root/SHA256SUMS" | wc -l | tr -d ' ')
    expected_count=$(wc -l < "$root/SHA256SUMS" | tr -d ' ')
    [ "$found" = "$expected_count" ] || die consul_release_unlisted_file
    (cd "$root" && shasum -a 256 -c SHA256SUMS >/dev/null 2>&1) || die consul_release_hash_mismatch
}
verify_installed_modes() {
    local unsafe
    unsafe=$(find "$1" \( -perm -4000 -o -perm -2000 -o -perm -0020 -o -perm -0002 \) -print -quit) || die consul_release_mode_check_failed
    [ -z "$unsafe" ] || die consul_release_unsafe_mode
}
prepare_release() {
    local source="$1" target="$2" digest="$3" staging
    # Copy metadata is untrusted. Keep the entire copy private until set-id bits
    # and writable ACLs/modes are removed, regardless of ditto/chown semantics.
    staging=$(mktemp -d "$BASE/releases/.install.XXXXXXXX")
    chmod 0700 "$staging"
    ditto "$source" "$staging/payload"
    verify_tree "$staging/payload" "$digest"
    chmod -R u-s,g-s "$staging/payload"
    chmod -RN "$staging/payload"
    xattr -cr "$staging/payload"
    chown -R root:wheel "$staging/payload"
    chmod -R go-w "$staging/payload"
    verify_installed_modes "$staging/payload"
    mv "$staging/payload" "$target"
    rmdir "$staging"
}
while [ "$#" -gt 0 ]; do
    case "$1" in
        --check|--plan|--apply|--rollback) MODE="$1"; shift ;;
        --bundle) BUNDLE="${2:?bundle required}"; shift 2 ;;
        --sha256) EXPECTED="${2:?reviewed digest required}"; shift 2 ;;
        --config) CONFIG="${2:?config file required}"; shift 2 ;;
        --grant) GRANT="${2:?grant UUID required}"; GRANT_FILE="${3:?grant file required}"; shift 3 ;;
        *) die consul_provision_argument_invalid ;;
    esac
done
if [ "$MODE" = --check ] || [ "$MODE" = --plan ]; then
    printf '%s\n' 'Plan: Pro only; new _nuz_consul identity; immutable release; fixed no-argument sudo target.'
    printf '%s\n' 'Prepare reviewed bundle + SHA256SUMS digest, service DB role/config, and preissued UUID grant.'
    printf 'host=%s uid=%s\n' "$(hostname -s)" "$(id -u)"
    if [ -n "$BUNDLE" ] || [ -n "$EXPECTED" ]; then
        verify_tree "$BUNDLE" "$EXPECTED"
        printf '%s\n' 'reviewed_bundle_hashes_verified; installation authorization remains separate'
    fi
    if [ -L "$BASE/current" ]; then printf 'binding=%s\n' "$(readlink "$BASE/current")"; fi
    exit 0
fi
[ "$(uname -s)" = Darwin ] && [ "$(hostname -s)" = Nuzantara ] || die consul_provision_pro_required
[ "$(id -u)" -eq 0 ] || die consul_provision_root_required
if [ "$MODE" = --apply ]; then
    [[ "$EXPECTED" =~ ^[a-f0-9]{64}$ ]] || die consul_reviewed_digest_required
    [ -d "$BUNDLE" ] && [ ! -L "$BUNDLE" ] || die consul_bundle_required
fi
umask 077
protected_directory() {
    local path="$1" mode
    [ -d "$path" ] && [ ! -L "$path" ] || die consul_provision_parent_missing
    [ "$(stat -f '%u' "$path")" = 0 ] || die consul_provision_parent_owner
    mode=$(stat -f '%OLp' "$path")
    (( (8#$mode & 8#022) == 0 )) || die consul_provision_parent_writable
    if /bin/ls -lde "$path" | grep -Eq '^[[:space:]]*[0-9]+:'; then die consul_provision_parent_acl; fi
}
# Shared ancestors must already exclude caller writes. Do not chmod shared trees.
for path in /usr/local /usr/local/lib /usr/local/libexec /var/db /private/var/db /private/etc/sudoers.d; do
    protected_directory "$path"
done
for path in "$BASE" "$BASE/releases" "$STATE" "$STATE/grants"; do
    if [ -e "$path" ] || [ -L "$path" ]; then protected_directory "$path"; fi
done
for binding in "$BASE/current" "$BASE/previous"; do
    if [ -e "$binding" ] || [ -L "$binding" ]; then
        [ -L "$binding" ] || die consul_binding_not_symlink
        [[ "$(readlink "$binding")" =~ ^releases/[a-f0-9]{64}$ ]] || die consul_binding_invalid
    fi
done
install -d -o root -g wheel -m 0755 "$BASE" "$BASE/releases"
install -d -o root -g wheel -m 0711 "$STATE"
mkdir "$STATE/provision.lock" 2>/dev/null || die consul_provision_busy
trap 'rmdir "$STATE/provision.lock"' EXIT
bind_release() {
    local target="$1"
    [ ! -e "$BASE/current" ] || [ -L "$BASE/current" ] || die consul_binding_not_symlink
    ln -s "$target" "$BASE/.current.$$"
    mv -fh "$BASE/.current.$$" "$BASE/current"
}
if [ "$MODE" = --rollback ]; then
    [ -L "$BASE/previous" ] || die consul_prior_binding_missing
    prior=$(readlink "$BASE/previous")
    [[ "$prior" =~ ^releases/[a-f0-9]{64}$ ]] || die consul_prior_binding_invalid
    verify_installed_modes "$BASE/$prior"
    verify_tree "$BASE/$prior" "${prior#releases/}"
    env -i HOME=/var/empty PATH=/usr/bin:/bin "$BASE/$prior/python/bin/python3" -I -S -B "$BASE/$prior/verify.py" --immutable
    bind_release "$prior"
    printf '%s\n' 'consul_prior_release_bound; grants/config/DB unchanged; fresh authorization still required'
    exit 0
fi
RELEASE="$BASE/releases/$EXPECTED"
if [ ! -e "$RELEASE" ]; then
    prepare_release "$BUNDLE" "$RELEASE" "$EXPECTED"
fi
verify_installed_modes "$RELEASE"
verify_tree "$RELEASE" "$EXPECTED"
env -i HOME=/var/empty PATH=/usr/bin:/bin "$RELEASE/python/bin/python3" -I -S -B "$RELEASE/verify.py" --immutable
if ! id "$SERVICE" >/dev/null 2>&1; then
    if dscl . -read "/Groups/$SERVICE" >/dev/null 2>&1; then die consul_partial_identity_requires_review; fi
    next_uid=$(dscl . -list /Users UniqueID | awk 'BEGIN {m=500} $2>m {m=$2} END {print m+1}')
    next_gid=$(dscl . -list /Groups PrimaryGroupID | awk 'BEGIN {m=500} $2>m {m=$2} END {print m+1}')
    dscl . -create "/Groups/$SERVICE" PrimaryGroupID "$next_gid"
    dscl . -create "/Users/$SERVICE" UniqueID "$next_uid"
    dscl . -create "/Users/$SERVICE" PrimaryGroupID "$next_gid"
    dscl . -create "/Users/$SERVICE" UserShell /usr/bin/false
    dscl . -create "/Users/$SERVICE" NFSHomeDirectory /var/empty
    dscl . -create "/Users/$SERVICE" IsHidden 1
fi
[ "$(dscl . -read "/Users/$SERVICE" UserShell)" = 'UserShell: /usr/bin/false' ] || die consul_existing_identity_unqualified
[ "$(dscl . -read "/Users/$SERVICE" NFSHomeDirectory)" = 'NFSHomeDirectory: /var/empty' ] || die consul_existing_identity_unqualified
[ "$(id -gn "$SERVICE")" = "$SERVICE" ] || die consul_existing_group_unqualified
if id -Gn "$SERVICE" | tr ' ' '\n' | grep -Eq '^(admin|wheel)$'; then die consul_privileged_identity_forbidden; fi
[ "$(id -u "$SERVICE")" != "$(id -u nuzantara)" ] || die consul_identity_not_separate
[ "$(id -u "$SERVICE")" -gt 500 ] || die consul_system_identity_forbidden
service_uid=$(id -u "$SERVICE")
[ "$(dscl . -list /Users UniqueID | awk -v target="$service_uid" '$2==target {n++} END {print n+0}')" = 1 ] || die consul_duplicate_identity_forbidden
if id zantara-codex >/dev/null 2>&1; then
    [ "$(id -u "$SERVICE")" != "$(id -u zantara-codex)" ] || die consul_existing_broker_identity_forbidden
fi
install -d -o root -g "$SERVICE" -m 0750 "$STATE/grants"
if [ -n "$CONFIG" ]; then
    [ ! -e "$STATE/config.json" ] || die consul_config_already_exists
    install -o "$SERVICE" -g "$SERVICE" -m 0600 "$CONFIG" "$STATE/config.json"
    chmod -N "$STATE/config.json"
    xattr -c "$STATE/config.json"
fi
[ -f "$STATE/config.json" ] || die consul_service_config_required
[ ! -L "$STATE/config.json" ] && [ "$(stat -f '%u' "$STATE/config.json")" = "$(id -u "$SERVICE")" ] && [ "$(stat -f '%OLp' "$STATE/config.json")" = 600 ] || die consul_config_permissions_invalid
if /bin/ls -lde "$STATE/config.json" | grep -Eq '^[[:space:]]*[0-9]+:'; then die consul_config_acl_forbidden; fi
if [ -n "$GRANT" ]; then
    [[ "$GRANT" =~ ^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$ ]] || die consul_grant_uuid_required
    [ ! -e "$STATE/grants/$GRANT.json" ] || die consul_grant_already_exists
    install -o root -g "$SERVICE" -m 0440 "$GRANT_FILE" "$STATE/grants/$GRANT.json"
    chmod -N "$STATE/grants/$GRANT.json"
    xattr -c "$STATE/grants/$GRANT.json"
fi
visudo -cf "$RELEASE/control/sudoers" >/dev/null || die consul_sudoers_invalid
[ ! -L "$WRAPPER" ] && [ ! -L /etc/sudoers.d/nuzantara-consul ] || die consul_target_symlink_forbidden
install -o root -g wheel -m 0755 "$RELEASE/control/wrapper.sh" "$WRAPPER"
install -o root -g wheel -m 0440 "$RELEASE/control/sudoers" /etc/sudoers.d/nuzantara-consul
chmod -N "$WRAPPER" /etc/sudoers.d/nuzantara-consul
xattr -c "$WRAPPER" /etc/sudoers.d/nuzantara-consul
if [ -L "$BASE/current" ]; then
    old=$(readlink "$BASE/current")
    [[ "$old" =~ ^releases/[a-f0-9]{64}$ ]] || die consul_current_binding_invalid
    ln -s "$old" "$BASE/.previous.$$"
    mv -fh "$BASE/.previous.$$" "$BASE/previous"
fi
bind_release "releases/$EXPECTED"
printf '%s\n' 'consul_release_bound; no daemon started; no database changes performed'
