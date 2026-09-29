"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import { Check, Info, Phone } from "lucide-react";
import type { ServicePackage } from "@/data/services_data";
import { WhatsAppLeadButton } from "@/components/lead/WhatsAppLeadButton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  usePricingData,
  useTierFloorPricingData,
} from "@/hooks/usePricingData";
import { R19_VARS } from "@/components/r19/presentation";

// ServiceData without icon (React component cannot be serialized)
type ServiceDataWithoutIcon = Omit<
  import("@/data/services_data").ServiceData,
  "icon"
>;

interface ServicePricingProps {
  service: ServiceDataWithoutIcon;
  slug: string;
}

/**
 * Resolve only an exact PricingTool identity. Static package text is never a
 * price authority; a missing or malformed row becomes contact-required.
 */
function usePackagePrice(pkg: ServicePackage): string {
  const { price: livePrice } = usePricingData(
    pkg.livePriceKey ?? null,
    pkg.livePriceCategory ?? null,
  );
  const { price: floorPrice } = useTierFloorPricingData(
    pkg.livePriceFloorKeys ? (pkg.livePriceCategory ?? null) : null,
    pkg.livePriceFloorKeys ?? null,
  );
  if (pkg.livePriceFloorKeys) {
    if (!floorPrice) return "Contact";
    const unit = pkg.livePriceFloorUnit ? `/${pkg.livePriceFloorUnit}` : "";
    return `from ${floorPrice}${unit}`;
  }
  return livePrice ?? "Contact";
}

function PriceValue({
  pkg,
  variant,
}: {
  pkg: ServicePackage;
  variant: "card" | "modal";
}) {
  const price = usePackagePrice(pkg);

  if (price === "Contact") {
    return (
      <span
        className="text-2xl font-medium"
        style={{ color: "var(--r19-copper)" }}
      >
        Contact for quote
      </span>
    );
  }

  const amount = (
    <span
      className="text-3xl font-medium"
      style={{ color: "var(--text-primary)" }}
    >
      {price}
    </span>
  );

  if (variant === "card") {
    return amount;
  }

  return (
    <div>
      {amount}
      <p className="text-sm mt-1" style={{ color: "var(--r19-copper)" }}>
        All-inclusive pricing
      </p>
    </div>
  );
}

