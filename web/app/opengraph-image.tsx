import { ImageResponse } from "next/og";

/**
 * The link-preview card, generated rather than shipped as a binary.
 *
 * Kept to the name, the one-line claim and the domain. No headline statistic:
 * a number baked into an image cannot be corrected when the benchmark is re-run,
 * and a stale figure in a preview card is exactly the kind of quiet inaccuracy
 * this project exists not to produce. Surfaces and accent are the site's own
 * tokens so the card and the page read as one thing.
 */

export const alt = "Hazium: early warning from public evidence";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#0d0d0d",
          padding: 72,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: 12,
              border: "4px solid #d95926",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              fontSize: 34,
              fontWeight: 700,
            }}
          >
            Hz
          </div>
          <div style={{ color: "#c3c2b7", fontSize: 30, letterSpacing: 1 }}>hazium.org</div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ color: "#ffffff", fontSize: 68, lineHeight: 1.1, fontWeight: 700 }}>
            Early warning from public evidence
          </div>
          <div style={{ color: "#c3c2b7", fontSize: 30, lineHeight: 1.4, maxWidth: 900 }}>
            A temporal knowledge graph of EU pesticide regulation, tested against a
            falsifiable early-warning benchmark.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 60, height: 4, background: "#d95926" }} />
          <div style={{ color: "#898781", fontSize: 24 }}>
            Every fact carries the date it became knowable
          </div>
        </div>
      </div>
    ),
    size,
  );
}
