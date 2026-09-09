const ALLOWED_EXTERNAL_PROTOCOLS = ["https:", "mailto:", "tel:"] as const;

export type AllowedExternalProtocol =
  (typeof ALLOWED_EXTERNAL_PROTOCOLS)[number];

declare const safeExternalHrefBrand: unique symbol;

export type SafeExternalHref = string & {
  readonly [safeExternalHrefBrand]: true;
};

declare const safeLocalHrefBrand: unique symbol;
export type SafeLocalHref = string & { readonly [safeLocalHrefBrand]: true };
export type SafeDestinationHref = SafeExternalHref | SafeLocalHref;

/** A local path has an implemented website/retained owner, not an implied host. */
export function toSafeDestinationHref(value: string): SafeDestinationHref {
  if (!value.startsWith("/")) return toSafeExternalHref(value);
  if (!/^\/[a-zA-Z0-9/_-]*$/.test(value) || value.includes("//")) {
    throw new TypeError("Local destinations must be canonical root-relative paths.");
  }
  return value as SafeLocalHref;
}

function hasAllowedProtocol(
  protocol: string,
): protocol is AllowedExternalProtocol {
  return ALLOWED_EXTERNAL_PROTOCOLS.some((allowed) => allowed === protocol);
}

export function toSafeExternalHref(value: string): SafeExternalHref {
  if (!value || value !== value.trim() || value.startsWith("//")) {
    throw new TypeError("External destinations must be absolute and trimmed.");
  }

  let destination: URL;
  try {
    destination = new URL(value);
  } catch {
    throw new TypeError("External destinations must be valid URLs.");
  }

  if (!hasAllowedProtocol(destination.protocol)) {
    throw new TypeError(
      `External destination protocol is not allowed: ${destination.protocol}`,
    );
  }

  if (destination.protocol === "https:") {
    if (!destination.hostname || destination.username || destination.password) {
      throw new TypeError(
        "HTTPS destinations require a hostname and cannot contain credentials.",
      );
    }
  }

  if (
    destination.protocol === "mailto:" &&
    !/^[^@/?#]+@[^@/?#]+$/.test(destination.pathname)
  ) {
    throw new TypeError("Mail destinations require one valid recipient.");
  }

  if (
    destination.protocol === "tel:" &&
    !/^\+[1-9]\d{7,14}$/.test(destination.pathname)
  ) {
    throw new TypeError("Telephone destinations require an E.164 number.");
  }

  return value as SafeExternalHref;
}
