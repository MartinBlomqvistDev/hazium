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
const TITLE = "Hazium: early warning from public evidence";
const DESCRIPTION =
  "A temporally-aware knowledge graph over EU pesticide regulation, hazard classification, and scientific literature, evaluated against a versioned, falsifiable early-warning benchmark (HEWB).";

export const metadata: Metadata = {
  // metadataBase makes every relative asset URL absolute, which is what link
  // previews need: without it the generated Open Graph image resolves against
  // the deployment URL rather than the domain, and shared links render bare.
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
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
