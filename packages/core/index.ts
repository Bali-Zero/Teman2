// Component exports
export { BZLogo, type BZLogoVariant } from "./components/BZLogo";
export { NavShell, type NavItem } from "./components/NavShell";
export { WhatsAppFAB } from "./components/WhatsAppFAB";
export {
  ProgressRing,
  type ProgressRingProps,
} from "./components/ProgressRing";
export {
  DeadlineBadge,
  type DeadlineBadgeProps,
} from "./components/DeadlineBadge";
export {
  ThemeProvider,
  ThemeScope,
  useTheme,
  type Theme,
  type Funnel,
} from "./components/ThemeProvider";
export { TrustBand, type TrustBandProps } from "./components/TrustBand";
export { CTAHandoff, type CTAHandoffProps } from "./components/CTAHandoff";
export { FunnelFrame, type FunnelFrameProps } from "./components/FunnelFrame";
export {
  CommandPalette,
  type CommandAction,
} from "./components/CommandPalette";

// Font exports
export { inter } from "./fonts/inter";

// Utility exports (pre-existing)
export * from "./utils";
export * from "./auth";

// Analytics exports
export * from "./analytics";
export {
  MatterCard,
  type MatterCardProps,
  type MatterType,
} from "./components/MatterCard";
export { ContextPanel, type ContextTab } from "./components/ContextPanel";

// Funnel apps (visa/kbli/tax/zoning interactive apps)
export * from "./components/apps";
export { useFunnelApp } from "./analytics/useFunnelApp";
