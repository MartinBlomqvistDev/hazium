import { ImageResponse } from "next/og";

/**
 * The link-preview card, generated rather than shipped as a binary.
 *
 * Kept to the name, the one-line claim and the domain. No headline statistic:
 * a number baked into an image cannot be corrected when the benchmark is re-run,
 * and a stale figure in a preview card is exactly the kind of quiet inaccuracy
 * this project exists not to produce. Surfaces and accent are the site's own
 * tokens so the card and the page read as one thing.
 *
 * This card carried "early warning from public evidence" long after that framing
 * was retired from the title and the page for overselling. It is the surface
 * almost every visitor sees first and the last one anybody thinks to check, so
 * it outlived the claim everywhere else. The replacement states the correction
 * rather than a capability, and states both halves of it: "the baseline beat the
 * model" on its own would advertise the intermediate result as if it were the
 * final one, which is the same failure pointed the other way.
 */

export const alt =
  "Hazium: a model of EU pesticide withdrawals, and the baseline that beat it";
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
          <div style={{ color: "#ffffff", fontSize: 64, lineHeight: 1.1, fontWeight: 700 }}>
            The baseline beat the model. The target was wrong.
          </div>
          <div style={{ color: "#c3c2b7", fontSize: 30, lineHeight: 1.4, maxWidth: 900 }}>
            A temporal knowledge graph of EU pesticide regulation, the trivial baseline that
            beat the first version of it, and the reformulation that earned the result back.
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 60, height: 4, background: "#d95926" }} />
          <div style={{ color: "#898781", fontSize: 24 }}>
            Every fact carries the date it became public
          </div>
        </div>
      </div>
    ),
    size,
  );
}
