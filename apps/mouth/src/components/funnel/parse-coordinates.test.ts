import { describe, it, expect } from "vitest";
import { parseCoordinates } from "./parse-coordinates";

describe("parseCoordinates", () => {
  describe("decimal format", () => {
    it("parses -8.65, 115.13 with comma", () => {
      expect(parseCoordinates("-8.65, 115.13")).toEqual({
        lat: -8.65,
        lng: 115.13,
      });
    });

    it("parses -8.65 115.13 with whitespace only", () => {
      expect(parseCoordinates("-8.65 115.13")).toEqual({
        lat: -8.65,
        lng: 115.13,
      });
    });

    it("parses with trailing whitespace", () => {
      expect(parseCoordinates("  -8.65, 115.13  ")).toEqual({
        lat: -8.65,
        lng: 115.13,
      });
    });

    it("parses positive lat/lng", () => {
      expect(parseCoordinates("40.7128, -74.0060")).toEqual({
        lat: 40.7128,
        lng: -74.006,
      });
    });
  });

  describe("DMS format (Google Maps paste)", () => {
    it("parses 8°39'17.4\"S 115°08'22.3\"E (Bali typical)", () => {
      const result = parseCoordinates("8°39'17.4\"S 115°08'22.3\"E");
      expect(result).not.toBeNull();
      expect(result!.lat).toBeCloseTo(-8.6548, 3);
      expect(result!.lng).toBeCloseTo(115.1395, 3);
    });

    it("parses N/E positive hemispheres", () => {
      const result = parseCoordinates("40°42'46.0\"N 74°00'21.6\"W");
      expect(result).not.toBeNull();
      expect(result!.lat).toBeCloseTo(40.7128, 3);
      expect(result!.lng).toBeCloseTo(-74.006, 3);
    });

    it("parses with Unicode prime/double-prime (′ ″)", () => {
      const result = parseCoordinates("8°39′17.4″S 115°08′22.3″E");
      expect(result).not.toBeNull();
      expect(result!.lat).toBeCloseTo(-8.6548, 3);
      expect(result!.lng).toBeCloseTo(115.1395, 3);
    });

    it("handles reversed order (lng first, lat second)", () => {
      const result = parseCoordinates("115°08'22.3\"E 8°39'17.4\"S");
      expect(result).not.toBeNull();
      expect(result!.lat).toBeCloseTo(-8.6548, 3);
      expect(result!.lng).toBeCloseTo(115.1395, 3);
    });

    it("parses DMS without seconds", () => {
      const result = parseCoordinates("8°39'S 115°08'E");
      expect(result).not.toBeNull();
      expect(result!.lat).toBeCloseTo(-8.65, 2);
      expect(result!.lng).toBeCloseTo(115.133, 2);
    });
  });

  describe("Google Maps URL", () => {
    it("parses ?q=lat,lng", () => {
      const result = parseCoordinates(
        "https://maps.google.com/?q=-8.65,115.13",
      );
      expect(result).toEqual({ lat: -8.65, lng: 115.13 });
    });

    it("parses /@lat,lng,zoom format", () => {
      const result = parseCoordinates(
        "https://www.google.com/maps/@-8.648,115.132,17z",
      );
      expect(result).toEqual({ lat: -8.648, lng: 115.132 });
    });
  });

  describe("rejects invalid input", () => {
    it("returns null for empty string", () => {
      expect(parseCoordinates("")).toBeNull();
    });

    it("returns null for pure garbage", () => {
      expect(parseCoordinates("hello world")).toBeNull();
    });

    it("returns null for one number only", () => {
      expect(parseCoordinates("-8.65")).toBeNull();
    });

    it("returns null for DMS with both N/S (no lng)", () => {
      expect(parseCoordinates("8°39'S 9°40'N")).toBeNull();
    });
  });
});
