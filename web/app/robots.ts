import type { MetadataRoute } from "next";

/**
 * Nothing here is private, so everything is crawlable.
 *
 * The file exists mainly to carry the sitemap pointer: without it a crawler
 * finds the landing page and has to guess that three more routes exist, and
 * two of those are the ones worth finding.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: "https://hazium.org/sitemap.xml",
    host: "https://hazium.org",
  };
}
