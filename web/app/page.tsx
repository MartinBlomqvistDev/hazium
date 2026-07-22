import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import OriginStory from "@/components/OriginStory";
import ResultSection from "@/components/ResultSection";
import HowItWorks from "@/components/HowItWorks";
import Principles from "@/components/Principles";
import Footer from "@/components/Footer";
import EvidenceMesh from "@/components/EvidenceMesh";
import hewbData from "@/data/hewb.json";
import capabilityData from "@/data/capability.json";
import substanceDetail from "@/data/substance_detail.json";
import evidenceMeshData from "@/data/evidence_mesh.json";
import type {
  CapabilityData,
  EvidenceMeshData,
  HewbData,
  SubstanceDetailMap,
} from "@/lib/types";

const data = hewbData as HewbData;
const capability = capabilityData as CapabilityData;
const detail = substanceDetail as SubstanceDetailMap;
const evidenceMesh = evidenceMeshData as EvidenceMeshData;

// The ten benchmark EU bans (fluazinam is the held-out north-star, not one of them).
// "Ahead" means flagged before the EU's own first regulatory action, which is the
// stricter bar the capability timeline reports, not merely before the final ban.
const benchmarkBans = capability.landmarks.filter((l) => !l.held_out);
const flaggedAhead = benchmarkBans.filter(
  (l) => l.outcome === "clean_lead" || l.outcome === "ahead_of_eu_action",
).length;

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <Hero data={data} flaggedAhead={flaggedAhead} banTotal={benchmarkBans.length} />
        <OriginStory />
        <HowItWorks />
        <ResultSection data={data} capability={capability} detail={detail} />
        <EvidenceMesh data={evidenceMesh} />
        <Principles />
      </main>
      <Footer />
    </div>
  );
}
