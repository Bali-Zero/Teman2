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
        <h3 className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-2">
          Practices
        </h3>
        <ul className="space-y-1">
          <li>
            <button
              className={`w-full text-left text-sm px-2 py-1 rounded ${
                !practiceFilter ? "bg-white/10" : "hover:bg-white/5"
              }`}
              onClick={() => onPracticeChange(null)}
            >
              All <span className="text-[#c9a96e]/40">({files.length})</span>
            </button>
          </li>
          {practices.map(([id, label]) => (
            <li key={id}>
              <button
                className={`w-full text-left text-sm px-2 py-1 rounded ${
                  practiceFilter === id ? "bg-white/10" : "hover:bg-white/5"
                }`}
                onClick={() => onPracticeChange(id)}
              >
                {label}{" "}
                <span className="text-[#c9a96e]/40">({countPractice(id)})</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      {types.length > 0 && (
        <section>
          <h3 className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 mb-2">
            Types
          </h3>
          <ul className="space-y-1">
            {types.map((t) => (
              <li key={t}>
                <button
                  className={`w-full text-left text-sm px-2 py-1 rounded ${
                    typeFilter === t ? "bg-white/10" : "hover:bg-white/5"
                  }`}
                  onClick={() => onTypeChange(typeFilter === t ? null : t)}
                >
                  {t}{" "}
                  <span className="text-[#c9a96e]/40">({countType(t)})</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </aside>
  );
}
