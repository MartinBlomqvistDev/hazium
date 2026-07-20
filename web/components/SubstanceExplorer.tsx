"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { SubstanceRow, SubstancesData } from "@/lib/types";

type Variant = "headline" | "early_warning";
type SortKey = "rank" | "name" | "hz" | "ag" | "sl";
const PAGE_SIZE = 50;

function rankKey(v: Variant): "hr" | "er" {
  return v === "headline" ? "hr" : "er";
}
function labelKey(v: Variant): "hL" | "eL" {
  return v === "headline" ? "hL" : "eL";
}

export default function SubstanceExplorer({ data }: { data: SubstancesData }) {
  const [variant, setVariant] = useState<Variant>("headline");
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("rank");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [pestOnly, setPestOnly] = useState(false);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [cmrOnly, setCmrOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState<string | null>(null);

  const rk = rankKey(variant);
  const lk = labelKey(variant);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = data.substances.filter((s) => {
      if (pestOnly && s.p !== 1) return false;
      if (flaggedOnly && s[lk] !== 1) return false;
      if (cmrOnly && s.cmr !== 1) return false;
      if (q && !s.n.toLowerCase().includes(q) && !s.c.includes(q)) return false;
      return true;
    });
    const dir = sortDir === "asc" ? 1 : -1;
    rows = [...rows].sort((a, b) => {
      let av: number | string;
      let bv: number | string;
      if (sortKey === "rank") {
        av = a[rk];
        bv = b[rk];
      } else if (sortKey === "name") {
        av = a.n.toLowerCase();
        bv = b.n.toLowerCase();
      } else {
        av = a[sortKey];
        bv = b[sortKey];
      }
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return a[rk] - b[rk];
    });
    return rows;
  }, [data.substances, query, pestOnly, flaggedOnly, cmrOnly, sortKey, sortDir, rk, lk]);

  const total = filtered.length;
  const maxPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
  const safePage = Math.min(page, maxPage);
  const pageRows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  function reset() {
    setPage(0);
    setOpen(null);
  }
  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "name" ? "asc" : key === "rank" ? "asc" : "desc");
    }
    reset();
  }

  return (
    <div>
      {/* controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <input
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            reset();
          }}
          placeholder="Search name or CAS…"
          className="w-full rounded-md border border-hairline bg-surface px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:border-accent focus:outline-none sm:max-w-xs"
        />
        <div className="inline-flex shrink-0 rounded-md border border-hairline p-0.5 text-sm">
          {(["headline", "early_warning"] as Variant[]).map((v) => (
            <button
              key={v}
              type="button"
              onClick={() => {
                setVariant(v);
                reset();
              }}
              className={`rounded px-3 py-1 transition-colors ${
                variant === v
                  ? "bg-accent/15 text-accent"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {v === "headline" ? "EU non-renewal" : "+ SE reevaluation"}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
        <FilterChip
          label="Pesticides only"
          on={pestOnly}
          set={(b) => {
            setPestOnly(b);
            reset();
          }}
        />
        <FilterChip
          label="Known regulatory action"
          on={flaggedOnly}
          set={(b) => {
            setFlaggedOnly(b);
            reset();
          }}
        />
        <FilterChip
          label="CMR-classified"
          on={cmrOnly}
          set={(b) => {
            setCmrOnly(b);
            reset();
          }}
        />
        <span className="ml-auto text-text-muted">
          {total.toLocaleString()} of {data.population.toLocaleString()} · ranked by{" "}
          {variant === "headline" ? "EU-non-renewal" : "early-warning"} risk
        </span>
      </div>

      {/* table */}
      <div className="mt-4 overflow-x-auto rounded-lg border border-hairline">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-hairline bg-surface/60 text-xs uppercase tracking-wide text-text-muted">
            <tr>
              <Th onClick={() => toggleSort("rank")} active={sortKey === "rank"} dir={sortDir} className="w-16">
                Rank
              </Th>
              <Th onClick={() => toggleSort("name")} active={sortKey === "name"} dir={sortDir}>
                Substance
              </Th>
              <th className="px-3 py-2 font-medium">Hazards</th>
              <Th onClick={() => toggleSort("ag")} active={sortKey === "ag"} dir={sortDir} className="w-24">
                Approved
              </Th>
              <Th onClick={() => toggleSort("sl")} active={sortKey === "sl"} dir={sortDir} className="w-24">
                Sales (t)
              </Th>
              <th className="px-3 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {pageRows.map((s) => (
              <Row
                key={s.c || s.n}
                s={s}
                rk={rk}
                lk={lk}
                open={open === (s.c || s.n)}
                onToggle={() => setOpen((o) => (o === (s.c || s.n) ? null : s.c || s.n))}
              />
            ))}
            {pageRows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-text-muted">
                  No substances match these filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* pagination */}
      {total > PAGE_SIZE && (
        <div className="mt-4 flex items-center justify-between text-sm text-text-secondary">
          <span>
            {safePage * PAGE_SIZE + 1}–{Math.min((safePage + 1) * PAGE_SIZE, total)} of{" "}
            {total.toLocaleString()}
          </span>
          <div className="flex gap-2">
            <PageBtn
              disabled={safePage === 0}
              onClick={() => {
                setPage(safePage - 1);
                setOpen(null);
              }}
            >
              Prev
            </PageBtn>
            <PageBtn
              disabled={safePage >= maxPage}
              onClick={() => {
                setPage(safePage + 1);
                setOpen(null);
              }}
            >
              Next
            </PageBtn>
          </div>
        </div>
      )}
    </div>
  );
}