export default function ServicePricing({ service, slug }: ServicePricingProps) {
  const [selectedPackage, setSelectedPackage] =
    React.useState<ServicePackage | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = React.useState(false);
  const dialogTitleRef = React.useRef<HTMLHeadingElement>(null);
  const dialogTriggerRef = React.useRef<HTMLButtonElement>(null);

  return (
    <Dialog open={isDetailsOpen} onOpenChange={setIsDetailsOpen}>
      {/* Pricing Table */}
      <section style={{ borderBottom: "1px solid var(--border-subtle)" }}>
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <h2
            className="tracking-tight mb-8"
            style={{
              fontFamily: "var(--font-serif)",
              fontWeight: 500,
              fontSize: "clamp(22px, 2.2vw, 28px)",
              color: "var(--text-primary)",
            }}
          >
            Pricing
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {service.packages.map((pkg) => {
              return (
                <div
                  key={pkg.name}
                  data-testid="public-service-price-card"
                  data-pricing-category={pkg.livePriceCategory}
                  data-pricing-key={pkg.livePriceKey}
                  className="rounded-xl border p-6 transition-all hover:scale-[1.02]"
                  style={{
                    background: "var(--r19-surface)",
                    borderColor: pkg.popular
                      ? "var(--r19-copper)"
                      : "var(--border-subtle)",
                  }}
                >
                  {pkg.popular && (
                    <span
                      className="inline-block px-3 py-1 rounded-full text-xs font-medium mb-4"
                      style={{
                        background: "var(--r19-copper)",
                        color: "var(--r19-cta-ink, #fff)",
                      }}
                    >
                      Most Popular
                    </span>
                  )}
                  <h3
                    className="font-medium text-lg mb-2"
                    style={{ color: "var(--text-primary)" }}
                  >
                    {pkg.name}
                  </h3>
                  <p
                    className="text-sm mb-4"
                    style={{ color: "var(--text-tertiary)" }}
                  >
                    {pkg.description}
                  </p>

                  <div className="mb-6">
                    <PriceValue pkg={pkg} variant="card" />
                  </div>

                  <ul className="space-y-3 mb-6">
                    {pkg.features.map((feature, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm"
                        style={{ color: "var(--text-secondary)" }}
                      >
                        <Check
                          className="w-4 h-4 mt-0.5 flex-shrink-0"
                          style={{ color: "var(--r19-copper)" }}
                        />
                        {feature}
                      </li>
                    ))}
                  </ul>

                  <DialogTrigger asChild>
                    <button
                      type="button"
                      onClick={(event) => {
                        dialogTriggerRef.current = event.currentTarget;
                        setSelectedPackage(pkg);
                      }}
                      className="flex items-center justify-center gap-2 w-full px-4 py-3 rounded-lg font-medium transition-colors"
                      style={
                        pkg.popular
                          ? {
                              background: "var(--r19-copper)",
                              color: "var(--r19-cta-ink, #fff)",
                            }
                          : {
                              border: "1px solid var(--r19-line-strong)",
                              color: "var(--text-primary)",
                            }
                      }
                    >
                      <Info className="w-4 h-4" aria-hidden="true" />
                      More Details
                    </button>
                  </DialogTrigger>
                </div>
              );
            })}
          </div>

          <p
            className="text-sm text-center mt-8"
            style={{ color: "var(--text-tertiary)" }}
          >
            * All-inclusive pricing. No hidden fees.
          </p>
        </div>
      </section>

      {/* Modal Popup */}
      {selectedPackage && (
        <DialogContent
          className="max-h-[90vh] overflow-y-auto p-0"
          style={{
            // Radix portals DialogContent to document.body, outside the
            // R19Presentation wrapper that would otherwise supply these
            // vars (see R19_VARS's own "also applied to the Radix portal"
            // comment) — re-declare them locally so the modal never falls
            // back to the app's global (dark) root values.
            ...R19_VARS,
            border: "1px solid var(--border-subtle)",
            background: "var(--r19-paper)",
            color: "var(--text-primary)",
          }}
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            dialogTitleRef.current?.focus();
          }}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            dialogTriggerRef.current?.focus();
          }}
        >
          <div className="p-8">
            {/* Header */}
            {selectedPackage.popular && (
              <span
                className="inline-block px-3 py-1 rounded-full text-xs font-medium mb-4"
                style={{
                  background: "var(--r19-copper)",
                  color: "var(--r19-cta-ink, #fff)",
                }}
              >
                Most Popular
              </span>
            )}
            <DialogTitle
              ref={dialogTitleRef}
              tabIndex={-1}
              className="tracking-tight mb-2 outline-none"
              style={{
                fontFamily: "var(--font-serif)",
                fontWeight: 500,
                fontSize: "24px",
                color: "var(--text-primary)",
              }}
            >
              {selectedPackage.name}
            </DialogTitle>
            <DialogDescription
              className="mb-6"
              style={{ color: "var(--text-secondary)" }}
            >
              {selectedPackage.description}
            </DialogDescription>

            {/* Price */}
            <div
              className="rounded-xl p-4 mb-6"
              style={{
                background: "var(--r19-surface)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <PriceValue pkg={selectedPackage} variant="modal" />
            </div>

            {/* Features */}
            <h3
              className="font-medium mb-3"
              style={{ color: "var(--text-primary)" }}
            >
              What&apos;s Included:
            </h3>
            <ul className="space-y-3 mb-6">
              {selectedPackage.features.map((feature, i) => (
                <li
                  key={i}
                  className="flex items-start gap-3"
                  style={{ color: "var(--text-secondary)" }}
                >
                  <Check
                    className="w-5 h-5 mt-0.5 flex-shrink-0"
                    style={{ color: "var(--r19-copper)" }}
                  />
                  {feature}
                </li>
              ))}
            </ul>

            {/* Additional Info */}
            <div
              className="rounded-xl p-4 mb-6"
              style={{
                background: "var(--r19-surface)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <h4
                className="text-sm uppercase tracking-wider mb-2"
                style={{ color: "var(--text-tertiary)" }}
              >
                Our Service Includes:
              </h4>
              <ul
                className="text-sm space-y-1"
                style={{ color: "var(--text-secondary)" }}
              >
                <li>• Document preparation & review</li>
                <li>• Government submission & liaison</li>
                <li>• Status tracking & updates</li>
                <li>• Dedicated support throughout</li>
              </ul>
            </div>

            {/* WhatsApp CTA — brand green kept as-is; guarded by
                src/app/whatsapp-ink.guard.test.ts sitewide, out of R19-skin
                scope. */}
            <WhatsAppLeadButton
              source="pricing_modal"
              context={{
                service_slug: slug,
                package_name: selectedPackage.name,
              }}
              whatsappContext={[
                { label: "Service", value: slug },
                { label: "Package", value: selectedPackage.name },
              ]}
              utm={{ page: `/services/${slug}` }}
              className="flex items-center justify-center gap-2 w-full px-6 py-4 rounded-xl bg-[#25D366] text-[var(--accent-whatsapp-ink)] font-medium hover:bg-[#20BD5A] transition-colors mb-3"
            >
              <Phone className="w-5 h-5" />
              Chat on WhatsApp
            </WhatsAppLeadButton>

            {/* Optional deep-link to a dedicated landing page */}
            {selectedPackage.link && (
              <Link
                href={selectedPackage.link.href}
                className="flex items-center justify-center gap-2 w-full px-6 py-3 rounded-xl font-medium transition-colors mb-3"
                style={{
                  border: "1px solid var(--r19-line-strong)",
                  color: "var(--text-primary)",
                }}
              >
                {selectedPackage.link.label} →
              </Link>
            )}

            <Link
              href="/chat"
              className="flex items-center justify-center gap-2 w-full px-6 py-3 rounded-xl font-medium transition-colors"
              style={{
                border: "1px solid var(--r19-line-strong)",
                color: "var(--text-primary)",
              }}
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
        </DialogContent>
      )}
    </Dialog>
  );
}
