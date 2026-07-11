import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";
import { getCode } from "@/lib/kbli-data";
import {
  getSectionVisual,
  codeFingerprint,
  sectionGradient,
  type FingerprintBar,
} from "@/lib/kbli-cover-design";

/**
 * Dynamic KBLI Cover Image Generator
 *
 * Endpoint: /api/og/kbli/[code]
 * Query params:
 * - t: title override (defaults to the code's English title, falling back
 *   to the Indonesian title when no real English title exists)
 *
 * Example: /api/og/kbli/55203
 *
 * Returns a 1200x630 deterministic editorial cover: section gradient +
 * per-code fingerprint motif + status chip. No external requests, no
 * committed rasters — every pixel is derived at request time from
 * kbli-cover-design.ts (design DNA) + the KBLI dataset (kbli-data.ts).
 */

export const runtime = "nodejs";

const WIDTH = 1200;
const HEIGHT = 630;

function statusChip(kbli: NonNullable<ReturnType<typeof getCode>>): {
  label: string;
  color: string;
} {
  if (kbli.baliL4?.blocked) {
    return { label: "BALI: BLOCKED", color: "#e0645a" };
  }
  switch (kbli.pma.status) {
    case "open":
      return { label: "OPEN", color: "#5aab6e" };
    case "restricted":
      return { label: "RESTRICTED", color: "#c9a227" };
    case "closed":
      return { label: "CLOSED", color: "#e0645a" };
    default:
      return { label: "OPEN", color: "#5aab6e" };
  }
}

/**
 * One fingerprint lane: a chart-like bar whose height encodes one digit of
 * the code, with the digit itself as a small mono label under the baseline.
 * The cover literally charts its own code — a Bloomberg-graphic gesture, not
 * decoration.
 */
function FingerprintBarEl({
  bar,
  accent,
  maxHeight,
}: {
  bar: FingerprintBar;
  accent: string;
  maxHeight: number;
}) {
  // digit 0 still gets a visible stub; 9 nearly fills the zone
  const height = Math.round(maxHeight * (0.14 + 0.86 * (bar.digit / 9)));
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "center",
        height: "100%",
        flexGrow: 1,
      }}
    >
      <div
        style={{
          width: "34px",
          height: `${height}px`,
          borderRadius: "8px 8px 0 0",
          background: accent,
          opacity: 0.34 + bar.digit * 0.05,
          display: "flex",
        }}
      />
    </div>
  );
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ code: string }> },
) {
  const { code } = await params;
  const kbli = getCode(code);

  if (!kbli) {
    return new Response("KBLI code not found", { status: 404 });
  }

  const { searchParams } = new URL(request.url);
  const titleOverride = searchParams.get("t");
  const title =
    titleOverride ||
    (kbli.titleEnIsReal ? kbli.titleEn : kbli.titleId) ||
    kbli.titleId;

  const visual = getSectionVisual(kbli.section);
  const fp = codeFingerprint(kbli.code);
  const chip = statusChip(kbli);

  const fingerprintZoneWidth = WIDTH / 3;
  const laneWidth = fingerprintZoneWidth / Math.max(fp.bars.length, 1);
  const fingerprintMaxHeight = 340;

  return new ImageResponse(
    (
      <div
        style={{
          width: `${WIDTH}px`,
          height: `${HEIGHT}px`,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: sectionGradient(visual),
          fontFamily: "system-ui, sans-serif",
          position: "relative",
          padding: "64px",
        }}
      >
        {/* Fingerprint motif — the code charted as five bars on a baseline,
            anchored to the right third above the footer. */}
        <div
          style={{
            position: "absolute",
            right: "64px",
            bottom: "128px",
            width: `${fingerprintZoneWidth}px`,
            height: `${fingerprintMaxHeight}px`,
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* bars on the baseline */}
          <div
            style={{
              display: "flex",
              alignItems: "flex-end",
              height: `${fingerprintMaxHeight - 44}px`,
              width: "100%",
              borderBottom: "2px solid rgba(255,255,255,0.22)",
            }}
          >
            {fp.bars.map((bar) => (
              <FingerprintBarEl
                key={bar.digitIndex}
                bar={bar}
                accent={visual.accent}
                maxHeight={fingerprintMaxHeight - 52}
              />
            ))}
          </div>
          {/* the digits under their bars — the cover charts its own code */}
          <div
            style={{
              display: "flex",
              width: "100%",
              marginTop: "10px",
            }}
          >
            {fp.bars.map((bar) => (
              <span
                key={bar.digitIndex}
                style={{
                  flexGrow: 1,
                  display: "flex",
                  justifyContent: "center",
                  fontFamily: "monospace",
                  fontSize: "17px",
                  color: "rgba(255,255,255,0.38)",
                }}
              >
                {bar.digit}
              </span>
            ))}
          </div>
        </div>

        {/* Top row: section label + status chip */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
          }}
        >
          <span
            style={{
              fontSize: "20px",
              fontWeight: 600,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.55)",
            }}
          >
            {visual.label}
          </span>
          <span
            style={{
              display: "flex",
              alignItems: "center",
              padding: "8px 18px",
              borderRadius: "999px",
              fontSize: "18px",
              fontWeight: 700,
              letterSpacing: "0.08em",
              color: chip.color,
              border: `1px solid ${chip.color}`,
              backgroundColor: "rgba(0,0,0,0.25)",
            }}
          >
            {chip.label}
          </span>
        </div>

        {/* Main content: code + title */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            // stop short of the fingerprint zone (right third) — long titles
            // wrap to two lines instead of colliding with the bars
            maxWidth: "640px",
          }}
        >
          <span
            style={{
              fontFamily: "monospace",
              fontSize: "34px",
              fontWeight: 700,
              color: visual.accent,
              letterSpacing: "0.04em",
              marginBottom: "18px",
              display: "flex",
            }}
          >
            KBLI {kbli.code}
          </span>
          <span
            style={{
              fontSize: title.length > 60 ? "44px" : "54px",
              fontWeight: 700,
              lineHeight: 1.15,
              color: "#ffffff",
              display: "flex",
            }}
          >
            {title}
          </span>
        </div>

        {/* Footer branding bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
          }}
        >
          <span
            style={{
              fontSize: "22px",
              fontWeight: 700,
              letterSpacing: "0.06em",
              color: "#ffffff",
            }}
          >
            BALI ZERO
          </span>
          <span
            style={{
              fontSize: "18px",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "rgba(255,255,255,0.45)",
            }}
          >
            KBLI 2025 Navigator
          </span>
        </div>
      </div>
    ),
    {
      width: WIDTH,
      height: HEIGHT,
      headers: {
        "Cache-Control": "public, immutable, no-transform, max-age=31536000",
      },
    },
  );
}
