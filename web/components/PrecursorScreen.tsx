"use client";

import { useState } from "react";
import type { TfaScreenData } from "@/lib/types";

const ACCENT = "#d95926";

/**
 * The answer to the section above it.
 *
 * The model cannot see this hazard, and the reason is not the model: a
 * withdrawal is a committee decision and TFA formation is a chemical property.
 * So this surface is deliberately not a model. It is one rule over a public
 * molecular formula, with the weights written down rather than fitted, because
 * six confirmed substances can check a rule and cannot train one.
 *
 * Every row is shown, not a top slice. A screen that publishes only its best
 * entries is not a screen, and the twenty here that no regulator has looked at
 * are the point of the exercise rather than an embarrassment to be trimmed.
 */
export default function PrecursorScreen({ data }: { data: TfaScreenData }) {
  const [open, setOpen] = useState<string | null>(null);
  const maxScore = Math.max(...data.entries.map((e) => e.score), 1);

  return (
    <section id="screen" className="border-b border-hairline bg-surface/40">
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
          The screen that does find it
        </h2>
        <p className="mt-4 text-text-secondary">
          TFA comes from trifluoromethyl groups. That is chemistry, not regulation, so it can
          be read off a molecular formula. A formula is public, free from PubChem, and the same
          at every cutoff, which means this can be run over the whole approved population
          without a model and without any way to leak.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Stat
            value={`${data.flagged} of ${data.population}`}
            label="of the approved substances with a resolved structure, able to form TFA"
          />
          <Stat
            value={String(data.flagged - data.kemi_found)}
            label="of them that no regulator is currently reviewing, which is the part worth arguing about"
          />
          <Stat value="0" label="models fitted, parameters estimated, or labels used" />
        </div>

        {/* Stated before a chemist states it. The hypergeometric figure this
            block used to lead with (1 in 1,138,341) is arithmetically correct
            and rhetorically dishonest: KEMI selected those six substances for
            forming TFA, and TFA comes from CF3, so a CF3 rule was never going to
            miss them. It measures implementation, not discovery. */}
        <div className="mt-8 rounded-lg border border-hairline bg-page p-5">
          <h3 className="font-medium text-text-primary">
            What the cohort check does and does not show
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            Kemikalieinspektionen chose its {data.kemi_total} because they form TFA, and TFA
            comes from trifluoromethyl groups. A rule that reads those groups was never going
            to miss them. Finding all {data.kemi_total} shows the rule is implemented
            correctly and applied to the right population. It is not evidence of a discovery,
            and any figure quoting the odds against it would be dressing a tautology as a
            result.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            The check that carries weight is the other one. EFSA&apos;s own degradation records
            name TFA parents independently of KEMI and of this screen.{" "}
            {data.efsa_found} of the {data.efsa_total} in the approved population{" "}
            {data.efsa_found === 1 ? "is" : "are"} flagged here. So is the reverse test:{" "}
            {data.fluorine_without_cf3} substances carry three or more fluorines without a
            CF3 group matching, and they are tracked as possible holes in the rule rather
            than quietly dropped.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            What the screen is actually for is the{" "}
            <strong className="text-text-primary">
              {data.flagged - data.kemi_found} substances below that nobody has opened a file
              on
            </strong>
            . Those are a prediction, made from data that has been public for decades, and
            they are unconfirmed.
          </p>
        </div>

        <div className="mt-10">
          <h3 className="font-medium text-text-primary">The whole shortlist</h3>
          <p className="mt-2 text-sm text-text-secondary">
            Ranked by fluorine payload and Swedish sales volume, combined by a rule written down
            in the source rather than learned from the substances it is checked against. Click a
            row for its formula and uses.
          </p>
          <div className="mt-5 space-y-1">
            {data.entries.map((entry) => {
              const isOpen = open === entry.cas;
              return (
                <div key={entry.cas} className={`rounded-md ${isOpen ? "bg-surface-raised/50" : ""}`}>
                  <div
                    role="button"
                    tabIndex={0}
                    aria-expanded={isOpen}
                    className="flex cursor-pointer items-center gap-2 rounded-md px-1 py-1.5 text-sm transition-colors hover:bg-surface-raised/60 sm:gap-3"
                    onClick={() => setOpen(isOpen ? null : entry.cas)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setOpen(isOpen ? null : entry.cas);
                      }
                    }}
                  >
                    <span className="w-6 shrink-0 text-right font-mono text-xs tabular-nums text-text-muted">
                      {entry.rank}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-text-secondary">
                      {entry.name}{" "}
                      <span className="text-text-muted" aria-hidden>
                        {isOpen ? "▾" : "▸"}
                      </span>
                    </span>
                    <span className="relative hidden h-3 w-24 shrink-0 rounded-sm bg-hairline/40 sm:block">
                      <span
                        className="absolute inset-y-0 left-0 rounded-sm"
                        aria-hidden
                        style={{
                          width: `${(entry.score / maxScore) * 100}%`,
                          backgroundColor: ACCENT,
                        }}
                      />
                    </span>
                    <span className="w-24 shrink-0 text-right text-[11px] text-text-muted">
                      {entry.in_kemi_cohort
                        ? "reevaluation"
                        : entry.efsa_confirmed
                          ? "EFSA: forms TFA"
                          : ""}
                    </span>
                  </div>

                  {isOpen && (
                    <div className="mx-1 mb-2 rounded-md border border-hairline bg-page/60 px-4 py-4 text-xs">
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <span className="text-sm font-medium text-text-primary">{entry.name}</span>
                        <span className="text-text-muted">CAS {entry.cas}</span>
                      </div>
                      <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
                        <dt className="text-text-muted">Formula</dt>
                        <dd className="font-mono text-text-secondary">{entry.formula}</dd>
                        <dt className="text-text-muted">CF3 groups</dt>
                        <dd className="text-text-secondary">
                          {entry.cf3_groups} of {entry.fluorine_count} fluorine atoms
                        </dd>
                        <dt className="text-text-muted">Sold in Sweden</dt>
                        <dd className="text-text-secondary">
                          {entry.tonnes === null ? "no recorded sales" : `${entry.tonnes} tonnes`}
                        </dd>
                        <dt className="text-text-muted">Approved for</dt>
                        <dd className="text-text-secondary">
                          {entry.crops.length ? entry.crops.join(", ") : "no Swedish crop use recorded"}
                        </dd>
                        <dt className="text-text-muted">Status</dt>
                        <dd className="text-text-secondary">
                          {entry.in_kemi_cohort
                            ? "under Kemikalieinspektionen reevaluation since 2025-11-20"
                            : entry.efsa_confirmed
                              ? "EFSA degradation records already list TFA as a metabolite"
                              : "no regulator has published a TFA concern for this substance"}
                        </dd>
                      </dl>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-10 rounded-lg border border-hairline bg-page p-5">
          <h3 className="font-medium text-text-primary">What the shortlist is and is not</h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            A CF3 group means a substance <em>can</em> yield TFA. Whether it does depends on
            where that group sits and on degradation pathways this rule does not model, so the
            screen is built wide on purpose: {data.flagged - data.kemi_found} of the{" "}
            {data.flagged} carry no published TFA finding from any regulator. A bound that
            misses real cases is worthless, and one that includes some innocents is merely wide.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            Two checks, neither of them an input. Kemikalieinspektionen named six TFA-forming
            substances on 2025-11-20, and all {data.kemi_found}{" "}
            are here. Separately, EFSA&apos;s
            own degradation records already list TFA as a metabolite for flutolanil, which the
            rule also flags without being told.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            {data.fluorine_without_cf3} substances carry fluorine in some other arrangement,
            almost all of them difluoromethyl, and are excluded. Those degrade toward
            difluoroacetic acid, a related concern and a different compound. A further{" "}
            {data.unresolved} have no PubChem structure and are left out of the population
            rather than counted as clean.
          </p>
        </div>

        <p className="mt-6 text-xs leading-relaxed text-text-muted">
          Reproduce with <span className="font-mono">pipeline/35_run_tfa_screen.py</span>. The
          rule, the weights and the held-out cohort are in{" "}
          <a
            href="https://github.com/MartinBlomqvistDev/hazium/blob/main/src/hazium/screen/tfa.py"
            className="text-accent underline underline-offset-2"
          >
            screen/tfa.py
          </a>
          . Structures are cached in the repository, so the screen runs offline and scores the
          same molecules a reviewer can read. Generated {data.generated}.
        </p>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface p-4">
      <div className="tabular-nums text-2xl font-semibold text-text-primary">{value}</div>
      <div className="mt-1 text-xs leading-relaxed text-text-secondary">{label}</div>
    </div>
  );
}
