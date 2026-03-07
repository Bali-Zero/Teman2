"use client";

import * as React from "react";
import Link from "next/link";
import Image from "next/image";
import {
  Phone,
  Mail,
  MapPin,
  Clock,
  Send,
  MessageCircle,
  Instagram,
  CheckCircle,
  Loader2,
} from "lucide-react";
import { useTranslation } from "@/i18n";

/**
 * Contact Page - Bali Zero
 * McKinsey-inspired layout with contact form
 */
export default function ContactPage() {
  const { t } = useTranslation();
  const [formState, setFormState] = React.useState<
    "idle" | "loading" | "success" | "error"
  >("idle");
  const [formData, setFormData] = React.useState({
    name: "",
    email: "",
    phone: "",
    service: "",
    message: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormState("loading");

    // Simulate form submission (replace with actual API call)
    await new Promise((resolve) => setTimeout(resolve, 1500));

    // Redirect to WhatsApp with message
    const message = encodeURIComponent(
      `Hi Bali Zero! I'm ${formData.name}.\n\nService interested: ${formData.service || "General inquiry"}\n\nMessage: ${formData.message}\n\nEmail: ${formData.email}${formData.phone ? `\nPhone: ${formData.phone}` : ""}`,
    );
    window.open(`https://wa.me/6285904369574?text=${message}`, "_blank");
    setFormState("success");
  };

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
    >,
  ) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  return (
    <div className="min-h-screen bg-[#051C2C]">
      {/* Hero Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16 lg:py-24">
          <div className="max-w-3xl">
            <div className="mb-8">
              <Image
                src="/assets/logo/balizero-logo.png"
                alt="Bali Zero"
                width={80}
                height={80}
                className="rounded-full"
              />
            </div>
            <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-4 block">
              {t("contact.hero.label")}
            </span>
            <h1 className="font-serif text-4xl lg:text-5xl xl:text-6xl text-white leading-[1.1] mb-6">
              {t("contact.hero.title")}{" "}
              <span className="text-[#e85c41]">
                {t("contact.hero.titleAccent")}
              </span>
            </h1>
            <p className="text-lg text-white/70 mb-8 leading-relaxed">
              {t("contact.hero.subtitle")}
            </p>
          </div>
        </div>
      </section>

      {/* Main Content */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16">
            {/* Contact Info */}
            <div>
              <h2 className="font-serif text-2xl text-white mb-8">
                {t("contact.info.getInTouch")}
              </h2>

              <div className="space-y-6">
                {/* WhatsApp */}
                <a
                  href="https://wa.me/6285904369574"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-4 p-6 rounded-xl border border-white/10 bg-[#0a2540] hover:border-[#25D366]/50 transition-all group"
                >
                  <div className="w-12 h-12 rounded-lg bg-[#25D366]/10 flex items-center justify-center flex-shrink-0">
                    <MessageCircle className="w-6 h-6 text-[#25D366]" />
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1 group-hover:text-[#25D366] transition-colors">
                      {t("contact.info.whatsapp")}
                    </h3>
                    <p className="text-white/60 text-sm mb-2">
                      {t("contact.info.whatsappDesc")}
                    </p>
                    <p className="text-[#25D366] font-medium">
                      +62 859 0436 9574
                    </p>
                  </div>
                </a>

                {/* Email */}
                <a
                  href="mailto:info@balizero.com"
                  className="flex items-start gap-4 p-6 rounded-xl border border-white/10 bg-[#0a2540] hover:border-[#2251ff]/50 transition-all group"
                >
                  <div className="w-12 h-12 rounded-lg bg-[#2251ff]/10 flex items-center justify-center flex-shrink-0">
                    <Mail className="w-6 h-6 text-[#2251ff]" />
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1 group-hover:text-[#2251ff] transition-colors">
                      {t("contact.info.email")}
                    </h3>
                    <p className="text-white/60 text-sm mb-2">
                      {t("contact.info.emailDesc")}
                    </p>
                    <p className="text-[#2251ff] font-medium">
                      info@balizero.com
                    </p>
                  </div>
                </a>

                {/* Instagram */}
                <a
                  href="https://instagram.com/balizero0"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-start gap-4 p-6 rounded-xl border border-white/10 bg-[#0a2540] hover:border-[#E4405F]/50 transition-all group"
                >
                  <div className="w-12 h-12 rounded-lg bg-[#E4405F]/10 flex items-center justify-center flex-shrink-0">
                    <Instagram className="w-6 h-6 text-[#E4405F]" />
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1 group-hover:text-[#E4405F] transition-colors">
                      {t("contact.info.instagram")}
                    </h3>
                    <p className="text-white/60 text-sm mb-2">
                      {t("contact.info.instagramDesc")}
                    </p>
                    <p className="text-[#E4405F] font-medium">@balizero0</p>
                  </div>
                </a>

                {/* Office */}
                <div className="flex items-start gap-4 p-6 rounded-xl border border-white/10 bg-[#0a2540]">
                  <div className="w-12 h-12 rounded-lg bg-[#e85c41]/10 flex items-center justify-center flex-shrink-0">
                    <MapPin className="w-6 h-6 text-[#e85c41]" />
                  </div>
                  <div>
                    <h3 className="text-white font-medium mb-1">
                      {t("contact.info.officeLocation")}
                    </h3>
                    <p className="text-white/60 text-sm mb-2">
                      {t("contact.info.officeDesc")}
                    </p>
                    <p className="text-white/80">
                      {t("contact.info.officeAddress")}
                    </p>
                    <p className="text-white/50 text-sm mt-1">
                      {t("contact.info.officeNote")}
                    </p>
                  </div>
                </div>
              </div>

              {/* Office Hours */}
              <div className="mt-8 p-6 rounded-xl border border-white/10 bg-[#0a2540]">
                <div className="flex items-center gap-3 mb-4">
                  <Clock className="w-5 h-5 text-[#2251ff]" />
                  <h3 className="text-white font-medium">
                    {t("contact.hours.title")}
                  </h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-white/60">
                      {t("contact.hours.monFri")}
                    </span>
                    <span className="text-white">
                      {t("contact.hours.monFriHours")}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">
                      {t("contact.hours.saturday")}
                    </span>
                    <span className="text-white">
                      {t("contact.hours.saturdayHours")}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">
                      {t("contact.hours.sunday")}
                    </span>
                    <span className="text-white/40">
                      {t("contact.hours.sundayClosed")}
                    </span>
                  </div>
                  <div className="pt-2 border-t border-white/10 mt-2">
                    <span className="text-white/40 text-xs">
                      {t("contact.hours.timezone")}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Contact Form */}
            <div>
              <h2 className="font-serif text-2xl text-white mb-8">
                {t("contact.form.title")}
              </h2>

              {formState === "success" ? (
                <div className="p-8 rounded-xl border border-[#22c55e]/30 bg-[#22c55e]/10 text-center">
                  <CheckCircle className="w-16 h-16 text-[#22c55e] mx-auto mb-4" />
                  <h3 className="text-xl font-medium text-white mb-2">
                    {t("contact.success.title")}
                  </h3>
                  <p className="text-white/60 mb-6">
                    {t("contact.success.description")}
                  </p>
                  <button
                    onClick={() => setFormState("idle")}
                    className="text-[#2251ff] hover:text-[#1a41cc] font-medium"
                  >
                    {t("common.cta.sendAnother")}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-6">
                  {/* Name */}
                  <div>
                    <label
                      htmlFor="name"
                      className="block text-sm font-medium text-white/80 mb-2"
                    >
                      {t("contact.form.fullName")}{" "}
                      <span className="text-[#e85c41]">*</span>
                    </label>
                    <input
                      type="text"
                      id="name"
                      name="name"
                      required
                      value={formData.name}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-lg bg-[#0a2540] border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-[#2251ff] transition-colors"
                      placeholder="John Doe"
                    />
                  </div>

                  {/* Email */}
                  <div>
                    <label
                      htmlFor="email"
                      className="block text-sm font-medium text-white/80 mb-2"
                    >
                      {t("contact.form.emailAddress")}{" "}
                      <span className="text-[#e85c41]">*</span>
                    </label>
                    <input
                      type="email"
                      id="email"
                      name="email"
                      required
                      value={formData.email}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-lg bg-[#0a2540] border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-[#2251ff] transition-colors"
                      placeholder="john@example.com"
                    />
                  </div>

                  {/* Phone */}
                  <div>
                    <label
                      htmlFor="phone"
                      className="block text-sm font-medium text-white/80 mb-2"
                    >
                      {t("contact.form.phone")}
                    </label>
                    <input
                      type="tel"
                      id="phone"
                      name="phone"
                      value={formData.phone}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-lg bg-[#0a2540] border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-[#2251ff] transition-colors"
                      placeholder="+62 xxx xxxx xxxx"
                    />
                  </div>

                  {/* Service */}
                  <div>
                    <label
                      htmlFor="service"
                      className="block text-sm font-medium text-white/80 mb-2"
                    >
                      {t("contact.form.service")}
                    </label>
                    <select
                      id="service"
                      name="service"
                      value={formData.service}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-lg bg-[#0a2540] border border-white/10 text-white focus:outline-none focus:border-[#2251ff] transition-colors"
                    >
                      <option value="">
                        {t("contact.form.servicePlaceholder")}
                      </option>
                      <option value="Visa Services">
                        {t("contact.form.serviceVisa")}
                      </option>
                      <option value="Company Setup">
                        {t("contact.form.serviceCompany")}
                      </option>
                      <option value="Tax Consulting">
                        {t("contact.form.serviceTax")}
                      </option>
                      <option value="Real Estate">
                        {t("contact.form.serviceRealEstate")}
                      </option>
                      <option value="Multiple Services">
                        {t("contact.form.serviceMultiple")}
                      </option>
                      <option value="Other">
                        {t("contact.form.serviceOther")}
                      </option>
                    </select>
                  </div>

                  {/* Message */}
                  <div>
                    <label
                      htmlFor="message"
                      className="block text-sm font-medium text-white/80 mb-2"
                    >
                      {t("contact.form.message")}{" "}
                      <span className="text-[#e85c41]">*</span>
                    </label>
                    <textarea
                      id="message"
                      name="message"
                      required
                      rows={5}
                      value={formData.message}
                      onChange={handleChange}
                      className="w-full px-4 py-3 rounded-lg bg-[#0a2540] border border-white/10 text-white placeholder:text-white/40 focus:outline-none focus:border-[#2251ff] transition-colors resize-none"
                      placeholder={t("contact.form.messagePlaceholder")}
                    />
                  </div>

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={formState === "loading"}
                    className="w-full flex items-center justify-center gap-2 px-6 py-4 rounded-lg bg-[#2251ff] text-white font-medium hover:bg-[#1a41cc] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {formState === "loading" ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        {t("common.cta.sending")}
                      </>
                    ) : (
                      <>
                        <Send className="w-5 h-5" />
                        {t("common.cta.sendMessage")}
                      </>
                    )}
                  </button>

                  <p className="text-center text-white/40 text-sm">
                    {t("contact.form.responseTime")}
                  </p>
                </form>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* Zantara AI CTA */}
    </div>
  );
}
