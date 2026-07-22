"use client";

/**
 * Two-hop evidence mesh, rotated in 3D and revealed through time.
 *
 * Colour discipline, which drives most of what this looks like:
 *
 * - The ~580 peripheral substances are *context*, not categories, and carry no
 *   label, so they are drawn in neutral ink. Colouring them would be a
 *   categorical encoding nobody can read, and the four-slot palette only clears
 *   the all-pairs CVD floor with a secondary encoding present.
 * - Colour is spent only where identity is also shown: the handful of core
 *   nodes, which get a validated categorical slot, a distinct shape, and a
 *   direct label. Three encodings, not one.
 * - The brand accent marks the focal substance. Per the token contract in
 *   globals.css it is identity, never data.
 * - Status red appears exactly once, when the real regulatory action lands, and
 *   always with a text label beside it.
 *
 * Depth is carried by opacity, size and line weight rather than glow, and marks
 * are flat. Detail lives in a panel below the canvas rather than a tooltip
 * inside it, which keeps it readable on a phone.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { EvidenceMeshCase, EvidenceMeshData } from "@/lib/types";

const STEP_MS = 950;
const HEIGHT = 440;

/** Categorical slots 1-4, dark steps, in the order the export fixes. */
const TYPE_COLOR = ["#3987e5", "#008300", "#d55181", "#c98500"];
const TYPE_LABEL: Record<string, string> = {
  substance: "substance",
  document: "EFSA assessment",
  hazard: "hazard classification",
  regulatory_event: "regulatory event",
};

const INK_MUTED = "#898781";
const HAIRLINE = "#2c2c2a";
const ACCENT = "#d95926";
const CRITICAL = "#d03b3b";

interface Picked {
  index: number;
  label: string;
  type: string;
  ref: string;
  core: boolean;
  frame: number;
  via: string;
}

const PREDICATE_PHRASE: Record<string, string> = {
  degrades_to: "degrades into",
  classified_as: "is classified as",
  subject_of: "is the subject of",
  evidenced_by: "is assessed in",
  contains: "contains",
  approved_in: "is approved in",
};

function refHref(ref: string): { href: string; text: string } | null {
  if (ref.startsWith("doi:")) {
    const doi = ref.slice(4);
    return { href: `https://doi.org/${doi}`, text: doi };
  }
  return null;
}

