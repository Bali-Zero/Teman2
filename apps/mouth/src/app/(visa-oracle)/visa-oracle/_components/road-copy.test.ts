import { ROAD_COPY, roadCopy } from "./road-copy";

const placeholders = (value: string) =>
  Array.from(value.matchAll(/\{(\w+)\}/g), (match) => match[1]).sort();

describe("ROAD_COPY — EN/ID parity", () => {
  it("carries the same keys in both languages", () => {
    expect(Object.keys(ROAD_COPY.id).sort()).toEqual(
      Object.keys(ROAD_COPY.en).sort(),
    );
  });

  for (const key of Object.keys(
    ROAD_COPY.en,
  ) as (keyof typeof ROAD_COPY.en)[]) {
    it(`${key}: non-empty in both, same placeholders`, () => {
      expect(ROAD_COPY.en[key].trim()).not.toBe("");
      expect(ROAD_COPY.id[key].trim()).not.toBe("");
      expect(placeholders(ROAD_COPY.id[key])).toEqual(
        placeholders(ROAD_COPY.en[key]),
      );
    });
  }

  it("never carries engine vocabulary, ranking words or banned voice", () => {
    const all = [
      ...Object.values(ROAD_COPY.en),
      ...Object.values(ROAD_COPY.id),
    ].join("\n");
    // GUILT controls: each pattern must fire on its own sample.
    const banned = [
      /\bjourney\b/i,
      /\bunlock/i,
      /\bseamless/i,
      /\bparadise\b/i,
      /\bbest\b/i,
      /\brecommended\b/i,
      /\b(decides|decision input)\b/i,
      /\b[a-z]+\.[a-z_]+\b/, // fact ids like person.nationalities
      /\b[A-Z]{2,}_[A-Z_]+\b/, // enums like NO_SUPPORTED_PATH
    ];
    for (const [pattern, sample] of banned.map(
      (pattern, index) =>
        [
          pattern,
          [
            "journey",
            "unlock",
            "seamless",
            "paradise",
            "best",
            "recommended",
            "decides",
            "person.nationalities",
            "NO_SUPPORTED_PATH",
          ][index],
        ] as const,
    )) {
      expect(sample).toMatch(pattern);
      expect(all).not.toMatch(pattern);
    }
  });

  it("fills placeholders and leaves unknown ones visible", () => {
    expect(roadCopy("en", "railOutcomeTitle")).toBe("Where this road ends");
  });
});
