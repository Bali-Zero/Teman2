"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { Check, X, Info, Phone } from "lucide-react";
import type { ServicePackage } from "@/data/services_data";

// ServiceData without icon (React component cannot be serialized)
type ServiceDataWithoutIcon = Omit<
  import("@/data/services_data").ServiceData,
  "icon"
>;

interface ServicePricingProps {
  service: ServiceDataWithoutIcon;
  slug: string;
}

// Get visa package color based on type (KITAS/KITAP = orange, Visit = blue)
function getVisaPackageColor(name: string): {
  bg: string;
  border: string;
  badge: string;
} {
  const lowerName = name.toLowerCase();
  // KITAS, KITAP, Working, Freelance, Investor KITAS, Spouse, Dependent, Retirement KITAS = Orange
  if (
    lowerName.includes("kitas") ||
    lowerName.includes("kitap") ||
    lowerName.includes("working") ||
    lowerName.includes("freelance") ||
    lowerName.includes("spouse") ||
    lowerName.includes("dependent") ||
    lowerName.includes("retirement") ||
    lowerName.includes("investor kitas")
  ) {
    return {
      bg: "bg-orange-500/20",
      border: "border-orange-500/40 hover:border-orange-400",
      badge: "bg-orange-500",
    };
  }
  // Visit visas (C, D series) = Blue
  return {
    bg: "bg-sky-500/20",
    border: "border-sky-500/40 hover:border-sky-400",
    badge: "bg-sky-500",
  };
}

export default function ServicePricing({ service, slug }: ServicePricingProps) {
  const [selectedPackage, setSelectedPackage] =
    React.useState<ServicePackage | null>(null);

  // Close modal on escape key
  React.useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedPackage(null);
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  return (
    <>
      {/* Pricing Table */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <h2 className="font-serif text-2xl text-white mb-8">Pricing</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {service.packages.map((pkg) => {
              // Use visa colors for visa service
              const visaColors =
                slug === "visa" ? getVisaPackageColor(pkg.name) : null;

              return (
                <div
                  key={pkg.name}
                  className={`rounded-xl border p-6 cursor-pointer transition-all hover:scale-[1.02] ${
                    slug === "visa" && visaColors
                      ? `${visaColors.bg} ${visaColors.border}`
                      : pkg.popular
                        ? "border-accent-blue-editorial bg-accent-blue-editorial/10 hover:border-accent-blue-editorial"
                        : "border-white/10 bg-[#0a2540] hover:border-white/30"
                  }`}
                  onClick={() => setSelectedPackage(pkg)}
                >
                  {pkg.popular && (
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-white text-xs font-medium mb-4 ${
                        slug === "visa" && visaColors
                          ? visaColors.badge
                          : "bg-accent-blue-editorial"
                      }`}
                    >
                      Most Popular
                    </span>
                  )}
                  <h3 className="text-white font-medium text-lg mb-2">
                    {pkg.name}
                  </h3>
                  <p className="text-white/50 text-sm mb-4">
                    {pkg.description}
                  </p>

                  <div className="mb-6">
                    {pkg.price === "Contact" ? (
                      <span className="text-2xl font-bold text-accent-blue-editorial">
                        Contact for quote
                      </span>
                    ) : (
                      <>
                        <span className="text-3xl font-bold text-white">
                          {pkg.price}
                        </span>
                        <span className="text-white/40 text-sm ml-2">IDR</span>
                      </>
                    )}
                  </div>

                  <ul className="space-y-3 mb-6">
                    {pkg.features.map((feature, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-white/70 text-sm"
                      >
                        <Check className="w-4 h-4 text-[#22c55e] mt-0.5 flex-shrink-0" />
                        {feature}
                      </li>
                    ))}
                  </ul>

                  <button
                    className={`flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg font-medium transition-colors ${
                      slug === "visa" && visaColors
                        ? `${visaColors.badge} text-white hover:opacity-90`
                        : pkg.popular
                          ? "bg-accent-blue-editorial text-white hover:bg-[#1a41cc]"
                          : "border border-white/20 text-white hover:bg-white/10"
                    }`}
                  >
                    <Info className="w-4 h-4" />
                    More Details
                  </button>
                </div>
              );
            })}
          </div>

          <p className="text-white/40 text-sm text-center mt-8">
            * All-inclusive pricing. No hidden fees.
          </p>
        </div>
      </section>

      {/* Modal Popup */}
      {selectedPackage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          onClick={() => setSelectedPackage(null)}
        >
          <div
            className="relative w-full max-w-lg bg-[#0a2540] rounded-2xl border border-white/10 shadow-2xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close Button */}
            <button
              onClick={() => setSelectedPackage(null)}
              className="absolute top-4 right-4 p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
            >
              <X className="w-5 h-5 text-white" />
            </button>

            {/* Modal Content */}
            <div className="p-8">
              {/* Header */}
              {selectedPackage.popular && (
                <span className="inline-block px-3 py-1 rounded-full bg-accent-blue-editorial text-white text-xs font-medium mb-4">
                  Most Popular
                </span>
              )}
              <h2 className="font-serif text-2xl text-white mb-2">
                {selectedPackage.name}
              </h2>
              <p className="text-white/60 mb-6">
                {selectedPackage.description}
              </p>

              {/* Price */}
              <div className="bg-[#051C2C] rounded-xl p-4 mb-6">
                {selectedPackage.price === "Contact" ? (
                  <span className="text-2xl font-bold text-accent-blue-editorial">
                    Contact for quote
                  </span>
                ) : (
                  <div>
                    <span className="text-3xl font-bold text-white">
                      {selectedPackage.price}
                    </span>
                    <span className="text-white/40 text-sm ml-2">IDR</span>
                    <p className="text-[#22c55e] text-sm mt-1">
                      All-inclusive pricing
                    </p>
                  </div>
                )}
              </div>

              {/* Features */}
              <h3 className="text-white font-medium mb-3">What's Included:</h3>
              <ul className="space-y-3 mb-6">
                {selectedPackage.features.map((feature, i) => (
                  <li key={i} className="flex items-start gap-3 text-white/80">
                    <Check className="w-5 h-5 text-[#22c55e] mt-0.5 flex-shrink-0" />
                    {feature}
                  </li>
                ))}
              </ul>

              {/* Additional Info */}
              <div className="bg-[#051C2C] rounded-xl p-4 mb-6">
                <h4 className="text-white/60 text-sm uppercase tracking-wider mb-2">
                  Our Service Includes:
                </h4>
                <ul className="text-white/70 text-sm space-y-1">
                  <li>• Document preparation & review</li>
                  <li>• Government submission & liaison</li>
                  <li>• Status tracking & updates</li>
                  <li>• Dedicated support throughout</li>
                </ul>
              </div>

              {/* WhatsApp CTA */}
              <Link
                href={`https://wa.me/628213107363?text=${encodeURIComponent(`Hi, I'm interested in ${selectedPackage.name}. Can you help me?`)}`}
                target="_blank"
                className="flex items-center justify-center gap-2 w-full px-6 py-4 rounded-xl bg-[#25D366] text-white font-medium hover:bg-[#20BD5A] transition-colors mb-3"
              >
                <Phone className="w-5 h-5" />
                Chat on WhatsApp
              </Link>

              <Link
                href="/chat"
                className="flex items-center justify-center gap-2 w-full px-6 py-3 rounded-xl border border-white/20 text-white font-medium hover:bg-white/10 transition-colors"
              >
                <Image
                  src="/assets/logo/zantara-lotus.png"
                  alt="Zantara Lotus Logo"
                  width={60}
                  height={60}
                />
                Ask Zantara AI
              </Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
