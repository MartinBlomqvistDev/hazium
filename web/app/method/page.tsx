import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import HowItWorks from "@/components/HowItWorks";
import ResultSection from "@/components/ResultSection";
import EvidenceMesh from "@/components/EvidenceMesh";
import hewbData from "@/data/hewb.json";
import capabilityData from "@/data/capability.json";
import substanceDetail from "@/data/substance_detail.json";
import evidenceMeshData from "@/data/evidence_mesh.json";
import survivalData from "@/data/survival.json";
import type {
  CapabilityData,
  EvidenceMeshData,
  HewbData,
  SubstanceDetailMap,
  SurvivalData,
} from "@/lib/types";

const data = hewbData as HewbData;
const capability = capabilityData as CapabilityData;
const detail = substanceDetail as SubstanceDetailMap;
const evidenceMesh = evidenceMeshData as EvidenceMeshData;
const survival = survivalData as SurvivalData;

export const metadata = {
  title: "Method | Hazium",
  description:
    "The six feature groups, what each is worth, the trivial baseline that beat the model, and the benchmark the result is measured against.",
};

export default function MethodPage() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <section className="border-b border-hairline">
          <div className="mx-auto max-w-3xl px-6 py-12">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              How the ranking is built, and what it is measured against
            </h1>
            <p className="mt-4 text-text-secondary">
              Two things decide whether a ranking like this means anything: what the model reads,
              and what it is compared against. This page covers both, including the baseline that
              beat an earlier version of the model outright.
            </p>
          </div>
        </section>
        <HowItWorks survival={survival} />
        <ResultSection data={data} capability={capability} detail={detail} />
        <EvidenceMesh data={evidenceMesh} />
      </main>
      <Footer />
    </div>
  );
}
