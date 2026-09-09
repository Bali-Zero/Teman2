export const VISA_ORACLE_MAX_RESPONSE_BYTES = 256 * 1_024;
export const VISA_ORACLE_MAX_JSON_DEPTH = 64;

const DANGEROUS_KEYS = new Set(["__proto__", "constructor", "prototype"]);
const HEX4 = /^[a-fA-F0-9]{4}$/;

export class StrictJsonError extends Error {
  constructor(
    public readonly code:
      | "INVALID_JSON"
      | "DUPLICATE_KEY"
      | "DANGEROUS_KEY"
      | "MAX_DEPTH"
      | "RESPONSE_TOO_LARGE",
  ) {
    super(code);
    this.name = "StrictJsonError";
  }
}

class JsonScanner {
  private index = 0;

  constructor(private readonly source: string) {}

  scan(): void {
    this.skipWhitespace();
    this.scanValue(0);
    this.skipWhitespace();
    if (this.index !== this.source.length) this.invalid();
  }

  private current(): string | undefined {
    return this.source[this.index];
  }

  private skipWhitespace(): void {
    while (/\s/.test(this.current() ?? "") && this.index < this.source.length) {
      this.index += 1;
    }
  }

  private scanValue(depth: number): void {
    this.skipWhitespace();
    const token = this.current();
    if (token === "{") {
      if (depth >= VISA_ORACLE_MAX_JSON_DEPTH) {
        throw new StrictJsonError("MAX_DEPTH");
      }
      this.scanObject(depth + 1);
      return;
    }
    if (token === "[") {
      if (depth >= VISA_ORACLE_MAX_JSON_DEPTH) {
        throw new StrictJsonError("MAX_DEPTH");
      }
      this.scanArray(depth + 1);
      return;
    }
    if (token === '"') {
      this.scanString();
      return;
    }
    this.scanPrimitive();
  }

  private scanObject(depth: number): void {
    this.index += 1;
    this.skipWhitespace();
    if (this.current() === "}") {
      this.index += 1;
      return;
    }

    const keys = new Set<string>();
    while (this.index < this.source.length) {
      this.skipWhitespace();
      if (this.current() !== '"') this.invalid();
      const key = this.scanString();
      if (DANGEROUS_KEYS.has(key)) {
        throw new StrictJsonError("DANGEROUS_KEY");
      }
      if (keys.has(key)) throw new StrictJsonError("DUPLICATE_KEY");
      keys.add(key);

      this.skipWhitespace();
      if (this.current() !== ":") this.invalid();
      this.index += 1;
      this.scanValue(depth);
      this.skipWhitespace();

      if (this.current() === "}") {
        this.index += 1;
        return;
      }
      if (this.current() !== ",") this.invalid();
      this.index += 1;
    }
    this.invalid();
  }

  private scanArray(depth: number): void {
    this.index += 1;
    this.skipWhitespace();
    if (this.current() === "]") {
      this.index += 1;
      return;
    }

    while (this.index < this.source.length) {
      this.scanValue(depth);
      this.skipWhitespace();
      if (this.current() === "]") {
        this.index += 1;
        return;
      }
      if (this.current() !== ",") this.invalid();
      this.index += 1;
    }
    this.invalid();
  }

  private scanString(): string {
    const start = this.index;
    this.index += 1;

    while (this.index < this.source.length) {
      const character = this.source[this.index];
      if (character === '"') {
        this.index += 1;
        try {
          return JSON.parse(this.source.slice(start, this.index)) as string;
        } catch {
          this.invalid();
        }
      }
      if (character === "\\") {
        const escape = this.source[this.index + 1];
        if (escape === "u") {
          if (!HEX4.test(this.source.slice(this.index + 2, this.index + 6))) {
            this.invalid();
          }
          this.index += 6;
          continue;
        }
        if (!['"', "\\", "/", "b", "f", "n", "r", "t"].includes(escape)) {
          this.invalid();
        }
        this.index += 2;
        continue;
      }
      if (character.charCodeAt(0) < 0x20) this.invalid();
      this.index += 1;
    }
    this.invalid();
  }

  private scanPrimitive(): void {
    const start = this.index;
    while (
      this.index < this.source.length &&
      !/[\s,\]}]/.test(this.source[this.index])
    ) {
      this.index += 1;
    }
    if (start === this.index) this.invalid();
    const token = this.source.slice(start, this.index);
    try {
      const parsed = JSON.parse(token) as unknown;
      if (typeof parsed === "object" && parsed !== null) this.invalid();
    } catch {
      this.invalid();
    }
  }

  private invalid(): never {
    throw new StrictJsonError("INVALID_JSON");
  }
}

/** Parse JSON only after rejecting duplicate/prototype keys and oversized bodies. */
export function parseStrictJson(
  source: string,
  maxBytes = VISA_ORACLE_MAX_RESPONSE_BYTES,
): unknown {
  if (new TextEncoder().encode(source).byteLength > maxBytes) {
    throw new StrictJsonError("RESPONSE_TOO_LARGE");
  }
  new JsonScanner(source).scan();
  try {
    return JSON.parse(source) as unknown;
  } catch {
    throw new StrictJsonError("INVALID_JSON");
  }
}
