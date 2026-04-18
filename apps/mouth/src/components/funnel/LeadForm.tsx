"use client";

import * as React from "react";
import { z } from "zod";
import { trackEvent, trackLeadCreated } from "@/lib/analytics";

const leadSchema = z.object({
  name: z.string().trim().min(2, "Please enter your full name."),
  email: z.string().trim().email("Please enter a valid email address."),
  phone: z
    .string()
    .trim()
    .min(6, "Please enter a valid phone number.")
    .optional()
    .or(z.literal("")),
  service: z.string().trim().min(1, "Please choose a service."),
  message: z.string().trim().min(10, "Please add at least 10 characters.").max(2000),
});

export type LeadFormValues = z.infer<typeof leadSchema>;

interface LeadFormProps {
  /** Where the lead is captured, used as analytics `source` (e.g. "visa-oracle-landing"). */
  source: string;
  /** Endpoint that accepts POST JSON. */
  endpoint?: string;
  services?: { value: string; label: string }[];
  onSuccess?: (values: LeadFormValues) => void;
  className?: string;
}

const DEFAULT_SERVICES = [
  { value: "visa", label: "Visa & immigration" },
  { value: "company", label: "Company setup (PT PMA)" },
  { value: "tax", label: "Tax & accounting" },
  { value: "property", label: "Property advisory" },
  { value: "other", label: "Something else" },
];

type Field = keyof LeadFormValues;

export function LeadForm({
  source,
  endpoint = "/api/leads",
  services = DEFAULT_SERVICES,
  onSuccess,
  className = "",
}: Readonly<LeadFormProps>) {
  const [values, setValues] = React.useState<LeadFormValues>({
    name: "",
    email: "",
    phone: "",
    service: "",
    message: "",
  });
  const [errors, setErrors] = React.useState<Partial<Record<Field, string>>>({});
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [success, setSuccess] = React.useState(false);
  const startedRef = React.useRef(false);
  const touchedRef = React.useRef(new Set<Field>());

  const handleChange = (field: Field) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>,
  ) => {
    const next = e.target.value;
    if (!startedRef.current) {
      startedRef.current = true;
      trackEvent("lead_form_start", { source });
    }
    setValues((prev) => ({ ...prev, [field]: next }));
    if (errors[field]) {
      setErrors((prev) => {
        const copy = { ...prev };
        delete copy[field];
        return copy;
      });
    }
  };

  const handleBlur = (field: Field) => () => {
    if (touchedRef.current.has(field)) return;
    touchedRef.current.add(field);
    trackEvent("lead_form_field", { source, field });
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setSubmitError(null);

    const parsed = leadSchema.safeParse(values);
    if (!parsed.success) {
      const fieldErrors: Partial<Record<Field, string>> = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0] as Field | undefined;
        if (key && !fieldErrors[key]) fieldErrors[key] = issue.message;
      }
      setErrors(fieldErrors);
      trackEvent("lead_form_error", {
        source,
        reason: "validation",
        fields: Object.keys(fieldErrors).join(","),
      });
      return;
    }

    setLoading(true);
    trackEvent("lead_form_submit", { source, service: parsed.data.service });
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...parsed.data, source }),
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      trackLeadCreated(source);
      setSuccess(true);
      onSuccess?.(parsed.data);
    } catch (err) {
      trackEvent("lead_form_error", {
        source,
        reason: "network",
        message: err instanceof Error ? err.message : "unknown",
      });
      setSubmitError(
        "We couldn't send your message. Please try again or contact us on WhatsApp.",
      );
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div
        role="status"
        className={`rounded-2xl p-6 text-center ${className}`}
        style={{
          backgroundColor: "var(--bz-elevated, rgba(255,255,255,0.04))",
          border: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <h3 className="text-lg font-semibold mb-2">Thanks — we got it.</h3>
        <p className="text-sm" style={{ color: "var(--tx-secondary, rgba(255,255,255,0.65))" }}>
          Our team will get back to you within one business day.
        </p>
      </div>
    );
  }

  const fieldClass =
    "w-full rounded-lg px-3 py-2 bg-white/5 border border-white/10 focus:outline-none focus:border-white/30 transition-colors";

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      aria-label="Lead capture form"
      className={`flex flex-col gap-4 ${className}`}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Full name</span>
          <input
            type="text"
            name="name"
            autoComplete="name"
            value={values.name}
            onChange={handleChange("name")}
            onBlur={handleBlur("name")}
            aria-invalid={Boolean(errors.name)}
            aria-describedby={errors.name ? "lead-name-error" : undefined}
            className={fieldClass}
            required
          />
          {errors.name ? (
            <span id="lead-name-error" className="text-xs" style={{ color: "#f87171" }}>
              {errors.name}
            </span>
          ) : null}
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Email</span>
          <input
            type="email"
            name="email"
            autoComplete="email"
            value={values.email}
            onChange={handleChange("email")}
            onBlur={handleBlur("email")}
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? "lead-email-error" : undefined}
            className={fieldClass}
            required
          />
          {errors.email ? (
            <span id="lead-email-error" className="text-xs" style={{ color: "#f87171" }}>
              {errors.email}
            </span>
          ) : null}
        </label>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Phone / WhatsApp (optional)</span>
          <input
            type="tel"
            name="phone"
            autoComplete="tel"
            value={values.phone ?? ""}
            onChange={handleChange("phone")}
            onBlur={handleBlur("phone")}
            aria-invalid={Boolean(errors.phone)}
            aria-describedby={errors.phone ? "lead-phone-error" : undefined}
            className={fieldClass}
          />
          {errors.phone ? (
            <span id="lead-phone-error" className="text-xs" style={{ color: "#f87171" }}>
              {errors.phone}
            </span>
          ) : null}
        </label>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium">Service</span>
          <select
            name="service"
            value={values.service}
            onChange={handleChange("service")}
            onBlur={handleBlur("service")}
            aria-invalid={Boolean(errors.service)}
            aria-describedby={errors.service ? "lead-service-error" : undefined}
            className={fieldClass}
            required
          >
            <option value="">Choose a service</option>
            {services.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          {errors.service ? (
            <span id="lead-service-error" className="text-xs" style={{ color: "#f87171" }}>
              {errors.service}
            </span>
          ) : null}
        </label>
      </div>

      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium">How can we help?</span>
        <textarea
          name="message"
          rows={5}
          value={values.message}
          onChange={handleChange("message")}
          onBlur={handleBlur("message")}
          aria-invalid={Boolean(errors.message)}
          aria-describedby={errors.message ? "lead-message-error" : undefined}
          className={fieldClass}
          required
        />
        {errors.message ? (
          <span id="lead-message-error" className="text-xs" style={{ color: "#f87171" }}>
            {errors.message}
          </span>
        ) : null}
      </label>

      {submitError ? (
        <div role="alert" className="text-sm" style={{ color: "#f87171" }}>
          {submitError}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={loading}
        className="self-start inline-flex items-center justify-center px-6 py-3 rounded-xl font-semibold transition-opacity disabled:opacity-60"
        style={{ backgroundColor: "var(--bz-accent, #d4845a)", color: "#fff" }}
      >
        {loading ? "Sending…" : "Send message"}
      </button>
    </form>
  );
}
