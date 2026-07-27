import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import WhatWasBuilt from "@/components/WhatWasBuilt";
import Findings from "@/components/Findings";
import EvidenceMesh from "@/components/EvidenceMesh";
import OriginStory from "@/components/OriginStory";
import Principles from "@/components/Principles";
import Footer from "@/components/Footer";
import evidenceMeshData from "@/data/evidence_mesh.json";
import watchlistData from "@/data/watchlist.json";
import survivalData from "@/data/survival.json";
import tfaScreenData from "@/data/tfa_screen.json";
import type {
  EvidenceMeshData,
  SurvivalData,
  TfaScreenData,
  WatchlistData,
} from "@/lib/types";

const evidenceMesh = evidenceMeshData as EvidenceMeshData;
const watchlist = watchlistData as WatchlistData;
const survival = survivalData as SurvivalData;
const tfaScreen = tfaScreenData as TfaScreenData;

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <Hero survival={survival} screen={tfaScreen} />
        <WhatWasBuilt />
        <Findings survival={survival} screen={tfaScreen} watchlist={watchlist} />
        <EvidenceMesh data={evidenceMesh} />
        <OriginStory />
        <Principles />
      </main>
      <Footer />
    </div>
  );
}
