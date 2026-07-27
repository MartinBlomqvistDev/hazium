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

export const metadata = {
  title: "What it says about today | Hazium",
  description:
    "Substances approved in the EU right now: ranked for withdrawal risk with a decision deadline on each, and screened separately for the ability to form PFAS.",
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
              Two lists, answering two different questions about the same population. One asks
              which approved pesticides the EU will withdraw, and is produced by a model. The
              other asks which of them break down into PFAS, and is produced by a rule over their
              molecular structure. Fourteen substances appear on both.
            </p>
            <p className="mt-3 text-sm text-text-muted">
              Nothing here has been checked against anything, because the future it describes has
              not happened. What makes it falsifiable is that every EU approval carries an expiry
              date on which the Commission has to decide.
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
