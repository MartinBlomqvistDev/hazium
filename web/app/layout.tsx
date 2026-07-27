import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Must match Vercel's primary domain, which is the apex: both the www form and
// the deployment URL redirect here. If the primary is ever switched, change this
// with it, because a canonical URL that disagrees with where visitors actually
// land is how link previews and search results drift apart.
const SITE_URL = "https://hazium.org";

// The title is what every shared link renders as, so it is where retired framing
// survives longest. Two have now been buried here: "early warning from public
// evidence", and then "risk screening", which still sold the project as a
// working instrument. It is a case study about evaluating one, which is a
// smaller and more defensible thing to be.
const TITLE = "Hazium: what you can score is not what you want to know";
const DESCRIPTION =
  "Predicting which pesticides turn out to be dangerous is a labelling problem before it is a modelling problem. A temporal knowledge graph over five public EU and Swedish sources, a target a date subtraction could answer, and what the substitution costs, measured against a cohort a regulator defined.";

export const metadata: Metadata = {
  // metadataBase makes every relative asset URL absolute, which is what link
  // previews need: without it the generated Open Graph image resolves against
  // the deployment URL rather than the domain, and shared links render bare.
  metadataBase: new URL(SITE_URL),
  title: {
    default: TITLE,
    // Sub-pages set only a plain string, so this keeps the brand on the end of
    // every tab without each page having to repeat it.
    template: "%s | Hazium",
  },
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    url: SITE_URL,
    siteName: "Hazium",
    type: "website",
    locale: "en_GB",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
