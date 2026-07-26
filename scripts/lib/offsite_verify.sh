#!/bin/bash
# offsite_verify.sh — ask the REMOTE whether the object is actually there.
#
# Why this exists (2026-07-27, backup audit). fly-pg-backup.sh judged its own success
# by reaching the end of the script, never by the artifact:
#
#   * `aws s3 cp ... 2>/dev/null` — stderr discarded, exit code never read — was followed
#     unconditionally by `log "Uploaded to Tigris: ..."`. That line was a CLAIM, not an
#     observation.
#   * when the credentials preflight failed, the script logged WARNs, skipped the upload
#     entirely, and still ended with `Backup complete ✅` and exit 0. Since the only alarm
#     in the chain fires on a non-zero exit (cron-wrapper.sh), a Tigris credential problem
#     produced a GREEN night with no off-site copy at all — and the local copy is pruned
#     after KEEP_LOCAL=7 days.
#
# Measured consequence: 2026-07-15 has no object in the bucket for either nightly run,
# while the 03:20 state file records {"status":"ok","exit_code":0} and the 03:00 log simply
# stops mid-upload. Two runs, no declared failure, no backup.
#
# So the rule this file enforces: a backup that is not off-site is not a backup, and the
# only thing allowed to say the object exists is the remote listing.
#
# Deliberately NOT a substring check — `foo.sql.gz` must not be satisfied by
# `foo.sql.gz.partial` or by `other-foo.sql.gz` (superscar #3: match the entity, not the
# shape). The listing is anchored on the exact basename in the name column.

# verify_offsite_object <bucket> <endpoint> <key_basename>
#   rc 0 -> the remote listing shows exactly this object
#   rc 1 -> it does not, or the listing itself could not be trusted
# Reads AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from the environment, like the caller.
verify_offsite_object() {
    local bucket="$1" endpoint="$2" key="$3"
    local prefix="${4:-postgres}"
    local attempt out rc had_e=0
    local nap="${OFFSITE_VERIFY_RETRY_SLEEP:-3}"

    # Save errexit and restore it exactly as found. A bare `set -e` here would switch
    # errexit ON in any caller that did not have it — which is not this function's call
    # to make, and which killed the corpus on its first guilt case.
    case $- in *e*) had_e=1 ;; esac

    if [ -z "$bucket" ] || [ -z "$endpoint" ] || [ -z "$key" ]; then
        echo "verify_offsite_object: missing argument (bucket/endpoint/key)" >&2
        return 1
    fi
    if ! command -v aws >/dev/null 2>&1; then
        echo "verify_offsite_object: aws CLI absent — cannot verify, so cannot claim success" >&2
        return 1
    fi

    # Two attempts: a listing taken the instant after a write is the one place a
    # transient could legitimately lie. Anything beyond that is a real absence.
    for attempt in 1 2; do
        set +e
        out=$(aws s3 ls "s3://$bucket/$prefix/" --endpoint-url "$endpoint" --region auto 2>&1)
        rc=$?
        [ $had_e -eq 1 ] && set -e
        if [ $rc -ne 0 ]; then
            echo "verify_offsite_object: listing failed rc=$rc: $(echo "$out" | head -1)" >&2
            if [ $attempt -eq 2 ]; then return 1; fi
            [ "$nap" != "0" ] && sleep "$nap"
            continue
        fi
        # `aws s3 ls` prints: <date> <time> <size> <name>. Judge the NAME column only,
        # and demand the whole field — never a substring of a longer name.
        if printf '%s\n' "$out" | awk -v want="$key" '{ if ($NF == want) found=1 } END { exit found ? 0 : 1 }'; then
            return 0
        fi
        if [ $attempt -eq 2 ]; then break; fi
        [ "$nap" != "0" ] && sleep "$nap"
    done

    echo "verify_offsite_object: '$key' is NOT in s3://$bucket/$prefix/" >&2
    return 1
}
