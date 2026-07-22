import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import SubstanceExplorer from "@/components/SubstanceExplorer";
import RankRace from "@/components/RankRace";
import substancesData from "@/data/substances.json";
import rankRaceData from "@/data/rank_race.json";
import substanceDetail from "@/data/substance_detail.json";
import type { RankRaceData, SubstanceDetailMap, SubstancesData } from "@/lib/types";

const data = substancesData as SubstancesData;
const rankRace = rankRaceData as RankRaceData;
const detail = substanceDetail as SubstanceDetailMap;

export const metadata = {
  title: "Explore the rankings | Hazium",
  description:
    "Watch the model's top-ranked substances shift between 2009 and 2024, then browse the full ranked population at the 2023 cutoff.",
};

export default function ExplorerPage() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <section className="border-b border-hairline">
          <div className="mx-auto max-w-5xl px-6 py-12">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              Substance explorer
            </h1>
            <p className="mt-4 max-w-2xl text-text-secondary">
              Every one of the{" "}
              <span className="text-text-primary">{data.population.toLocaleString()}</span>{" "}
              substances the model scored at the {data.cutoff} cutoff, ranked by
              regulatory risk using only evidence dated before it. Search, sort,
              and filter the whole population, not just the landmark cases.
            </p>
            <p className="mt-3 max-w-2xl text-sm text-text-muted">
              This is the model&apos;s ranking of past evidence, not a prediction
              of future bans. A high rank means the model found a substance&apos;s
              evidence profile similar to those that were later restricted; it is
              a research signal, not a regulatory judgement. HEWB v{data.hewb_version}.
            </p>
            <div className="mt-8">
              <SubstanceExplorer data={data} />
            </div>
          </div>
        </section>
        <section id="radar">
          <div className="mx-auto max-w-5xl px-6 py-14">
            <h2 className="text-3xl font-semibold tracking-tight">Risk radar over time</h2>
            <p className="mt-4 max-w-2xl text-text-secondary">
              The model&apos;s ten highest-risk substances at each annual cutoff, 2009 to
              2024. Press play to watch them rise and fall, or click any substance to follow
              its whole arc. Most were still approved at the time; the ones in red were later
              confirmed by a real EU ban, and a substance leaves the chart the year after it
              is banned.
            </p>
            <div className="mt-8 rounded-xl border border-hairline bg-surface p-5 sm:p-7">
              <RankRace data={rankRace} detail={detail} />
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </div>
  );
}
