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

// "Early warning from public evidence" was the old framing and it outlived the
// claim: the withdrawal model turned out to be measuring seniority as much as
// foresight, and the site says so throughout. The title is what every shared
// link renders as, so it was the last place the retired wording survived.
const TITLE = "Hazium: public-data risk screening for EU pesticides";
const DESCRIPTION =
  "A temporally-aware knowledge graph over EU pesticide regulation, hazard classification and scientific literature. Ranks approved substances for withdrawal risk against a versioned benchmark, and screens the same population for PFAS formation by molecular structure.";

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