export default function EvidenceMesh({ data }: { data: EvidenceMeshData }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [frame, setFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [picked, setPicked] = useState<Picked | null>(null);
  // Mirrored into a ref so the draw loop can highlight the selection without
  // the selection being a dependency of the render effect: otherwise every
  // click tears the loop down and reallocates the projection buffers.
  const pickedIndex = useRef<number | null>(null);

  const item: EvidenceMeshCase | undefined = data.cases[0];
  const lastFrame = data.cutoffs.length - 1;

  // Rotation and projected positions live in refs: they change every animation
  // frame and must not drive React re-renders.
  const angle = useRef({ y: 0.6, x: -0.25 });
  const drag = useRef<{ x: number; y: number } | null>(null);
  const moved = useRef(false);
  const projected = useRef<Float32Array>(new Float32Array(0));
  const scaleRef = useRef<Float32Array>(new Float32Array(0));
  // The render loop reads the current frame without being torn down and rebuilt
  // on every step, so the value is mirrored into a ref from an effect. Writing
  // it during render is a React 19 error (react-hooks/refs).
  const frameRef = useRef(0);
  useEffect(() => {
    frameRef.current = frame;
  }, [frame]);

  const actionFrame = useMemo(() => {
    if (!item?.action_date) return null;
    const i = data.cutoffs.findIndex((c) => c >= item.action_date!);
    return i === -1 ? null : i;
  }, [item, data.cutoffs]);

  useEffect(() => {
    if (!playing || frame >= lastFrame) return;
    const t = setTimeout(() => {
      const next = frame + 1;
      if (next >= lastFrame) setPlaying(false);
      setFrame(Math.min(next, lastFrame));
    }, STEP_MS);
    return () => clearTimeout(t);
  }, [playing, frame, lastFrame]);

  // Render loop. Kept outside React so rotation is smooth.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !item) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const n = item.types.length;
    projected.current = new Float32Array(n * 2);
    scaleRef.current = new Float32Array(n);

    // The focal substance sits at the model origin, but the mesh's mass does
    // not, so projecting around the origin parks the cloud off-centre with dead
    // margin. Recentre on the centroid, computed once: it is constant in model
    // space, so it cannot jitter as the view rotates.
    let mx = 0, my = 0, mz = 0;
    for (let i = 0; i < n; i++) {
      mx += item.xyz[i * 3];
      my += item.xyz[i * 3 + 1];
      mz += item.xyz[i * 3 + 2];
    }
    mx /= n; my /= n; mz /= n;
    let raf = 0;

    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = HEIGHT;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);

      if (!drag.current) angle.current.y += 0.0022;
      const cy = Math.cos(angle.current.y);
      const sy = Math.sin(angle.current.y);
      const cxr = Math.cos(angle.current.x);
      const sxr = Math.sin(angle.current.x);
      const s = Math.min(w, h) / 430;
      const f = frameRef.current;

      const px = projected.current;
      const sc = scaleRef.current;
      for (let i = 0; i < n; i++) {
        if (item.frames[i] > f) {
          sc[i] = 0;
          continue;
        }
        const X = item.xyz[i * 3] - mx;
        const Y = item.xyz[i * 3 + 1] - my;
        const Z = item.xyz[i * 3 + 2] - mz;
        const x1 = X * cy + Z * sy;
        const z1 = -X * sy + Z * cy;
        const y1 = Y * cxr - z1 * sxr;
        const z2 = Y * sxr + z1 * cxr;
        const k = 560 / (560 + z2 + 230);
        px[i * 2] = w / 2 + x1 * k * s * 2.2;
        px[i * 2 + 1] = h / 2 + y1 * k * s * 2.2;
        sc[i] = k;
      }

      ctx.lineWidth = 0.7;
      for (let e = 0; e < item.edges.length; e += 3) {
        const a = item.edges[e];
        const b = item.edges[e + 1];
        if (item.edges[e + 2] > f || sc[a] === 0 || sc[b] === 0) continue;
        const depth = (sc[a] + sc[b]) / 2;
        ctx.globalAlpha = Math.max(0.1, Math.min(0.55, (depth - 0.62) * 1.7));
        ctx.strokeStyle = HAIRLINE;
        ctx.beginPath();
        ctx.moveTo(px[a * 2], px[a * 2 + 1]);
        ctx.lineTo(px[b * 2], px[b * 2 + 1]);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      const order: number[] = [];
      for (let i = 0; i < n; i++) if (sc[i] > 0) order.push(i);
      order.sort((a, b) => sc[a] - sc[b]);

      for (const i of order) {
        const isCentre = i === item.center;
        const isCore = item.core[i] === 1;
        const x = px[i * 2];
        const y = px[i * 2 + 1];
        const depth = Math.max(0.2, Math.min(1, (sc[i] - 0.6) * 2.6));
        const r = (isCentre ? 7.5 : isCore ? 4.2 : 1.9) * sc[i] * 1.5 * s;

        if (isCentre) {
          ctx.globalAlpha = 1;
          ctx.fillStyle = f >= (actionFrame ?? Infinity) ? CRITICAL : ACCENT;
        } else if (isCore) {
          ctx.globalAlpha = 0.95;
          ctx.fillStyle = TYPE_COLOR[item.types[i]] ?? INK_MUTED;
        } else {
          // Context, not category: neutral ink, weight by depth only.
          ctx.globalAlpha = depth * 0.5;
          ctx.fillStyle = INK_MUTED;
        }

        ctx.beginPath();
        const t = item.types[i];
        if (isCore && t === 2) {
          ctx.rect(x - r, y - r, r * 2, r * 2); // hazard: square
        } else if (isCore && t === 3) {
          ctx.moveTo(x, y - r * 1.2); // regulatory event: diamond
          ctx.lineTo(x + r, y);
          ctx.lineTo(x, y + r * 1.2);
          ctx.lineTo(x - r, y);
          ctx.closePath();
        } else {
          ctx.arc(x, y, r, 0, Math.PI * 2);
        }
        ctx.fill();

        if (pickedIndex.current === i) {
          ctx.globalAlpha = 1;
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 1.6;
          ctx.beginPath();
          ctx.arc(x, y, r + 5, 0, Math.PI * 2);
          ctx.stroke();
          ctx.lineWidth = 0.7;
        }
      }

      ctx.globalAlpha = 1;
      ctx.textAlign = "center";

      // Label sparingly. The detail panel below the canvas exists precisely so
      // that marks do not have to carry their own identity, and labelling all
      // thirteen core nodes buried the picture under six overlapping EFSA
      // titles. Only the focal substance and short codes get drawn; assessments
      // are identified by colour, shape, and a click.
      const drawn: Array<[number, number, number, number]> = [];
      const fits = (x: number, y: number, halfW: number, halfH: number) => {
        for (const [ax, ay, aw, ah] of drawn) {
          if (Math.abs(x - ax) < halfW + aw && Math.abs(y - ay) < halfH + ah) return false;
        }
        drawn.push([x, y, halfW, halfH]);
        return true;
      };

      for (const i of order.slice().reverse()) {
        if (item.core[i] !== 1) continue;
        const isCentre = i === item.center;
        // Regulatory events carry the narrative ("non-renewal 2019") but are
        // written long in the graph, so they are compacted rather than dropped.
        // Assessment titles are dropped outright: they are the clutter, and
        // they are one click away in the panel.
        const raw = item.labels[i];
        const label =
          item.types[i] === 3
            ? raw.replace(/_/g, "-").replace(/(\d{4})-\d{2}-\d{2}/, "$1")
            : raw;
        if (!isCentre && label.length > 18) continue;

        ctx.font = isCentre
          ? '600 13px system-ui, sans-serif'
          : '11px ui-monospace, monospace';
        const halfW = ctx.measureText(label).width / 2 + 4;
        const x = px[i * 2];
        const y = px[i * 2 + 1] - (isCentre ? 15 : 10);
        if (!isCentre && !fits(x, y, halfW, 8)) continue;
        if (isCentre) drawn.push([x, y, halfW, 8]);

        ctx.fillStyle = isCentre ? "#ffffff" : "#c3c2b7";
        ctx.fillText(label, x, y);
      }
    };

    // Paint once synchronously before handing over to the animation loop. This
    // is not just belt and braces: requestAnimationFrame does not fire while
    // the page is not being composited (a hidden tab, a background window), and
    // without a first synchronous paint the canvas would sit blank and, worse,
    // the projected positions that hit-testing reads would never be computed,
    // so clicking would silently do nothing.
    draw();

    const loop = () => {
      draw();
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
    // `frame` is a dependency so a scrub repaints synchronously via the draw()
    // above. Relying on the animation loop alone would leave the canvas stale
    // whenever requestAnimationFrame is throttled or suspended.
  }, [item, actionFrame, frame]);

  const pick = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      if (!canvas || !item) return;
      const rect = canvas.getBoundingClientRect();
      const mx = clientX - rect.left;
      const my = clientY - rect.top;
      const px = projected.current;
      const sc = scaleRef.current;
      let best = -1;
      let bestDist = 18 * 18;
      for (let i = 0; i < item.types.length; i++) {
        if (sc[i] === 0) continue;
        const dx = px[i * 2] - mx;
        const dy = px[i * 2 + 1] - my;
        const d = dx * dx + dy * dy;
        // Prefer core nodes when marks overlap, since they are the labelled ones.
        const bias = item.core[i] === 1 ? 0.4 : 1;
        if (d * bias < bestDist) {
          bestDist = d * bias;
          best = i;
        }
      }
      pickedIndex.current = best === -1 ? null : best;
      setPicked(
        best === -1
          ? null
          : {
              index: best,
              label: item.labels[best],
              type: data.type_order[item.types[best]] ?? "unknown",
              ref: item.refs[best],
              core: item.core[best] === 1,
              frame: item.frames[best],
              via: item.via[best] ?? "",
            },
      );
    },
    [item, data.type_order],
  );

  if (!item) return null;

  const year = data.cutoffs[frame].slice(0, 4);
  const rank = item.ranks[frame];
  const actioned = actionFrame !== null && frame >= actionFrame;
  let visibleNodes = 0;
  for (let i = 0; i < item.frames.length; i++) if (item.frames[i] <= frame) visibleNodes++;
  let visibleEdges = 0;
  for (let e = 2; e < item.edges.length; e += 3) if (item.edges[e] <= frame) visibleEdges++;

  const link = picked ? refHref(picked.ref) : null;

  return (
    <section className="mx-auto w-full max-w-5xl px-4 py-14" aria-labelledby="mesh-heading">
      <h2 id="mesh-heading" className="text-2xl font-semibold tracking-tight">
        What was knowable, year by year
      </h2>
      <p className="mt-2 max-w-2xl text-sm text-text-secondary">
        Every fact carries the date it became public, so this is the evidence available at
        each cutoff, not what is known today. Substances appear once they are connected to{" "}
        {item.name} within two steps, most often by sharing a hazard classification.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => (frame >= lastFrame ? (setFrame(0), setPlaying(true)) : setPlaying((p) => !p))}
          className="rounded border border-hairline bg-surface-raised px-3 py-1 text-sm"
        >
          {frame >= lastFrame ? "Replay" : playing ? "Pause" : "Play"}
        </button>
        <input
          type="range"
          min={0}
          max={lastFrame}
          value={frame}
          onChange={(e) => {
            setPlaying(false);
            setFrame(Number(e.target.value));
          }}
          className="w-44"
          aria-label="Cutoff year"
        />
        <span className="tabular-nums font-mono text-sm font-semibold">{year}</span>
        <span className="tabular-nums font-mono text-sm text-text-secondary">
          {rank == null ? (actioned ? "censored" : "unranked") : `rank #${rank}`}
        </span>
        {actioned && (
          <span
            className="rounded px-2 py-0.5 font-mono text-xs font-semibold"
            style={{ color: CRITICAL, border: `1px solid ${CRITICAL}` }}
          >
            EU action {item.action_date}
          </span>
        )}
        <span className="ml-auto tabular-nums font-mono text-xs text-text-muted">
          {visibleNodes} facts · {visibleEdges} links
        </span>
      </div>

      <canvas
        ref={canvasRef}
        style={{ height: HEIGHT }}
        className="mt-3 w-full cursor-grab rounded-lg border border-hairline bg-page"
        onPointerDown={(e) => {
          drag.current = { x: e.clientX, y: e.clientY };
          moved.current = false;
        }}
        onPointerMove={(e) => {
          if (!drag.current) return;
          if (Math.abs(e.clientX - drag.current.x) > 3 || Math.abs(e.clientY - drag.current.y) > 3) {
            moved.current = true;
          }
          angle.current.y += (e.clientX - drag.current.x) * 0.006;
          angle.current.x = Math.max(
            -1.2,
            Math.min(1.2, angle.current.x + (e.clientY - drag.current.y) * 0.004),
          );
          drag.current = { x: e.clientX, y: e.clientY };
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onPointerLeave={() => {
          drag.current = null;
        }}
        // Picking hangs off click rather than pointerup: it fires after a clean
        // press in every browser, survives synthetic dispatch, and keeps the
        // rotate gesture and the select gesture from competing.
        onClick={(e) => {
          if (moved.current) {
            moved.current = false;
            return;
          }
          pick(e.clientX, e.clientY);
        }}
        role="img"
        aria-label={`Evidence mesh for ${item.name} at ${year}: ${visibleNodes} facts, ${visibleEdges} links`}
      />

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-text-secondary">
        {data.type_order.map((t, i) => (
          <span key={t} className="inline-flex items-center gap-1.5">
            <span
              aria-hidden
              className="inline-block h-2.5 w-2.5"
              style={{
                backgroundColor: TYPE_COLOR[i],
                borderRadius: i === 2 ? 0 : i === 3 ? 2 : "50%",
                transform: i === 3 ? "rotate(45deg)" : undefined,
              }}
            />
            {TYPE_LABEL[t] ?? t}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: INK_MUTED }} />
          related substance
        </span>
        <span className="text-text-muted">drag to rotate · click a mark for detail</span>
      </div>

      <div className="mt-4 min-h-24 rounded-lg border border-hairline bg-surface p-4">
        {picked ? (
          <div>
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className="font-medium">{picked.label}</span>
              <span className="font-mono text-xs text-text-muted">
                {TYPE_LABEL[picked.type] ?? picked.type}
              </span>
              <span className="font-mono text-xs text-text-muted">
                first knowable {data.cutoffs[picked.frame].slice(0, 4)}
              </span>
            </div>
            {picked.index !== item.center && picked.via && (
              <p className="mt-1.5 text-sm text-text-secondary">
                {picked.via.startsWith("direct:") ? (
                  <>
                    {item.name} {PREDICATE_PHRASE[picked.via.slice(7)] ?? picked.via.slice(7)}{" "}
                    this.
                  </>
                ) : (
                  <>
                    Not related to {item.name} directly. Both carry{" "}
                    <span className="font-mono">{picked.via.slice(7)}</span>, which is what puts
                    it in this picture.
                  </>
                )}
              </p>
            )}
            {link ? (
              <a
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-block font-mono text-xs underline"
                style={{ color: ACCENT }}
              >
                doi.org/{link.text}
              </a>
            ) : picked.ref.startsWith("cas:") ? (
              <p className="mt-2 font-mono text-xs text-text-secondary">
                CAS {picked.ref.slice(4)}
              </p>
            ) : picked.ref.startsWith("clp:") ? (
              <p className="mt-2 text-xs text-text-secondary">
                CLP hazard class{" "}
                <span className="font-mono text-text-primary">{picked.ref.slice(4)}</span>, as
                recorded in ECHA&apos;s harmonised classification list (Annex VI).{" "}
                <a
                  href={item.clp_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono underline"
                  style={{ color: ACCENT }}
                >
                  CLP Regulation
                </a>
              </p>
            ) : (
              <p className="mt-2 text-xs text-text-muted">
                No external identifier is published for this node, so no link is offered.
              </p>
            )}
          </div>
        ) : (
          <p className="text-sm text-text-muted">
            Click any mark to see what it is. EFSA assessments link to their published opinion.
          </p>
        )}
      </div>

      {item.truncated > 0 && (
        <p className="mt-2 text-xs text-text-muted">
          {item.truncated} further connected substances are not drawn.
        </p>
      )}
    </section>
  );
}
