import { describe, it, expect } from "vitest";
import {
  parsePrimeUrl,
  serializePrimeUrl,
  type PrimeUrlState,
} from "../usePrimeUrlState";

describe("parsePrimeUrl", () => {
  it("parses a full-valid querystring", () => {
    const out = parsePrimeUrl(
      new URLSearchParams(
        "lat=-8.65&lng=115.21&zoom=15&layers=zoneColors,kkop&compareA=Z1&compareB=Z2",
      ),
    );
    expect(out).toEqual({
      lat: -8.65,
      lng: 115.21,
      zoom: 15,
      layers: ["zoneColors", "kkop"],
      compareA: "Z1",
      compareB: "Z2",
    });
  });

  it("drops out-of-bound lat silently", () => {
    const out = parsePrimeUrl(new URLSearchParams("lat=40&lng=115.21&zoom=10"));
    expect(out.lat).toBeUndefined();
    // Zod safeParse rejects the whole object when one field fails → lng also dropped
    expect(out.lng).toBeUndefined();
  });

  it("keeps valid fields when other fields are missing", () => {
    const out = parsePrimeUrl(new URLSearchParams("lat=-8.65&zoom=10"));
    expect(out.lat).toBe(-8.65);
    expect(out.zoom).toBe(10);
  });

  it("drops unknown layer names silently", () => {
    const out = parsePrimeUrl(
      new URLSearchParams("layers=zoneColors,bogus,kkop"),
    );
    expect(out.layers).toEqual(["zoneColors", "kkop"]);
  });

  it("returns empty object for empty params", () => {
    expect(parsePrimeUrl(new URLSearchParams(""))).toEqual({});
  });
});

describe("serializePrimeUrl", () => {
  it("omits undefined fields", () => {
    const s = serializePrimeUrl({ lat: -8.65, lng: 115.21 });
    expect(s).toBe("lat=-8.65&lng=115.21");
  });

  it("joins layers as csv", () => {
    const s = serializePrimeUrl({ layers: ["zoneColors", "kkop"] });
    expect(s).toBe("layers=zoneColors%2Ckkop");
  });

  it("round-trips a full state", () => {
    const state: PrimeUrlState = {
      lat: -8.65,
      lng: 115.21,
      zoom: 15,
      layers: ["zoneColors", "kkop"],
      compareA: "Z1",
      compareB: "Z2",
    };
    const s = serializePrimeUrl(state);
    expect(parsePrimeUrl(new URLSearchParams(s))).toEqual(state);
  });
});
