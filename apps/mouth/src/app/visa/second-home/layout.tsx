import { I18nProvider } from "@/i18n";

export default function SecondHomeLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Route-level provider — the /visa segment layout has no I18nProvider
  // ancestor. lint_i18n_providers contract: the provider must live in the
  // calling file itself or in an ancestor layout.tsx. Missing keys in fr/ru
  // fall back to EN (src/i18n/index.tsx).
  return <I18nProvider>{children}</I18nProvider>;
}
