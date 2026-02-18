interface Section {
  code: string;
  name: string;
}

interface Props {
  sections?: Section[];
}

export function KBLISectorGrid({ sections }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {sections?.map((section) => (
        <div
          key={section.code}
          className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 text-sm"
        >
          {section.name}
        </div>
      )) || <div>No sections</div>}
    </div>
  );
}
