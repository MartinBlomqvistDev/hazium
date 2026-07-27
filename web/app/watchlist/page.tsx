import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import Watchlist from "@/components/Watchlist";
import AnchorCase from "@/components/AnchorCase";
import PrecursorScreen from "@/components/PrecursorScreen";
import watchlistData from "@/data/watchlist.json";
import survivalData from "@/data/survival.json";
import tfaScreenData from "@/data/tfa_screen.json";
import type { SurvivalData, TfaScreenData, WatchlistData } from "@/lib/types";

const watchlist = watchlistData as WatchlistData;
const survival = survivalData as SurvivalData;
const tfaScreen = tfaScreenData as TfaScreenData;

const TITLE = "What it says about today";
const DESCRIPTION =
  "Substances approved in the EU right now: ranked for withdrawal risk with a decision deadline on each, and screened separately for the ability to form PFAS.";

export const metadata = {
  title: TITLE,
  description: DESCRIPTION,
  alternates: { canonical: "/watchlist" },
  openGraph: { title: `${TITLE} | Hazium`, description: DESCRIPTION, url: "/watchlist" },
  twitter: { title: `${TITLE} | Hazium`, description: DESCRIPTION },
};

export default function WatchlistPage() {
  return (
    <div className="flex min-h-full flex-col">
      <Nav />
      <main className="flex-1">
        <section className="border-b border-hairline">
          <div className="mx-auto max-w-3xl px-6 py-12">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              What it says about substances on the market today
            </h1>
            <p className="mt-4 text-text-secondary">
              Two lists over one set: the{" "}
              <strong className="text-text-primary">
                {survival.anchor_cohort.population} substances
              </strong>{" "}
              that hold an EU approval today and have not been withdrawn. One ranks them for
              withdrawal risk, the other screens them for PFAS formation, and fourteen
              substances appear on both.
            </p>

            <p className="mt-3 text-text-secondary">
              The screen covers {tfaScreen.population} of the{" "}
              {survival.anchor_cohort.population}. The remaining {tfaScreen.unresolved} have no
              molecular formula in PubChem to read, so they are neither flagged nor cleared.
            </p>
          </div>
        </section>
        <Watchlist data={watchlist} />
        <AnchorCase cohort={survival.anchor_cohort} screen={tfaScreen} />
        <PrecursorScreen data={tfaScreen} />
      </main>
      <Footer />
    </div>
  );
}
