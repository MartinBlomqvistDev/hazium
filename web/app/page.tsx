import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import WhatWasBuilt from "@/components/WhatWasBuilt";
import Findings from "@/components/Findings";
import EvidenceMesh from "@/components/EvidenceMesh";
import OriginStory from "@/components/OriginStory";
import Principles from "@/components/Principles";
import Footer from "@/components/Footer";
import buildFactsData from "@/data/build.json";
import evidenceMeshData from "@/data/evidence_mesh.json";
import watchlistData from "@/data/watchlist.json";
import survivalData from "@/data/survival.json";
import tfaScreenData from "@/data/tfa_screen.json";
import type {
  BuildFacts,
  EvidenceMeshData,
  SurvivalData,
  TfaScreenData,
  WatchlistData,
} from "@/lib/types";

const buildFacts = buildFactsData as BuildFacts;
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
        <WhatWasBuilt facts={buildFacts} />
        <Findings screen={tfaScreen} watchlist={watchlist} />
        {/* Origin before mesh: the mesh closes on "this is the gap the project
            was built around", which only lands once the reader has been told
            what that gap is. Reversed, it asked for a callback to a story the
            page had not told yet. */}
        <OriginStory />
        <EvidenceMesh data={evidenceMesh} />
        <Principles />
      </main>
      <Footer />
    </div>
  );
}
