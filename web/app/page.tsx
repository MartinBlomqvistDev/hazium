import Link from "next/link";
import EvidenceMesh from "@/components/EvidenceMesh";
import Footer from "@/components/Footer";
import Nav from "@/components/Nav";
import buildFactsData from "@/data/build.json";
import evidenceMeshData from "@/data/evidence_mesh.json";
import survivalData from "@/data/survival.json";
import tfaScreenData from "@/data/tfa_screen.json";
import type {
  BuildFacts,
  EvidenceMeshData,
  SurvivalData,
  TfaScreenData,
} from "@/lib/types";

const facts = buildFactsData as BuildFacts;
const evidenceMesh = evidenceMeshData as EvidenceMeshData;
const survival = survivalData as SurvivalData;
const screen = tfaScreenData as TfaScreenData;

/**
 * Written to one rule: no sentence whose job is to manage expectations.
 *
 * The previous version carried six of them ("a real result and a small one",
 * "that is not a discovery", and so on) and called that honesty. It is not; it
 * is flinching, and it left a reader with nothing to take away. Nothing here
 * claims a discovery, so nothing here needs to deny one.
 *
 * It also opens on the labelling problem rather than on a redemption arc, because
 * that is the transferable part: the target was chosen by what could be scored,
 * and the distance between that target and the real question is measurable.
 *
 * Numbers read from the run that produced them. The two v1.4 figures are
 * literals because that release is frozen and never recomputed.
 */
