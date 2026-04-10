"use client";

import React, { useState } from "react";
import { User, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { cropToSquare } from "@/lib/utils/imageResize";
import type { Client } from "@/lib/api/crm/crm.types";
import { COMMON_NATIONALITIES, CLIENT_STATUSES } from "@/lib/api/crm/crm.types";
import { Modal } from "../Modal";
import { useTeamMemberOptions } from "@/hooks/useTeamMembers";
import { COUNTRY_CODES, extractCountryCode } from "../utils";

export function EditClientModal({
  client,
  onClose,
  onSave,
}: {
  client: Client;
  onClose: () => void;
  onSave: () => void;
}) {
  const { options: teamMemberOptions } = useTeamMemberOptions();
  const [isSaving, setIsSaving] = useState(false);
  const [formData, setFormData] = useState({
    full_name: client.full_name || "",
    email: client.email || "",
    phone: client.phone || "",
    whatsapp: client.whatsapp || "",
    company_name: client.company_name || "",
    nationality: client.nationality || "",
    passport_number: client.passport_number || "",
    passport_expiry: client.passport_expiry?.split("T")[0] || "",
    date_of_birth: client.date_of_birth?.split("T")[0] || "",
    address: client.address || "",
    notes: client.notes || "",
    status: client.status || "lead",
    client_type: client.client_type || "individual",
    assigned_to: client.assigned_to || "",
    avatar_url: client.avatar_url || "",
    lead_source: client.lead_source || "",
    service_interest: client.service_interest || "",
    tags: (client.tags || []).join(", "),
  });

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith("image/")) {
      toast.error("Please select an image file");
      return;
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      toast.error("Image size must be less than 2MB");
      return;
    }

    try {
      // Crop to square and resize to 400x400px
      const resizedImage = await cropToSquare(file, 400, 0.85);
      setFormData((prev) => ({ ...prev, avatar_url: resizedImage }));
    } catch (error) {
      logger.error(
        "Failed to process image",
        { component: "ClientDetail", action: "processImage" },
        error instanceof Error ? error : new Error(String(error)),
      );
      toast.error("Failed to process image. Please try again.");
    }
  };

  const removeAvatar = () => {
    setFormData((prev) => ({ ...prev, avatar_url: "" }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.full_name.trim()) {
      toast.error("Full name is required");
      return;
    }

    // Block saving if client is under 18
    if (formData.date_of_birth) {
      const dob = new Date(formData.date_of_birth);
      const today = new Date();
      const age = Math.floor(
        (today.getTime() - dob.getTime()) / (365.25 * 24 * 60 * 60 * 1000),
      );
      if (age < 18) {
        toast.error(
          `Minor (${age} years old) — under-18 clients must be linked to a parent via Family Members.`,
        );
        return;
      }
    }

    setIsSaving(true);
    try {
      const user = await api.getProfile();
      const requiredFields = ["full_name", "status", "client_type"];
      const updates: Record<string, unknown> = {};
      Object.entries(formData).forEach(([key, value]) => {
        if (key === "tags") {
          const tagsArray = (value as string)
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean);
          if (tagsArray.length > 0) updates[key] = tagsArray;
          return;
        }
        if (
          value !== undefined &&
          value !== null &&
          (value !== "" || requiredFields.includes(key))
        ) {
          updates[key] = value;
        }
      });
      await api.crm.updateClient(client.id, updates, user.email);
      onSave();
      onClose();
      toast.success("Client updated");
    } catch (err) {
      toast.error("Failed to update", { description: (err as Error).message });
    } finally {
      setIsSaving(false);
    }
  };

  const inputClass =
    "w-full px-4 py-2.5 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50 focus:border-[var(--accent)]";

  return (
    <Modal
      title="Edit Client"
      aria-label="Edit Client"
      onClose={onClose}
      isSaving={isSaving}
      onSave={handleSubmit}
    >
      {/* Avatar Upload */}
      <div className="flex items-center gap-6 pb-6 border-b border-[var(--bz-border)]">
        <div className="relative">
          <div className="w-24 h-24 rounded-full overflow-hidden border-2 border-[var(--bz-border)] bg-[var(--bz-surface)] flex items-center justify-center">
            {formData.avatar_url ? (
              <img
                src={formData.avatar_url}
                alt="Avatar preview"
                className="w-full h-full object-cover"
              />
            ) : formData.status === "lead" ? (
              <img
                src="/avatars/default-lead.svg"
                alt="Default Lead"
                className="w-full h-full object-cover"
              />
            ) : formData.status === "active" ? (
              <img
                src="/avatars/default-active.svg"
                alt="Default Active"
                className="w-full h-full object-cover"
              />
            ) : (
              <User className="w-12 h-12 text-[var(--bz-text-2)]" />
            )}
          </div>
          {formData.avatar_url && (
            <button
              type="button"
              onClick={removeAvatar}
              className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-red-500 text-white flex items-center justify-center hover:bg-red-600 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Client Photo</label>
          <p className="text-xs text-[var(--bz-text-2)] mb-2">
            Upload a profile picture (max 2MB)
          </p>
          <label className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--bz-accent)] text-white hover:bg-[var(--bz-accent)]/90 transition-colors cursor-pointer">
            <Upload className="w-4 h-4" />
            {formData.avatar_url ? "Change Photo" : "Upload Photo"}
            <input
              type="file"
              accept="image/*"
              onChange={handleAvatarUpload}
              className="hidden"
            />
          </label>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">
            Full Name *
          </label>
          <input
            type="text"
            value={formData.full_name}
            onChange={(e) =>
              setFormData({ ...formData, full_name: e.target.value })
            }
            className={inputClass}
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Email</label>
          <input
            type="email"
            value={formData.email}
            onChange={(e) =>
              setFormData({ ...formData, email: e.target.value })
            }
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">Phone</label>
          <div className="flex gap-2">
            <select
              value={extractCountryCode(formData.phone).countryCode}
              onChange={(e) => {
                const { localNumber } = extractCountryCode(formData.phone);
                setFormData({
                  ...formData,
                  phone: e.target.value + localNumber,
                });
              }}
              className={`${inputClass} !w-[90px] flex-shrink-0`}
            >
              {COUNTRY_CODES.map(({ code, flag }) => (
                <option key={code} value={code}>
                  {flag} {code}
                </option>
              ))}
            </select>
            <input
              type="tel"
              aria-label="Phone number"
              value={extractCountryCode(formData.phone).localNumber}
              onChange={(e) => {
                const { countryCode } = extractCountryCode(formData.phone);
                const digits = e.target.value.replace(/[^\d]/g, "");
                setFormData({ ...formData, phone: countryCode + digits });
              }}
              className={`${inputClass} flex-1 min-w-[100px]`}
              placeholder="Phone number"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Nationality
          </label>
          <select
            value={formData.nationality}
            onChange={(e) =>
              setFormData({ ...formData, nationality: e.target.value })
            }
            className={inputClass}
          >
            <option value="">Select...</option>
            {COMMON_NATIONALITIES.map((nat) => (
              <option key={nat} value={nat}>
                {nat}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Passport Number
          </label>
          <input
            type="text"
            value={formData.passport_number}
            onChange={(e) =>
              setFormData({
                ...formData,
                passport_number: e.target.value.toUpperCase(),
              })
            }
            className={inputClass}
            placeholder="e.g. YA123456"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Passport Expiry
          </label>
          <input
            type="date"
            value={formData.passport_expiry}
            onChange={(e) =>
              setFormData({ ...formData, passport_expiry: e.target.value })
            }
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Date of Birth
          </label>
          <input
            type="date"
            value={formData.date_of_birth}
            onChange={(e) =>
              setFormData({ ...formData, date_of_birth: e.target.value })
            }
            className={inputClass}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Lead Source
          </label>
          <select
            value={formData.lead_source}
            onChange={(e) =>
              setFormData({ ...formData, lead_source: e.target.value })
            }
            className={inputClass}
          >
            <option value="">Select...</option>
            <option value="website">Website</option>
            <option value="referral">Referral</option>
            <option value="social_media">Social Media</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="telegram">Telegram</option>
            <option value="walk_in">Walk-in</option>
            <option value="event">Event</option>
            <option value="other">Other</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Service Interest
          </label>
          <input
            type="text"
            value={formData.service_interest}
            onChange={(e) =>
              setFormData({ ...formData, service_interest: e.target.value })
            }
            className={inputClass}
            placeholder="e.g. PT PMA, KITAS, Tax"
          />
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Tags</label>
          <input
            type="text"
            value={formData.tags}
            onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
            className={inputClass}
            placeholder="Comma-separated, e.g. VIP, Urgent, Bali"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1.5">
            Assigned To
          </label>
          <select
            value={formData.assigned_to}
            onChange={(e) =>
              setFormData({ ...formData, assigned_to: e.target.value })
            }
            className={inputClass}
          >
            <option value="">Unassigned</option>
            {teamMemberOptions.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
        </div>
        <div className="md:col-span-2">
          <label className="block text-sm font-medium mb-1.5">Status</label>
          <div className="flex gap-2 flex-wrap">
            {CLIENT_STATUSES.map(({ value, label, color }) => (
              <button
                key={value}
                type="button"
                onClick={() => setFormData({ ...formData, status: value })}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all border ${
                  formData.status === value
                    ? `border-${color}-500/50`
                    : "border-transparent bg-[var(--bz-surface)]"
                }`}
                style={{
                  backgroundColor:
                    formData.status === value
                      ? `var(--${color === "blue" ? "accent" : color}-500-20, rgba(59, 130, 246, 0.2))`
                      : undefined,
                  color:
                    formData.status === value
                      ? `var(--${color === "blue" ? "accent" : color}-500, #3b82f6)`
                      : "var(--bz-text-2)",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}
