import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import OriginStory from "@/components/OriginStory";
import WhatWasBuilt from "@/components/WhatWasBuilt";
import ResultSection from "@/components/ResultSection";
import HowItWorks from "@/components/HowItWorks";
import AnchorCase from "@/components/AnchorCase";
import Principles from "@/components/Principles";
import Footer from "@/components/Footer";
import EvidenceMesh from "@/components/EvidenceMesh";
import Watchlist from "@/components/Watchlist";
import hewbData from "@/data/hewb.json";
import capabilityData from "@/data/capability.json";
import substanceDetail from "@/data/substance_detail.json";
import evidenceMeshData from "@/data/evidence_mesh.json";
import watchlistData from "@/data/watchlist.json";
import survivalData from "@/data/survival.json";
import type {
  CapabilityData,
  EvidenceMeshData,
  HewbData,
  SubstanceDetailMap,
  SurvivalData,
  WatchlistData,
} from "@/lib/types";

const data = hewbData as HewbData;
const capability = capabilityData as CapabilityData;
const detail = substanceDetail as SubstanceDetailMap;
const evidenceMesh = evidenceMeshData as EvidenceMeshData;
const watchlist = watchlistData as WatchlistData;
const survival = survivalData as SurvivalData;

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <Hero survival={survival} />
        <WhatWasBuilt />
        <OriginStory />
        <HowItWorks survival={survival} />
        <ResultSection data={data} capability={capability} detail={detail} />
        <AnchorCase cohort={survival.anchor_cohort} />
        <EvidenceMesh data={evidenceMesh} />
        <Watchlist data={watchlist} />
        <Principles />
      </main>
      <Footer />
    </div>
  );
}
