"""Shared bounds for the single-turn, fixed-input native canary.

The lease includes the admission reply, turn fence, completion fence and
checkpoint; thread/start, config/account discovery and turn/start use the cached
catalog for the unchanged binding. A changed binding refuses before inference.
The extra RPC allowance and margin cover bookkeeping and helper reaping. These
bounds qualify this consumer only, not arbitrary native sessions or renewal.
"""

HELPER_TIMEOUT_SECONDS = 20
RPC_TIMEOUT_SECONDS = 10
TURN_TIMEOUT_SECONDS = 60
POST_ADMISSION_HELPER_CALLS = 4
POST_ADMISSION_RPC_CALLS = 5
LEASE_MARGIN_SECONDS = 10
CANARY_LEASE_SECONDS = (
    POST_ADMISSION_HELPER_CALLS * HELPER_TIMEOUT_SECONDS
    + POST_ADMISSION_RPC_CALLS * RPC_TIMEOUT_SECONDS
    + TURN_TIMEOUT_SECONDS
    + LEASE_MARGIN_SECONDS
)
