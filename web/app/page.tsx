import Nav from "@/components/Nav";
import Hero from "@/components/Hero";
import OriginStory from "@/components/OriginStory";
import ResultSection from "@/components/ResultSection";
import HowItWorks from "@/components/HowItWorks";
import Principles from "@/components/Principles";
import Footer from "@/components/Footer";
import hewbData from "@/data/hewb.json";
import type { HewbData } from "@/lib/types";

const data = hewbData as HewbData;

export default function Home() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <Hero data={data} />
        <OriginStory />
        <ResultSection data={data} />
        <HowItWorks />
        <Principles />
      </main>
      <Footer />
    </div>
  );
}