function Th({
  children,
  onClick,
  active,
  dir,
  className = "",
}: {
  children: React.ReactNode;
  onClick: () => void;
  active: boolean;
  dir: "asc" | "desc";
  className?: string;
}) {
  return (
    <th className={`px-3 py-2 font-medium ${className}`}>
      <button
        type="button"
        onClick={onClick}
        className={`inline-flex items-center gap-1 hover:text-text-primary ${active ? "text-text-primary" : ""}`}
      >
        {children}
        {active && <span aria-hidden>{dir === "asc" ? "▲" : "▼"}</span>}
      </button>
    </th>
  );
}

function Row({
  s,
  rk,
  lk,
  open,
  onToggle,
}: {
  s: SubstanceRow;
  rk: "hr" | "er";
  lk: "hL" | "eL";
  open: boolean;
  onToggle: () => void;
}) {
  const flagged = s[lk] === 1;
  const isLandmark = !!s.lm;
  return (
    <>
      <tr
        onClick={onToggle}
        className={`cursor-pointer border-b border-hairline/60 last:border-0 hover:bg-surface/60 ${
          open ? "bg-surface/60" : ""
        }`}
        style={isLandmark ? { boxShadow: "inset 2px 0 0 var(--accent)" } : undefined}
      >
        <td className="px-3 py-2 tabular-nums text-text-secondary">{s[rk]}</td>
        <td className="px-3 py-2">
          <span className="font-medium text-text-primary">{s.n}</span>
          {isLandmark && (
            <span className="ml-2 rounded-sm bg-accent/15 px-1.5 py-0.5 text-[10px] text-accent">
              landmark
            </span>
          )}
          <div className="text-[11px] tabular-nums text-text-muted">{s.c || "no CAS"}</div>
        </td>
        <td className="px-3 py-2">
          <div className="flex flex-wrap gap-1">
            {s.cmr === 1 && <Badge tone="critical">CMR</Badge>}
            {s.aq === 1 && <Badge tone="warning">Aquatic</Badge>}
            {s.st === 1 && <Badge tone="neutral">STOT</Badge>}
            {s.hz > 0 && <span className="text-[11px] text-text-muted">{s.hz} codes</span>}
            {s.hz === 0 && <span className="text-[11px] text-text-muted">—</span>}
          </div>
        </td>
        <td className="px-3 py-2 tabular-nums text-text-secondary">
          {s.ap === 1 ? `${s.ag} yr` : "—"}
        </td>
        <td className="px-3 py-2 tabular-nums text-text-secondary">{s.sl > 0 ? s.sl : "—"}</td>
        <td className="px-3 py-2">
          {flagged ? (
            <span className="text-xs text-status-critical/90">regulatory action</span>
          ) : (
            <span className="text-xs text-text-muted">no action</span>
          )}
        </td>
      </tr>
      {open && (
        <tr className="border-b border-hairline/60 bg-surface/40">
          <td colSpan={6} className="px-3 py-3">
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs text-text-secondary sm:grid-cols-4">
              <Detail label="EU-non-renewal rank">{s.hr.toLocaleString()}</Detail>
              <Detail label="early-warning rank">{s.er.toLocaleString()}</Detail>
              <Detail label="pesticide">{s.p === 1 ? "yes" : "no"}</Detail>
              <Detail label="severe hazard codes">{s.hz}</Detail>
              <Detail label="CMR">{s.cmr === 1 ? "yes" : "no"}</Detail>
              <Detail label="aquatic chronic 1">{s.aq === 1 ? "yes" : "no"}</Detail>
              <Detail label="years since EU approval">{s.ap === 1 ? s.ag : "not approved"}</Detail>
              <Detail label="latest sales (tonnes)">{s.sl > 0 ? s.sl : "—"}</Detail>
            </div>
            {isLandmark && (
              <p className="mt-2 text-xs text-text-muted">
                {s.n} is a HEWB landmark case.{" "}
                <Link href="/#result" className="text-accent hover:underline">
                  See its lead-time on the timeline →
                </Link>
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-text-muted">{label}</div>
      <div className="text-text-primary">{children}</div>
    </div>
  );
}

function Badge({ children, tone }: { children: React.ReactNode; tone: "critical" | "warning" | "neutral" }) {
  const cls =
    tone === "critical"
      ? "bg-status-critical/15 text-status-critical/90"
      : tone === "warning"
        ? "bg-status-warning/15 text-status-warning"
        : "bg-surface-raised text-text-secondary";
  return <span className={`rounded-sm px-1.5 py-0.5 text-[10px] ${cls}`}>{children}</span>;
}

function FilterChip({ label, on, set }: { label: string; on: boolean; set: (b: boolean) => void }) {
  return (
    <button
      type="button"
      onClick={() => set(!on)}
      className={`rounded-full border px-2.5 py-1 transition-colors ${
        on
          ? "border-accent bg-accent/15 text-accent"
          : "border-hairline text-text-secondary hover:text-text-primary"
      }`}
    >
      {label}
    </button>
  );
}

function PageBtn({
  children,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-md border border-hairline px-3 py-1 text-text-primary transition-colors hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40"
    >
      {children}
    </button>
  );
}
