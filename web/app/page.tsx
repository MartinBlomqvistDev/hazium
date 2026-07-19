import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import OriginStory from "@/components/OriginStory";
import ResultSection from "@/components/ResultSection";
import HowItWorks from "@/components/HowItWorks";
import Principles from "@/components/Principles";
import Footer from "@/components/Footer";
import RankRace from "@/components/RankRace";
import hewbData from "@/data/hewb.json";
import capabilityData from "@/data/capability.json";
import substanceDetail from "@/data/substance_detail.json";
import rankRaceData from "@/data/rank_race.json";
import type { CapabilityData, HewbData, RankRaceData, SubstanceDetailMap } from "@/lib/types";

const data = hewbData as HewbData;
const capability = capabilityData as CapabilityData;
const detail = substanceDetail as SubstanceDetailMap;
const rankRace = rankRaceData as RankRaceData;

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <Hero data={data} />
        <OriginStory />
        <ResultSection data={data} capability={capability} detail={detail} />
        <section id="radar" className="border-b border-hairline bg-surface/40">
          <div className="mx-auto max-w-3xl px-6 py-16">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">
              Risk radar over time
            </h2>
            <p className="mt-4 text-text-secondary">
              The model&apos;s top 14 highest-risk substances at each annual cutoff,
              2009 to 2024. Press play to watch them rise and fall. These are the
              model&apos;s risk ranking, and most were still approved at the time;
              the ones in red were later confirmed by a real EU ban, and a substance
              leaves the chart the year after it is banned.
            </p>
            <div className="mt-8 rounded-xl border border-hairline bg-surface p-5 sm:p-7">
              <RankRace data={rankRace} />
            </div>
          </div>
        </section>
        <HowItWorks />
        <Principles />
      </main>
      <Footer />
    </div>
  );
}