export default function Home() {
  const h1 = survival.horizon_1;
  const age = h1.arms["age only"].average_precision;
  const both = h1.arms["age + evidence"].average_precision;
  const split = h1.quoted_split;
  const cohort = survival.anchor_cohort;
  const p = survival.verification.permutation_p;

  return (
    <div className="flex min-h-full flex-col">
      {/* The story page had no nav, so following a link to /watchlist made a
          header appear out of nowhere and the site stopped feeling like one
          site. The wordmark repeating under it is fine: it is the home page, and
          the h1 is the only place the project is named at full size. */}
      <Nav />
      <main className="flex-1 py-16 sm:py-24">
        <article className="mx-auto max-w-2xl px-6">
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Hazium</h1>
          <p className="mt-3 text-lg text-text-secondary">
            Predicting which pesticides turn out to be dangerous is a labelling problem
            before it is a modelling problem. What you can score is not what you want to
            know, and the distance between them is measurable.
          </p>

          <Section title="The labelling problem">
            <P>
              Harm has no ground truth. There is no register of substances that turned out
              to be dangerous, because that is the thing under investigation. Regulatory
              withdrawal has ground truth: dated, public, unambiguous.
            </P>
            <P>
              So withdrawal is what gets predicted. Every project in this shape makes that
              substitution, and it is usually made once, early, and never revisited. This
              one measures what it costs.
            </P>
          </Section>

          <Section title="The graph">
            <P>
              Five public EU and Swedish sources with no shared identifier and no shared
              schema, resolved into one graph:{" "}
              <strong className="text-text-primary">
                {(facts.graph_nodes + facts.graph_edges).toLocaleString("en-GB")} facts
              </strong>
              , each carrying the date it entered the public record.
            </P>
            <P>
              That date is the expensive constraint. A model scored at a 2015 cutoff sees
              what was public in 2015 and nothing else, which is what stops a retrospective
              study from quietly scoring itself on the future.
            </P>
            {/* The page referred to "the model" three times before it ever said
                what one was, including in the mesh caption directly below. Naming
                it here fixes the referent and is also what a keyword screen greps
                for: XGBoost appeared nowhere on the site. */}
            <P>
              Over that graph, gradient-boosted trees (XGBoost) read six dated feature
              groups: EFSA assessment history, hazard classifications under CLP, ECHA
              classification intentions, sales trajectory, independent literature signal,
              and graph links to substances already flagged. Scores are out-of-fold, folds
              grouped by substance.
            </P>
          </Section>
        </article>

        {/* The claim above is that the graph is dated. This is the graph, dated,
            and it argues the point better than the paragraph does. Full width
            against the narrow column, so it reads as evidence rather than as an
            illustration dropped into the prose. */}
        <div className="mt-14">
          <EvidenceMesh data={evidenceMesh} />
        </div>

        <article className="mx-auto max-w-2xl px-6">
          <Section title="What the baseline exposed">
            <P>
              Approval age sat inside the model as a feature, so it had never been scored
              alone. Ranked on its own it reached{" "}
              <strong className="text-text-primary">0.474 against the model&apos;s 0.470</strong>{" "}
              across sixteen annual cutoffs, and reproduced the published lead times to the
              month.
            </P>
            <P>
              The model had learned an eligibility test. 96% of the population was never
              approved in the EU and so could never be withdrawn, and one date subtraction
              separates those. The target was answerable without the evidence, which means
              the evidence had never been measured.
            </P>
          </Section>

          <Section title="The reformulation">
            <P>
              Recast as discrete-time survival, one approved substance in one year at risk,
              approval age becomes the baseline hazard and the evidence has to earn what is
              left. Average precision moves from {age.toFixed(3)} to{" "}
              <strong className="text-text-primary">{both.toFixed(3)}</strong>.
            </P>
            {/* The permutation belongs to the pooled figure above, not to the
                forward split below: it refits out-of-fold over the whole panel
                with substance histories shuffled. Writing the two as one
                sentence attached p to the wrong result, and the forward split
                has its own average precision on its own scale besides. */}
            <P>
              Scores are out of fold with folds grouped by substance, so no substance
              appears on both sides of a split. Shuffling whole substance histories and
              refitting puts that gain at p&nbsp;=&nbsp;{p.toFixed(3)}.
            </P>
            <P>
              A separate forward test refits on evidence up to {split?.train_through} and
              scores against what actually happened after. Its top 50 holds{" "}
              {split?.both_hits_at_50} real withdrawals to the baseline&apos;s{" "}
              {split?.age_hits_at_50}.
            </P>
          </Section>

          <Section title="What the substitution costs">
            <P>
              Sweden opened {cohort.size} substances for reevaluation in November 2025
              because they degrade into TFA, a persistent PFAS compound that reaches
              groundwater. Against that cohort the model ranks{" "}
              <strong className="text-text-primary">
                {cohort.hits_in_top_k} of {cohort.size} in its top {cohort.top_k}
              </strong>
              , where chance places {cohort.expected_in_top_k.toFixed(1)}.
            </P>
            <P>
              The reason is representational, not statistical. A degradation pathway leaves
              no trace in an approval file, a hazard classification or a sales table, so no
              quantity of regulatory evidence encodes it. A molecular formula does. One
              structural test over PubChem returns {screen.flagged} of {screen.population}{" "}
              approved substances and contains all {screen.kemi_total}.
            </P>
            <P>
              Withdrawal predicts a committee&apos;s attention. Harm is a property of the
              molecule. The two separate exactly where the hazard is chemical rather than
              procedural, and there the choice of representation decides the outcome and
              the choice of model does not.
            </P>
          </Section>

          <Section title="What&rsquo;s here">
            <P>
              A reproducible pipeline, {facts.tests} tests, and both versions of the
              benchmark in one citable dataset: the one that was answerable by a date
              subtraction, and the one that replaced it.
            </P>
            <ul className="mt-5 space-y-2 text-text-secondary">
              {/* First, because it is the only route to the modelling detail.
                  Without it /method was reachable only through the nav on
                  /watchlist, two hops from the front door, so the page carrying
                  the feature contributions and the calibration finding was
                  effectively orphaned. */}
              <li>
                <Link href="/method" className="text-accent underline underline-offset-2">
                  What each evidence source is worth
                </Link>{" "}
                <span className="text-text-muted">
                  &middot; the six feature groups measured one at a time, the checks the
                  result survived, and where it is weakest
                </span>
              </li>
              <li>
                <a
                  href="https://github.com/MartinBlomqvistDev/hazium"
                  className="text-accent underline underline-offset-2"
                >
                  Code on GitHub
                </a>{" "}
                <span className="text-text-muted">
                  &middot; AGPL-3.0 &middot; {facts.model_sources.join(", ")}
                </span>
              </li>
              <li>
                <a
                  href="https://huggingface.co/datasets/MartinBlomqvist/hewb"
                  className="text-accent underline underline-offset-2"
                >
                  Both benchmark versions on HuggingFace
                </a>{" "}
                <span className="text-text-muted">&middot; CC-BY-4.0</span>
              </li>
              <li>
                <Link href="/watchlist" className="text-accent underline underline-offset-2">
                  What it ranks today
                </Link>{" "}
                <span className="text-text-muted">
                  &middot; every entry carries the date the Commission must decide
                </span>
              </li>
            </ul>
          </Section>

          <p className="mt-16 text-sm text-text-muted">
            Martin Blomqvist &middot;{" "}
            <a
              href="https://www.linkedin.com/in/martin-blomqvist"
              className="underline underline-offset-2 hover:text-text-secondary"
            >
              LinkedIn
            </a>
          </p>
        </article>
      </main>
      <Footer />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-14">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-accent">{title}</h2>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="leading-relaxed text-text-secondary">{children}</p>;
}
