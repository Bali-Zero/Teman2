# The exact string held in the Vercel project's `commandForIgnoringBuildStep`.
#
# It lives here for one reason: on 2026-07-29 that field held a bare invocation of
# scripts/ci/vercel_should_build.sh, the script was not on main yet, bash exited 127, and
# 9 deployments went to ERROR in half an hour. The field is dashboard/API state — nothing in
# the repo described it, so nothing could review it and no test could run against it.
#
# Vercel's contract for this command is: exit 0 = skip the build, exit 1 = build,
# ANY OTHER EXIT CODE = the deployment fails. So the command must never let an unexpected
# status escape: a missing file, a syntax error, or a signal all have to become exit 1.
# That is the whole job of the wrapper below, and scripts/tests/test_vercel_should_build.sh
# executes this exact line against those three cases.
#
# Constraint: the API rejects the field over 256 characters (`invalid_command_for_ignoring_build_step`).
# The single non-comment line below is the payload; the test asserts both its length and its
# behaviour. Keep it to one line — the extractor reads exactly one.
#
# To apply after changing it:
#   PATCH https://api.vercel.com/v9/projects/<id>?teamId=<team>  {"commandForIgnoringBuildStep": "<line>"}
# and only once scripts/ci/vercel_should_build.sh is on the production branch — that ordering
# is the part that was skipped.

S="$(git rev-parse --show-toplevel)/scripts/ci/vercel_should_build.sh"; [ -f "$S" ] || exit 1; bash "$S"; [ $? = 0 ] && exit 0 || exit 1
