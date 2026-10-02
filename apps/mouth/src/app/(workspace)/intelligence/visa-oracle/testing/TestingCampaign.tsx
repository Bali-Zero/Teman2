"use client";

import { useEffect, useState, type ReactNode, type FormEvent } from "react";
import Link from "next/link";
import {
  CARD,
  FIELD,
  FOCUS,
  EYEBROW,
  Masthead,
  Field,
  Notice,
  StatePill,
} from "@/components/workspace/r19";
import { baliDate } from "@/app/(workspace)/dashboard/VisaOracleTestingBanner";
import { testingApi } from "./api";
import type {
  Assignment,
  CampaignData,
  Expected,
  Result,
  Review,
} from "./types";

const BUTTON = `min-h-11 rounded-md border border-[var(--line-control)] px-4 py-2 text-sm font-semibold disabled:opacity-40 ${FOCUS}`;
const PRIMARY = `${BUTTON} bg-[var(--bz-panel)] text-[var(--bz-on-panel)]`;
const initialExpected: Expected = {
  text: "",
  basis: "hypothesis",
  reference: "",
  browser: "",
  device: "",
  displayed_version: "unknown",
};
const initialResult: Result = {
  steps: "",
  actual_state: "other",
  actual: "",
  source_notes: "",
  uncertainty: "",
  comment: "",
  category: "none",
  severity: "none",
  certainty: "observation",
  reproducibility: "not_retried",
  evidence_ref: "",
};
const INPUT_LABELS: Record<string, string> = {
  in_indonesia: "Saat ini berada di Indonesia",
  holds_stay_permit: "Memiliki izin tinggal",
  nationalities: "Kewarganegaraan (kode negara)",
  nationality: "Kewarganegaraan",
  birth_date: "Tanggal lahir",
  category: "Tujuan utama",
  trip_scope: "Lingkup tujuan perjalanan",
  stay_days: "Lama tinggal (hari)",
  entry_pattern: "Pola masuk",
  review_gate: "Pernyataan ketidakpastian / tujuan campuran",
  sponsor_category: "Jenis sponsor",
  remote_clients: "Lokasi klien pekerjaan jarak jauh",
  remote_compensation: "Imbalan dari Indonesia",
  work_payer: "Pihak Indonesia membayar pekerjaan",
  remote_employer_country: "Negara pemberi kerja",
  remote_pt_pma: "Kaitan pekerjaan dengan PT PMA",
  wants_onshore_conversion: "Ingin mengubah izin dari dalam Indonesia",
  application_channel: "Jalur permohonan",
  current_status_code: "Kode status kunjungan saat ini",
  stay_permit_code: "Kode izin tinggal saat ini",
  permit_expiry: "Tanggal berakhirnya izin",
  overstay_days: "Hari melebihi izin tinggal",
  renewal_paid: "Pembayaran perpanjangan sudah dilakukan",
  family_sponsor_confirmed: "Sponsor keluarga telah dikonfirmasi",
  business_activity: "Kegiatan bisnis",
  work_indonesia_compensation: "Imbalan pekerjaan dari Indonesia",
  work_sponsor_confirmed: "Sponsor pekerjaan telah dikonfirmasi",
  study_level: "Jenjang pendidikan",
  study_admission_confirmed: "Penerimaan studi telah dikonfirmasi",
  study_sponsor_confirmed: "Sponsor studi telah dikonfirmasi",
  family_relation: "Hubungan keluarga",
  marital_status: "Status perkawinan",
  family_sponsor_nationalities: "Kewarganegaraan sponsor keluarga",
  family_marriage_registered: "Perkawinan terdaftar",
  investment_vehicle: "Bentuk investasi",
  investment_pt_pma: "Investasi melalui PT PMA",
  investment_currency: "Mata uang investasi",
  investment_capital_idr: "Nilai investasi (IDR)",
  investment_paid_up_capital_idr: "Modal disetor (IDR)",
  investment_role: "Peran dalam perusahaan",
  retirement_basis: "Dasar tujuan pensiun",
  retirement_undecided_basis: "Hal yang belum diputuskan untuk pensiun",
  diaspora_connection: "Hubungan diaspora",
  diaspora_documents: "Dokumen diaspora tersedia",
  other_purpose: "Tujuan lainnya",
  other_paid_activity: "Kegiatan lain menerima imbalan",
};
function EvidenceLink({ id }: { id: string }) {
  return (
    <a
      className="inline-block py-2 text-sm underline"
      href={`/api/visa-oracle/testing/${encodeURIComponent(id)}/screenshot`}
      target="_blank"
      rel="noopener noreferrer"
    >
      Lihat screenshot tersimpan (akses tim)
    </a>
  );
}
const RESULT_LABELS: Record<string, string> = {
  steps: "Input dan langkah",
  actual_state: "Status aktual",
  actual: "Hasil dan alasan",
  source_notes: "Sumber / yang tidak ditampilkan",
  uncertainty: "Penanganan ketidakpastian",
  comment: "Komentar",
  category: "Kategori",
  severity: "Dampak",
  certainty: "Kepastian",
  reproducibility: "Pengulangan",
  evidence_ref: "Referensi bukti",
};
const STATES = {
  supported: "Didukung",
  needs_input: "Perlu informasi",
  human_review: "Perlu tinjauan manusia",
  no_path: "Tidak ada jalur",
  unavailable: "Tidak tersedia",
  blocked: "Terhalang",
  other: "Lainnya",
};
function Area({
  name,
  label,
  value,
  onChange,
  required = true,
}: {
  name: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm" htmlFor={name}>
      <span className={EYEBROW}>{label}</span>
      <textarea
        id={name}
        name={name}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        minLength={8}
        maxLength={2000}
        className={`${FIELD} h-auto min-h-24 py-3`}
      />
    </label>
  );
}
function Choice({
  name,
  label,
  value,
  options,
  onChange,
}: {
  name: string;
  label: string;
  value: string;
  options: Record<string, string>;
  onChange: (value: string) => void;
}) {
  return (
    <label htmlFor={name} className="flex flex-col gap-1">
      <span className={EYEBROW}>{label}</span>
      <select
        id={name}
        name={name}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={FIELD}
      >
        {Object.entries(options).map(([id, text]) => (
          <option key={id} value={id}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}
function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={`${CARD} p-5 space-y-4`}>
      <h2 className="text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}
function dayLabel(day: string) {
  return new Intl.DateTimeFormat("id-ID", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  }).format(new Date(`${day}T12:00:00Z`));
}
/** Opens on today's Bali date when it has cases (the campaign days are not
 * consecutive), otherwise on the first campaign day. */
export function initialDay(
  data: Pick<CampaignData, "campaign"> & { assignments: { day: string }[] },
  today: string,
): string {
  return data.assignments.some((a) => a.day === today)
    ? today
    : data.campaign.start_date;
}

// Self-review (2026-09-30): a tester only reviews their OWN submitted runs. The
// admin (no assigned slot) keeps the full cross-slot queue for auditing.
function ownReview(a: Assignment, viewerSlot: string | null) {
  return !!a.record?.result && (viewerSlot === null || a.slot === viewerSlot);
}

export default function OracleTestingPage() {
  const [data, setData] = useState<CampaignData | null>(null);
  const [failed, setFailed] = useState(false);
  const [day, setDay] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function load() {
    setFailed(false);
    try {
      const response = await testingApi.load();
      setData(response);
      setDay(
        (current) => current || initialDay(response, baliDate(new Date())),
      );
    } catch {
      setData(null);
      setFailed(true);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function mutate(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      await load();
      setMessage("Perubahan tersimpan di server.");
    } catch {
      setError(
        "Perubahan belum tersimpan. Periksa koneksi dan izin akun, lalu coba lagi. Data mungkin telah dikunci atau diperbarui oleh pengguna lain.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function exportData() {
    setBusy(true);
    setError("");
    try {
      const exported = await testingApi.export();
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(exported, null, 2)], {
          type: "application/json",
        }),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "visa-oracle-testing.json";
      anchor.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Ekspor gagal. Periksa koneksi dan izin reviewer.");
    } finally {
      setBusy(false);
    }
  }
  if (failed)
    return (
      <div className="space-y-4 p-4">
        <Notice role="alert">
          Data pengujian belum dapat dimuat. Masuk dengan akun tim yang
          berwenang atau coba lagi.
        </Notice>
        <button className={BUTTON} onClick={() => void load()}>
          Coba lagi
        </button>
      </div>
    );
  if (!data)
    return (
      <p role="status" className="p-6">
        Memuat penugasan dari server…
      </p>
    );
  const days = [...new Set(data.assignments.map((a) => a.day))].sort();
  const perTester = days.length * 5;
  const mine = data.assignments.filter(
    (a) => a.slot === data.viewer.slot && a.day === day,
  );
  const current = mine.find((a) => a.id === selected);
  const lockedExpectations = mine.filter((a) => a.record?.expected).length;
  const submitted = data.assignments.filter(
    (a) => a.record?.status === "submitted",
  );
  const { blocked, reached } = data.counts;
  return (
    <main className="mx-auto max-w-6xl space-y-6 p-4 pb-20 text-[var(--tx-pure)] md:p-6">
      <Masthead
        eyebrow="Riset internal · Visa Oracle"
        title="Pengujian tim"
        sub="2, 5 dan 6 Oktober 2026 · Lima kasus per hari, 15 per orang. Catat apa yang benar-benar terjadi; hasil terhalang tetap berguna."
        actions={
          <Link className={BUTTON} href="/intelligence/visa-oracle">
            Kembali
          </Link>
        }
      />
      <Notice tone="wait">
        Gunakan hanya data sintetis. Jangan masukkan identitas klien atau
        mengirim WhatsApp, email, formulir kontak, atau permintaan layanan.
        Halaman ini mencatat pengamatan, bukan bukti kepatuhan privasi
        operasional.
      </Notice>
      <div
        className="grid grid-cols-2 gap-3 md:grid-cols-5"
        aria-label="Ringkasan kampanye"
      >
        {[
          ["Direncanakan", data.counts.planned],
          ["Ekspektasi dikunci", data.counts.started],
          ["Observasi dikirim", data.counts.submitted],
          ["Isu direproduksi", data.counts.reproduced],
          ["Ditinjau reviewer", data.counts.reviewed],
        ].map(([label, number]) => (
          <div key={label} className={`${CARD} p-4`}>
            <p className={EYEBROW}>{label}</p>
            <p className="mt-2 text-3xl tabular-nums">{number}</p>
          </div>
        ))}
      </div>
      <p className="text-sm text-[var(--tx-secondary)]">
        Seluruh kampanye: {reached} mencapai status hasil, {blocked}{" "}
        terhalang/tidak tersedia. Angka ini tidak mengukur akurasi hukum. Zona
        waktu kampanye: {data.campaign.timezone}.
      </p>
      {error && <Notice role="alert">{error}</Notice>}
      {message && (
        <Notice tone="ok" role="status">
          {message}
        </Notice>
      )}
      {data.progress.length > 0 && (
        <Block title="Progres bersama">
          <p className="text-sm">
            Observasi terkirim / 5 per hari. Ditinjau dihitung terpisah; ini
            bukan peringkat atau nilai akurasi.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Progres tim per hari">
              <thead>
                <tr>
                  <th className="p-2 text-left">Slot</th>
                  {days.map((d) => (
                    <th key={d} className="p-2">
                      {d.slice(5)}
                    </th>
                  ))}
                  <th className="p-2">Total / {perTester}</th>
                  <th className="p-2">Ditinjau</th>
                </tr>
              </thead>
              <tbody>
                {data.slots.map((slot) => (
                  <tr
                    key={slot.slot}
                    className="border-t border-[var(--bz-border)]"
                  >
                    <th className="p-2 text-left">{slot.slot}</th>
                    {days.map((d) => (
                      <td key={d} className="p-2 text-center">
                        {data.progress.find(
                          (p) => p.slot === slot.slot && p.day === d,
                        )?.submitted ?? 0}
                        /5
                      </td>
                    ))}
                    <td className="p-2 text-center">
                      {data.progress
                        .filter((p) => p.slot === slot.slot)
                        .reduce((n, p) => n + p.submitted, 0)}
                      /{perTester}
                    </td>
                    <td className="p-2 text-center">
                      {data.progress
                        .filter((p) => p.slot === slot.slot)
                        .reduce((n, p) => n + p.reviewed, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Block>
      )}
      <Block title="Penugasan Anda">
        <p className="text-sm">
          Fase 1: tulis dan kunci ekspektasi untuk kelima kasus tanpa membuka
          Oracle. Fase 2: setelah kelimanya dikunci, buka Oracle dan catat hasil
          setiap kasus.
        </p>
        {data.viewer.slot && (
          <p role="status" className="text-sm font-semibold">
            Ekspektasi terkunci untuk hari yang dipilih: {lockedExpectations}/5.
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <StatePill tone="ink" label={data.viewer.slot || "Belum ada slot"} />
          <div className="min-w-60">
            <Choice
              name="day"
              label="Hari pengujian"
              value={day}
              options={Object.fromEntries(days.map((d) => [d, dayLabel(d)]))}
              onChange={(v) => {
                setDay(v);
                setSelected(null);
              }}
            />
          </div>
        </div>
        {!data.viewer.slot && (
          <Notice tone="wait">
            Akun ini belum ditempatkan pada T01–T06. Admin harus menetapkan slot
            sebelum Anda dapat menguji.
          </Notice>
        )}
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {mine.map((a) => (
            <button
              type="button"
              key={a.id}
              aria-pressed={a.id === selected}
              onClick={() => setSelected(a.id)}
              className={`${BUTTON} p-4 text-left ${a.id === selected ? "border-[var(--bz-copper)] bg-[var(--bz-card)]" : ""}`}
            >
              <span className={EYEBROW}>
                Kasus {a.index + 1} · {a.scenario.id}
              </span>
              <span className="my-3 block font-semibold">
                {a.scenario.title}
              </span>
              <span className="block text-xs">
                {a.record?.status === "submitted"
                  ? "Observasi terkirim"
                  : a.record
                    ? "Ekspektasi dikunci"
                    : "Belum dimulai"}
              </span>
            </button>
          ))}
        </div>
        {data.viewer.slot && mine.length === 0 && (
          <p>Tidak ada penugasan untuk hari ini.</p>
        )}
      </Block>
      {current && (
        <CaseForm
          key={`${current.id}-${current.record?.status || "new"}`}
          assignment={current}
          busy={busy}
          mutate={mutate}
        />
      )}
      {data.viewer.can_review && (
        <Block title="Antrean reviewer">
          <p className="text-sm">
            Kunci kelima ekspektasi hari ini sebelum meninjau. Setiap tester
            meninjau hasil pengujiannya sendiri — bukan milik rekan lain. Isu
            terkonfirmasi dan isu yang berhasil direproduksi dicatat terpisah.
          </p>
          <button
            type="button"
            className={BUTTON}
            disabled={busy}
            onClick={() => void exportData()}
          >
            Ekspor data JSON
          </button>
          {submitted
            .filter((a) => ownReview(a, data.viewer.slot))
            .map((a) => (
              <ReviewForm
                key={`${a.id}-${a.record?.review?.reviewed_at || "pending"}`}
                assignment={a}
                busy={busy}
                mutate={mutate}
              />
            ))}
          {submitted.filter((a) => ownReview(a, data.viewer.slot)).length ===
            0 && <p>Belum ada observasi untuk ditinjau.</p>}
        </Block>
      )}
      {data.viewer.can_configure && (
        <Block title="Konfigurasi enam slot">
          <p className="text-sm">
            Pilih akun tim yang sebenarnya. Server menolak perubahan penugasan
            setelah slot memiliki catatan.
          </p>
          {data.slots.map((slot) => (
            <SlotForm
              key={`${slot.slot}-${slot.member_id}-${slot.reviewer}`}
              slot={slot}
              candidates={data.staff_candidates || []}
              busy={busy}
              mutate={mutate}
            />
          ))}
        </Block>
      )}
    </main>
  );
}

type Mutation = (action: () => Promise<unknown>) => Promise<void>;
function CaseForm({
  assignment: a,
  busy,
  mutate,
}: {
  assignment: Assignment;
  busy: boolean;
  mutate: Mutation;
}) {
  const [expected, setExpected] = useState<Expected>(
    a.record?.expected || initialExpected,
  );
  const [result, setResult] = useState<Result>({
    ...initialResult,
    ...a.record?.result,
  });
  const [attested, setAttested] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [screenshotName, setScreenshotName] = useState("");
  const [readingImage, setReadingImage] = useState(false);
  function selectScreenshot(input: HTMLInputElement) {
    const file = input.files?.[0];
    setValidationError("");
    setScreenshotName("");
    setResult((previous) => ({ ...previous, screenshot_base64: undefined }));
    if (!file) return;
    if (file.size > 600 * 1024) {
      setValidationError(
        "Gunakan PNG, JPG, atau WebP berukuran maksimal 600 KiB, tanpa data pribadi.",
      );
      input.value = "";
      return;
    }
    const reader = new FileReader();
    setReadingImage(true);
    reader.onerror = () => {
      setReadingImage(false);
      setValidationError("Gambar tidak dapat dibaca. Pilih ulang file.");
      input.value = "";
    };
    reader.onload = () => {
      setReadingImage(false);
      const bytes = new Uint8Array(reader.result as ArrayBuffer);
      const png = [137, 80, 78, 71, 13, 10, 26, 10].every(
        (byte, index) => bytes[index] === byte,
      );
      const jpeg = [255, 216, 255].every(
        (byte, index) => bytes[index] === byte,
      );
      const webp =
        [82, 73, 70, 70].every((byte, index) => bytes[index] === byte) &&
        [87, 69, 66, 80].every((byte, index) => bytes[index + 8] === byte);
      if (!png && !jpeg && !webp) {
        setValidationError(
          "File harus berupa PNG, JPG, atau WebP yang valid. SVG tidak diterima.",
        );
        input.value = "";
        return;
      }
      let binary = "";
      for (const byte of bytes) binary += String.fromCharCode(byte);
      setResult((previous) => ({
        ...previous,
        screenshot_base64: btoa(binary),
      }));
      setScreenshotName(file.name);
    };
    reader.readAsArrayBuffer(file);
  }
  const locked = !!a.record;
  const complete = a.record?.status === "submitted";
  const canRecordResults = locked && a.can_record_results === true;
  const canStart = locked || a.can_start !== false;
  const changeExpected = (key: keyof Expected, value: string) =>
    setExpected((previous) => ({ ...previous, [key]: value }));
  const changeResult = (key: keyof Result, value: string) =>
    setResult((previous) => ({ ...previous, [key]: value }));
  function start(e: FormEvent) {
    e.preventDefault();
    if (
      ["official", "expert"].includes(expected.basis) &&
      expected.reference.trim().length < 8
    ) {
      setValidationError(
        "Cantumkan referensi untuk ekspektasi resmi atau yang dikonfirmasi ahli.",
      );
      return;
    }
    if (attested && canStart)
      void mutate(() => testingApi.start(a.id, expected));
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    if (!canRecordResults || complete || busy) return;
    setValidationError("");
    if ((result.category === "none") !== (result.severity === "none")) {
      setValidationError(
        "Samakan kategori dan dampak: pilih dampak untuk isu, atau pilih Tidak ada untuk keduanya.",
      );
      return;
    }
    if (attested) void mutate(() => testingApi.result(a.id, result, true));
  }
  return (
    <div className="space-y-5">
      <Block title={`${a.scenario.id} · ${a.scenario.title}`}>
        <p>{a.scenario.focus}</p>
        <dl className="grid gap-3 sm:grid-cols-2">
          {Object.entries(a.scenario.inputs).map(([key, value]) => (
            <div key={key} className="border-b border-[var(--bz-border)] pb-2">
              <dt className={EYEBROW}>
                {INPUT_LABELS[key] || key.replaceAll("_", " ")}
              </dt>
              <dd className="mt-1 text-sm">{value}</dd>
            </div>
          ))}
        </dl>
        <ol className="list-decimal space-y-2 pl-5 text-sm">
          {a.scenario.instructions.map((text, i) => (
            <li key={i}>{text}</li>
          ))}
        </ol>
        <Notice tone="wait">
          Jangan menebak jawaban hukum dari judul kasus. Tulis ekspektasi Anda
          sendiri sebelum melihat hasil.
        </Notice>
      </Block>
      <Block title="1. Kunci ekspektasi sebelum menguji">
        {!canStart && (
          <Notice tone="wait">
            WITA menentukan tanggal mulai kasus. Mulai pada hari penugasan; draf
            yang sudah ada dapat dilanjutkan.
          </Notice>
        )}
        <form onSubmit={start} className="space-y-4">
          <fieldset
            disabled={locked || busy || !canStart}
            className="space-y-4"
          >
            <Area
              name="expected"
              label="Hasil yang Anda harapkan dan alasannya"
              value={expected.text}
              onChange={(v) => changeExpected("text", v)}
            />
            <Choice
              name="basis"
              label="Dasar ekspektasi"
              value={expected.basis}
              onChange={(v) => changeExpected("basis", v)}
              options={{
                hypothesis: "Hipotesis pribadi",
                official: "Rujukan resmi",
                expert: "Dikonfirmasi ahli",
                needs_review: "Masih perlu ditinjau",
              }}
            />
            <Field
              id="expected-reference"
              label="URL atau referensi dasar (wajib untuk rujukan resmi/ahli)"
              value={expected.reference}
              onChange={(e) => changeExpected("reference", e.target.value)}
              maxLength={1000}
            />
            <details open={!locked}>
              <summary
                className={`cursor-pointer py-2 text-sm font-semibold ${FOCUS}`}
              >
                Konteks perangkat dan versi
              </summary>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field
                  id="browser"
                  label="Browser dan versi"
                  required
                  value={expected.browser}
                  onChange={(e) => changeExpected("browser", e.target.value)}
                  minLength={2}
                  maxLength={100}
                />
                <Field
                  id="device"
                  label="Perangkat / OS"
                  required
                  value={expected.device}
                  onChange={(e) => changeExpected("device", e.target.value)}
                  minLength={2}
                  maxLength={100}
                />
                <Field
                  id="version"
                  label="Versi Oracle yang ditampilkan"
                  value={expected.displayed_version}
                  onChange={(e) =>
                    changeExpected(
                      "displayed_version",
                      e.target.value || "unknown",
                    )
                  }
                  hint="Isi unknown jika tidak ditampilkan."
                  minLength={2}
                  maxLength={100}
                />
              </div>
            </details>
          </fieldset>
          {!locked && (
            <>
              <Attestation checked={attested} onChange={setAttested} />
              <button
                className={PRIMARY}
                disabled={busy || !attested || readingImage || !canStart}
                type="submit"
              >
                Kunci ekspektasi
              </button>
            </>
          )}
        </form>
        {locked && (
          <>
            <Notice tone="ok">
              Ekspektasi dikunci di server: {a.record?.started_at}. Waktu ini
              mencatat alur kerja, bukan bukti independen bahwa pengujian
              dilakukan pada waktu tersebut.
            </Notice>
            {canRecordResults ? (
              <>
                <a
                  href="https://balizero.com/visa-oracle"
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${PRIMARY} inline-flex items-center`}
                >
                  Buka Visa Oracle
                </a>
                <p className="text-sm">
                  Tautan hanya membuka halaman baru. Masukkan fixture secara
                  manual; tidak ada data yang dikirim otomatis ke Oracle.
                </p>
              </>
            ) : (
              <Notice tone="wait">
                Lanjutkan mengunci ekspektasi kasus lainnya. Oracle dan
                pencatatan hasil dibuka setelah server mengonfirmasi kelima
                ekspektasi pada tanggal penugasan ini.
              </Notice>
            )}
          </>
        )}
      </Block>
      {locked && (
        <Block title="2. Catat hasil yang diamati">
          {validationError && <Notice role="alert">{validationError}</Notice>}
          <form onSubmit={submit} className="space-y-4">
            <fieldset
              disabled={busy || complete || readingImage || !canRecordResults}
              className="space-y-4"
            >
              <Area
                name="steps"
                label="Input persis dan langkah yang dilakukan"
                value={result.steps}
                onChange={(v) => changeResult("steps", v)}
              />
              <Choice
                name="actual-state"
                label="Status hasil aktual"
                value={result.actual_state}
                options={STATES}
                onChange={(v) => changeResult("actual_state", v)}
              />
              <Area
                name="actual"
                label="Hasil aktual dan alasan yang tampil"
                value={result.actual}
                onChange={(v) => changeResult("actual", v)}
              />
              <Area
                name="source-notes"
                label="URL / referensi sumber, serta informasi yang tidak ditampilkan"
                value={result.source_notes}
                onChange={(v) => changeResult("source_notes", v)}
              />
              <Area
                name="uncertainty"
                label="Bagaimana Oracle menangani ketidakpastian? Tulis tidak ditampilkan jika tidak ada."
                value={result.uncertainty}
                onChange={(v) => changeResult("uncertainty", v)}
              />
              <div className="grid gap-4 sm:grid-cols-2">
                <Choice
                  name="category"
                  label="Kategori temuan"
                  value={result.category}
                  onChange={(v) => changeResult("category", v)}
                  options={{
                    none: "Tidak ada isu yang diamati",
                    eligibility: "Kelayakan",
                    missing_question: "Pertanyaan hilang",
                    explanation: "Penjelasan",
                    reference: "Sumber / referensi",
                    navigation: "Navigasi",
                    privacy: "Privasi",
                  }}
                />
                <Choice
                  name="severity"
                  label="Dampak masalah"
                  value={result.severity}
                  onChange={(v) => changeResult("severity", v)}
                  options={{
                    none: "Tidak ada",
                    low: "Rendah",
                    medium: "Sedang",
                    high: "Tinggi",
                  }}
                />
                <Choice
                  name="certainty"
                  label="Kepastian penilaian Anda"
                  value={result.certainty}
                  onChange={(v) => changeResult("certainty", v)}
                  options={{
                    observation: "Observasi langsung",
                    hypothesis: "Dugaan",
                    expert: "Dikonfirmasi ahli",
                  }}
                />
                <Choice
                  name="reproducibility"
                  label="Hasil pengulangan"
                  value={result.reproducibility}
                  onChange={(v) => changeResult("reproducibility", v)}
                  options={{
                    not_retried: "Belum diulang",
                    same: "Sama",
                    different: "Berbeda",
                    blocked: "Pengulangan terhalang",
                  }}
                />
              </div>
              {!complete && (
                <div className="space-y-2">
                  <label htmlFor="screenshot" className={EYEBROW}>
                    Screenshot privat PNG/JPG/WebP
                  </label>
                  <input
                    id="screenshot"
                    type="file"
                    accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp"
                    className={`block w-full text-sm ${FOCUS}`}
                    onChange={(event) => selectScreenshot(event.currentTarget)}
                  />
                  <p className="text-xs text-[var(--tx-secondary)]">
                    Maksimal 600 KiB. Potong atau samarkan identitas pribadi
                    terlebih dahulu. Gambar ikut disimpan bersama draf atau
                    observasi ke server privat; tidak dikirim ke media publik.
                  </p>
                  {screenshotName && (
                    <p role="status" className="text-sm">
                      {screenshotName} siap disimpan.
                    </p>
                  )}
                </div>
              )}
              <Field
                id="evidence-ref"
                required={
                  result.reproducibility === "same" &&
                  !result.screenshot_base64 &&
                  !a.record?.result?.screenshot_available
                }
                label="Referensi bukti / nama screenshot / observasi kedua"
                value={result.evidence_ref}
                onChange={(e) => changeResult("evidence_ref", e.target.value)}
                maxLength={1000}
                hint="Tanpa data pribadi. File tidak diunggah oleh kolom ini; tulis lokasi bukti yang dapat ditinjau."
              />
              <Area
                name="comment"
                label="Komentar singkat dan dapat ditindaklanjuti (wajib, termasuk jika tidak ada isu)"
                value={result.comment}
                onChange={(v) => changeResult("comment", v)}
              />
              {!complete && (
                <Attestation checked={attested} onChange={setAttested} />
              )}
            </fieldset>
            {readingImage && <p role="status">Membaca gambar…</p>}
            {a.record?.result?.screenshot_available && (
              <div className="flex gap-3">
                <EvidenceLink id={a.id} />
                <button
                  type="button"
                  className={BUTTON}
                  disabled={busy}
                  onClick={() =>
                    void mutate(() => testingApi.removeScreenshot(a.id))
                  }
                >
                  Hapus lampiran
                </button>
              </div>
            )}
            {complete ? (
              <Notice tone="ok">
                Observasi dikirim: {a.record?.submitted_at}. Validasi reviewer
                tetap merupakan langkah terpisah.
              </Notice>
            ) : (
              <div className="flex flex-wrap gap-3">
                <button
                  className={BUTTON}
                  type="button"
                  disabled={
                    busy || !attested || readingImage || !canRecordResults
                  }
                  onClick={() => {
                    if (canRecordResults && !complete && !busy)
                      void mutate(() => testingApi.result(a.id, result, false));
                  }}
                >
                  Simpan draf ke server
                </button>
                <button
                  className={PRIMARY}
                  type="submit"
                  disabled={
                    busy || !attested || readingImage || !canRecordResults
                  }
                >
                  Kirim observasi
                </button>
              </div>
            )}
          </form>
        </Block>
      )}
    </div>
  );
}
function Attestation({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-3 text-sm">
      <input
        type="checkbox"
        className={`mt-1 size-5 ${FOCUS}`}
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        required
      />
      <span>
        Saya hanya menggunakan data sintetis dan tidak melakukan pengiriman
        keluar ke klien atau tim layanan.
      </span>
    </label>
  );
}
function ReviewForm({
  assignment: a,
  busy,
  mutate,
}: {
  assignment: Assignment;
  busy: boolean;
  mutate: Mutation;
}) {
  const reviewLocked = !!a.record?.review;
  const [review, setReview] = useState<Review>(
    a.record?.review || {
      verdict: "needs_expert_review",
      comment: "",
      reproduced: false,
      reproduction_evidence: "",
    },
  );
  return (
    <details className="border-t border-[var(--bz-border)] py-3">
      <summary className={`cursor-pointer py-2 ${FOCUS}`}>
        {a.slot} · {dayLabel(a.day)} · {a.scenario.title} ·{" "}
        {a.record?.review ? "Sudah ditinjau" : "Menunggu"}
      </summary>
      <div className="my-3 space-y-3 text-sm">
        {a.record?.result?.screenshot_available && <EvidenceLink id={a.id} />}
        <p>
          <strong>Ekspektasi:</strong> {a.record?.expected?.text}
        </p>
        {Object.entries(a.record?.result || {})
          .filter(
            ([key]) =>
              key !== "screenshot_base64" && key !== "screenshot_available",
          )
          .map(([key, value]) => (
            <p key={key} className="whitespace-pre-wrap break-words">
              <strong>{RESULT_LABELS[key] || key}:</strong>{" "}
              {key === "actual_state"
                ? STATES[value as keyof typeof STATES] || String(value)
                : String(value)}
            </p>
          ))}
      </div>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (reviewLocked || busy) return;
          void mutate(() =>
            testingApi.review(a.id, {
              verdict: review.verdict,
              comment: review.comment,
              reproduced: review.reproduced,
              reproduction_evidence: review.reproduction_evidence,
            }),
          );
        }}
      >
        {reviewLocked && (
          <Notice tone="wait">
            Tinjauan sudah tersimpan dan tidak dapat diubah.
          </Notice>
        )}
        <fieldset disabled={reviewLocked || busy} className="space-y-4">
          <Choice
            name={`verdict-${a.id}`}
            label="Keputusan reviewer"
            value={review.verdict}
            options={{
              confirmed_issue: "Isu terkonfirmasi",
              not_issue: "Bukan isu",
              needs_expert_review: "Perlu tinjauan ahli hukum",
            }}
            onChange={(v) =>
              setReview((r) => ({
                ...r,
                verdict: v as Review["verdict"],
                reproduced: false,
              }))
            }
          />
          <Area
            name={`review-${a.id}`}
            label="Alasan, bukti, dan referensi reviewer"
            value={review.comment}
            onChange={(v) => setReview((r) => ({ ...r, comment: v }))}
          />
          <label className="flex gap-3 text-sm">
            <input
              type="checkbox"
              checked={review.reproduced}
              disabled={review.verdict !== "confirmed_issue"}
              onChange={(e) =>
                setReview((r) => ({ ...r, reproduced: e.target.checked }))
              }
            />
            Reviewer telah mereproduksi isu yang sama
          </label>
          <Field
            id={`reproduction-${a.id}`}
            label="Referensi observasi kedua dan langkah pengulangan"
            required={review.reproduced}
            value={review.reproduction_evidence}
            onChange={(e) =>
              setReview((r) => ({
                ...r,
                reproduction_evidence: e.target.value,
              }))
            }
            maxLength={1000}
          />
          <button className={BUTTON} disabled={busy || reviewLocked}>
            Simpan tinjauan
          </button>
        </fieldset>
      </form>
    </details>
  );
}
function SlotForm({
  slot,
  candidates,
  busy,
  mutate,
}: {
  slot: CampaignData["slots"][number];
  candidates: { id: string; label: string }[];
  busy: boolean;
  mutate: Mutation;
}) {
  const [member, setMember] = useState(slot.member_id || "");
  const [reviewer, setReviewer] = useState(slot.reviewer);
  return (
    <form
      className="flex flex-wrap items-end gap-4 border-t border-[var(--bz-border)] pt-3"
      onSubmit={(e) => {
        e.preventDefault();
        void mutate(() => testingApi.slot(slot.slot, member || null, reviewer));
      }}
    >
      <div className="min-w-60 flex-1">
        <Choice
          name={`slot-${slot.slot}`}
          label={slot.slot}
          value={member}
          options={{
            "": "Belum ditetapkan",
            ...Object.fromEntries(candidates.map((c) => [c.id, c.label])),
          }}
          onChange={setMember}
        />
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={reviewer}
          onChange={(e) => setReviewer(e.target.checked)}
        />
        Reviewer
      </label>
      <button className={BUTTON} disabled={busy}>
        Simpan {slot.slot}
      </button>
    </form>
  );
}
