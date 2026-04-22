/**
 * Social UTM builder — enforced attribution for all social CTAs.
 *
 * Every link posted to Instagram/LinkedIn/TikTok/Threads/YouTube/X/blog
 * MUST route through this helper so the CRM can attribute leads to the
 * right social channel. Without enforcement, CTAs go uninstrumented and
 * GA4 shows "(direct) / (none)" — which is exactly what CRO audit
 * 2026-04-19 found.
 *
 * Baseline state (2026-04-22): social_90d = 5 / 324 leads (1.5%). Most
 * of that "5" is x_social_listening (a fluke), not intentional tracked
 * traffic. This builder is the foundation for lifting that number.
 *
 * Usage:
 *   import { buildSocialCTA } from "@/lib/social-utm";
 *
 *   const href = buildSocialCTA({
 *     baseUrl: "https://visa.balizero.com/",
 *     channel: "instagram",
 *     contentId: "post-20260422-kitas",
 *     campaign: "kitas-apr26",
 *   });
 *   // → https://visa.balizero.com/?utm_source=instagram&utm_medium=social&
 *   //    utm_campaign=kitas-apr26&utm_content=post-20260422-kitas
 *
 * Throws if any required field is missing/empty — don't want silent
 * degradation.
 */

export type SocialChannel =
  | "instagram"
  | "linkedin"
  | "tiktok"
  | "threads"
  | "twitter"
  | "x"
  | "youtube"
  | "facebook"
  | "newsletter"
  | "blog"
  | "podcast"
  | "quora"
  | "reddit";

// Canonical medium per channel family — hard-coded so analysts see
// consistent breakdowns in GA4 acquisition reports.
const CHANNEL_MEDIUM: Record<SocialChannel, string> = {
  instagram: "social",
  linkedin: "social",
  tiktok: "social",
  threads: "social",
  twitter: "social",
  x: "social",
  youtube: "social",
  facebook: "social",
  newsletter: "email",
  blog: "referral",
  podcast: "referral",
  quora: "referral",
  reddit: "referral",
};

export interface SocialCTAParams {
  baseUrl: string;
  channel: SocialChannel;
  contentId: string; // unique per post/video/episode
  campaign: string; // e.g. "kitas-apr26" — consistent per campaign
  term?: string; // optional, usually a keyword/topic
}

export function buildSocialCTA(params: SocialCTAParams): string {
  const { baseUrl, channel, contentId, campaign, term } = params;

  if (!baseUrl) throw new Error("buildSocialCTA: baseUrl is required");
  if (!channel) throw new Error("buildSocialCTA: channel is required");
  if (!contentId || contentId.trim() === "") {
    throw new Error("buildSocialCTA: contentId is required (non-empty)");
  }
  if (!campaign || campaign.trim() === "") {
    throw new Error("buildSocialCTA: campaign is required (non-empty)");
  }

  const medium = CHANNEL_MEDIUM[channel];
  if (!medium) {
    throw new Error(`buildSocialCTA: unknown channel "${channel}"`);
  }

  const url = new URL(baseUrl);
  url.searchParams.set("utm_source", channel);
  url.searchParams.set("utm_medium", medium);
  url.searchParams.set("utm_campaign", campaign);
  url.searchParams.set("utm_content", contentId);
  if (term) url.searchParams.set("utm_term", term);

  return url.toString();
}
