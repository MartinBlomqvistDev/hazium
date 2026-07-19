import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import OriginStory from "@/components/OriginStory";
import ResultSection from "@/components/ResultSection";
import HowItWorks from "@/components/HowItWorks";
import Principles from "@/components/Principles";
import Footer from "@/components/Footer";
import hewbData from "@/data/hewb.json";
import capabilityData from "@/data/capability.json";
import type { CapabilityData, HewbData } from "@/lib/types";

const data = hewbData as HewbData;
const capability = capabilityData as CapabilityData;

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <Hero data={data} />
        <OriginStory />
        <ResultSection data={data} capability={capability} />
        <HowItWorks />
        <Principles />
      </main>
      <Footer />
    </div>
  );
}
