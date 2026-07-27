/**
 * E2E credentials — environment-only, no defaults, fail loud.
 *
 * These specs authenticate as a real Bali Zero account against a real login
 * form. Until 2026-07-27, the account email and its PIN were committed as `||`
 * fallbacks across 14 spec files in this repository — which is PUBLIC — and
 * several of those specs defaulted their base URL to production. A default
 * credential is not a convenience: it is a published credential that also
 * happens to work.
 *
 * The repository secrets `E2E_TEST_EMAIL` / `E2E_TEST_PIN` have existed since
 * 2026-04-11 and are already wired into the E2E workflow, so the supported path
 * was always available; the fallbacks were legacy convenience, nothing more.
 *
 * Everything here resolves LAZILY. Reading these at module scope would make a
 * missing variable explode on import for every spec in the suite, including the
 * ones that never authenticate.
 */

function requireEnv(name: string, hint: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `${name} is not set.\n\n` +
        `This spec authenticates against a real login form, so the credential ` +
        `has to come from the environment — there is deliberately no default.\n` +
        `${hint}\n\n` +
        `Locally:  export ${name}=...   (ask the owner; never commit it)\n` +
        `In CI:    already provided as a repository secret of the same name.`,
    );
  }
  return value;
}

/** Email of the E2E test account. Never defaulted. */
export function e2eEmail(): string {
  return requireEnv(
    "E2E_TEST_EMAIL",
    "It identifies which account the run signs in as.",
  );
}

/** PIN of the E2E test account. Never defaulted, never logged. */
export function e2ePin(): string {
  return requireEnv("E2E_TEST_PIN", "It is the account's login secret.");
}

// NOTE — deliberately NOT handled here: several of these specs default their
// base URL to production (`smoke.spec.ts`, `mission_simulation.spec.ts`). That
// is a real concern, but smoke.spec.ts is a production smoke test BY DESIGN, so
// re-pointing it at localhost would invert its purpose rather than secure it.
// Left as a separate decision. With the credential now env-only, none of these
// specs can reach a production login with a working secret by accident.
