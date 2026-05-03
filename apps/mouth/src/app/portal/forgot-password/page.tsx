"use client";

import Link from "next/link";
import { Cormorant_Garamond } from "next/font/google";
import { I18nProvider, useTranslation } from "@/i18n";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["300", "400", "700"],
  display: "swap",
});

function ForgotPasswordInner() {
  const { t } = useTranslation();
  const subject = encodeURIComponent("Portal Access Recovery");
  const body = encodeURIComponent(
    "Hi team,\n\nI need help recovering access to my Bali Zero client portal.\n\nRegistered email: ",
  );
  const mailto = `mailto:team@balizero.com?subject=${subject}&body=${body}`;
  return (
    <main className="min-h-screen bg-black text-[#f0ece4] flex items-center justify-center px-6">
      <div className="max-w-md w-full">
        <h1
          className={`${cormorant.className} text-3xl md:text-4xl font-light tracking-[0.06em] mb-4 text-white`}
        >
          {t("portal.forgot_password.title")}
        </h1>
        <p className="text-sm text-[#c9a96e]/70 mb-8">
          {t("portal.forgot_password.sent")}
        </p>
        <a
          href={mailto}
          className="block w-full text-center py-4 rounded-xl bg-gradient-to-br from-[#d9bd7a] to-[#a07838] text-black font-bold uppercase tracking-[0.08em] shadow-[0_4px_24px_rgba(201,169,110,0.3)]"
        >
          Write to the team
        </a>
        <Link
          href="/portal/login-upgraded"
          className="block mt-6 text-center text-xs text-[#c9a96e]/60 hover:text-[#c9a96e] uppercase tracking-[2px]"
        >
          ← Back to login
        </Link>
      </div>
    </main>
  );
}

export default function ForgotPasswordPage() {
  return (
    <I18nProvider>
      <ForgotPasswordInner />
    </I18nProvider>
  );
}
