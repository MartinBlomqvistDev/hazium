import type { MetadataRoute } from "next";
import watchlist from "@/data/watchlist.json";

/**
 * Four routes, with `lastModified` taken from the data that drives them rather
 * than from the build clock, so a rebuild that changed nothing does not claim
 * the content is new.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const dataDate = new Date(watchlist.generated);
  return [
    { url: "https://hazium.org", lastModified: dataDate, changeFrequency: "monthly", priority: 1 },
    {
      url: "https://hazium.org/watchlist",
      lastModified: dataDate,
      changeFrequency: "monthly",
      priority: 0.9,
    },
    {
      url: "https://hazium.org/method",
      lastModified: dataDate,
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: "https://hazium.org/explorer",
      lastModified: dataDate,
      changeFrequency: "monthly",
      priority: 0.6,
    },
  ];
}
