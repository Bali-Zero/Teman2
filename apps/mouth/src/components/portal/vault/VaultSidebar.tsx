"use client";
import type { VaultFile } from "@/lib/schemas/vault";

interface Props {
  files: VaultFile[];
  practiceFilter: string | null;
  typeFilter: string | null;
  onPracticeChange: (id: string | null) => void;
  onTypeChange: (t: string | null) => void;
}

export function VaultSidebar({
  files,
  practiceFilter,
  typeFilter,
  onPracticeChange,
  onTypeChange,
}: Props) {
  const practices = Array.from(
    new Map(
      files
        .filter((f) => f.practice_id != null)
        .map((f) => [
          String(f.practice_id),
          f.practice_name ?? String(f.practice_id),
        ]),
    ).entries(),
  );
  const types = Array.from(new Set(files.map((f) => f.type))).filter(Boolean);

  const countPractice = (id: string) =>
    files.filter((f) => String(f.practice_id) === id).length;
  const countType = (t: string) => files.filter((f) => f.type === t).length;

  return (
    <aside className="space-y-6" aria-label="Vault filters">
      <section>
        <h3
          className="text-xs uppercase tracking-[2px] mb-2"
          style={{ color: "var(--bz-copper-text, var(--tx-secondary))" }}
        >
          Practices
        </h3>
        <ul className="space-y-1">
          <li>
            <button
              className={`w-full text-left text-sm px-2 py-1 rounded ${
                !practiceFilter
                  ? "bg-[var(--glass-rim)]"
                  : "hover:bg-[var(--bz-card-hover)]"
              }`}
              onClick={() => onPracticeChange(null)}
            >
              All{" "}
              <span
                style={{ color: "var(--text-tertiary, var(--tx-tertiary))" }}
              >
                ({files.length})
              </span>
            </button>
          </li>
          {practices.map(([id, label]) => (
            <li key={id}>
              <button
                className={`w-full text-left text-sm px-2 py-1 rounded ${
                  practiceFilter === id
                    ? "bg-[var(--glass-rim)]"
                    : "hover:bg-[var(--bz-card-hover)]"
                }`}
                onClick={() => onPracticeChange(id)}
              >
                {label}{" "}
                <span
                  style={{ color: "var(--text-tertiary, var(--tx-tertiary))" }}
                >
                  ({countPractice(id)})
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {types.length > 0 && (
        <section>
          <h3
            className="text-xs uppercase tracking-[2px] mb-2"
            style={{ color: "var(--bz-copper-text, var(--tx-secondary))" }}
          >
            Types
          </h3>
          <ul className="space-y-1">
            {types.map((t) => (
              <li key={t}>
                <button
                  className={`w-full text-left text-sm px-2 py-1 rounded ${
                    typeFilter === t
                      ? "bg-[var(--glass-rim)]"
                      : "hover:bg-[var(--bz-card-hover)]"
                  }`}
                  onClick={() => onTypeChange(typeFilter === t ? null : t)}
                >
                  {t}{" "}
                  <span
                    style={{
                      color: "var(--text-tertiary, var(--tx-tertiary))",
                    }}
                  >
                    ({countType(t)})
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}
