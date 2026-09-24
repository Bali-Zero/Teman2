/**
 * The localStorage key the wizard hands its answers to the verdict screen
 * under, written just before the eligibility check is sent. Separate from the
 * wizard's own resume key (`bz.garuda_voa.wizard`), which the wizard deletes
 * on completion — the verdict's decline mirror used to read that one, and so
 * always found it gone.
 */
export const SUBMITTED_ANSWERS_KEY = "bz.garuda_voa.submitted";
