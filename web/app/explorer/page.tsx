import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import SubstanceExplorer from "@/components/SubstanceExplorer";
import substancesData from "@/data/substances.json";
import type { SubstancesData } from "@/lib/types";

const data = substancesData as SubstancesData;

export const metadata = {
  title: "Substance explorer — Hazium",
  description:
    "Browse the model's regulatory-risk ranking of every EU pesticide active substance at the 2023 cutoff.",
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
      </main>
      <Footer />
    </div>
  );
}
