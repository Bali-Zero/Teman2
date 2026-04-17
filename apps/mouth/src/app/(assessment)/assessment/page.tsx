"use client";

import { useState, useEffect, useCallback, useRef } from "react";

// ── Types ──────────────────────────────────────────────────────────
interface BlockState {
  answers: Record<string, string>;
  submitted: boolean;
  submitting: boolean;
  startedAt: number | null;
}

type Phase = "intro" | "briefing" | "blocks" | "done";

// ── Constants ──────────────────────────────────────────────────────
const CANDIDATE_NAME = "Subhi Darajat";
const BLOCK_TITLES = [
  "Blok 1 — Memahami Organisme",
  "Blok 2 — Medan Perangmu",
  "Blok 3 — Wilayah Baru",
];
const BLOCK_DURATIONS = [60, 60, 60]; // minutes per block
const BLOCK_DESCRIPTIONS = [
  "Baca briefing, eksplorasi repo di GitHub, lalu jawab pertanyaan tentang sistem Nuzantara.",
  "Area keahlianmu — SEO, content, advertising. Tunjukkan cara kerjamu yang sebenarnya.",
  "Navigasi codebase yang belum pernah kamu lihat. Yang dinilai: bagaimana kamu belajar.",
];

const BLOCKS: { id: string; label: string; placeholder: string }[][] = [
  // Block 1
  [
    {
      id: "1_1",
      label:
        '1.1 Alur Nyata (10 poin)\n\nSeorang klien menulis di WhatsApp: "I need a KITAS for my wife, she\'s Russian. What documents do I need and how much does it cost?"\n\nJelaskan langkah demi langkah apa yang terjadi di dalam Nuzantara — dari pesan masuk sampai klien menerima jawaban. Sebutkan komponen spesifik yang terlibat dan peran masing-masing.',
      placeholder: "Jelaskan alur dari pesan masuk sampai jawaban keluar...",
    },
    {
      id: "1_2",
      label:
        '1.2 Kapan Organisme Harus Berhenti (10 poin)\n\nDi briefing tertulis bahwa sistem mengambil keputusan otonom untuk 70% operasi. Tapi ada aturan: "Zero sebagai instansi terakhir — organisme mengusulkan, tidak memutuskan."\n\nBuat satu contoh konkret (boleh fiktif, tapi realistis) di mana sistem HARUS berhenti dan bertanya ke Zero. Jelaskan kenapa dalam kasus itu otonomi tidak cukup.',
      placeholder: "Contoh situasi di mana sistem harus berhenti...",
    },
    {
      id: "1_3",
      label:
        "1.3 Ketika Pro Mati (10 poin)\n\nPukul 03:00 WITA. Mac Pro mati (listrik padam). Mac Air masih hidup. Backend di Fly.io masih jalan.\n\n- Sistem apa yang berhenti bekerja?\n- Sistem apa yang tetap jalan normal?\n- Apa yang terjadi pada klien yang menulis di WhatsApp saat itu?\n- Ketika Pro kembali online, apa yang harus terjadi?",
      placeholder: "Analisis dampak ketika Mac Pro offline...",
    },
    {
      id: "1_4",
      label:
        "1.4 Prioritas di Bawah Tekanan (10 poin)\n\nSenin pagi, kamu buka dashboard dan menemukan 4 situasi:\n\n1. SEO Guardian: 47 halaman KBLI kehilangan ranking (top 3 → halaman 2)\n2. Klien VIP: menulis di WA hari Sabtu, Zantara jawab benar tapi klien minta bicara manusia\n3. Red Team Evaluator: survival rate turun 90% → 72%, 14 tes adversarial lolos\n4. War Room: 5 konten di weekend, 1 punya kesalahan fakta deadline visa\n\nUrutkan berdasarkan prioritas. Untuk masing-masing: kenapa prioritas itu, aksi pertama, berapa lama sebelum pindah.",
      placeholder: "Urutkan dan jelaskan prioritas...",
    },
  ],
  // Block 2
  [
    {
      id: "2_1",
      label:
        "2.1 Audit SEO — balizero.com (20 poin)\n\nBuka balizero.com dan subdomain-nya (kita, prime). Gunakan tool apa saja.\n\na) Temukan 3 masalah SEO konkret yang kamu lihat sekarang. Untuk setiap masalah: apa, kenapa, bagaimana memperbaiki, estimasi dampak.\n\nb) Temukan 3 peluang pertumbuhan organik yang belum dimanfaatkan. Untuk setiap peluang: keyword/topik, strategi, KPI.",
      placeholder: "Masalah SEO dan peluang pertumbuhan yang kamu temukan...",
    },
    {
      id: "2_2",
      label:
        '2.2 Brief Konten (10 poin)\n\nBali Zero ingin mempublikasikan artikel: "Perubahan aturan Golden Visa Indonesia 2026 — apa yang perlu diketahui investor asing"\n\nBuat content brief: target keyword (utama + secondary), search intent, struktur artikel (H2/H3), CTA, channel distribusi, estimasi waktu produksi.\n\nBoleh gunakan AI untuk riset — tapi brief-nya harus keputusanmu.',
      placeholder: "Content brief lengkap...",
    },
    {
      id: "2_3",
      label:
        "2.3 Strategi Ads — Budget Rp 7.500.000/bulan (10 poin)\n\nBuat strategi:\n- Platform mana dan kenapa\n- Targeting: siapa, di mana, kapan\n- Copy angle: pesan utama\n- Landing page: ke mana traffic, apa yang harus ada\n- Funnel: dari klik sampai jadi klien\n- KPI: apa yang diukur, target angka spesifik",
      placeholder: "Strategi advertising lengkap...",
    },
  ],
  // Block 3
  [
    {
      id: "3_1",
      label:
        "3.1 Eksplorasi Codebase (15 poin)\n\nBuka repo Nuzantara di GitHub. Navigasi dan jawab:\n\na) Berapa jumlah router API di backend? Di mana didefinisikan? (Verifikasi di kode, bukan dari briefing.)\n\nb) Temukan file di mana kepribadian Zantara didefinisikan (system prompt utama). Nama file dan direktori?\n\nc) Lihat daftar cron job Mac Air. Pilih 3 yang paling kritikal dan jelaskan kenapa.",
      placeholder: "Hasil eksplorasi codebase...",
    },
    {
      id: "3_2",
      label:
        "3.2 Baca Satu Service (15 poin)\n\nBuka apps/backend-rag/backend/services/ di GitHub. Pilih SATU service yang menarik.\n\n- Service mana dan kenapa menarik\n- Apa yang dilakukannya (3-4 kalimat)\n- Dengan service lain apa dia berinteraksi\n- Kalau harus memperbaiki, apa yang kamu ubah dan kenapa",
      placeholder: "Analisis service yang kamu pilih...",
    },
    {
      id: "3_3",
      label:
        "3.3 Regulasi Baru Masuk ke Sistem (10 poin)\n\nSkenario: mulai 1 Juni 2026, pemegang KITAS Investor harus menyerahkan Surat Keterangan Domisili digital saat perpanjangan.\n\nJelaskan step-by-step bagaimana memasukkan informasi ini ke sistem Nuzantara, dari pengumpulan info sampai Zantara bisa menjawab klien.\n\n- Tool/sistem apa yang digunakan?\n- Urutan langkah?\n- Apa yang manual vs otomatis?",
      placeholder: "Langkah-langkah memasukkan regulasi baru...",
    },
  ],
];

// ── Helpers ─────────────────────────────────────────────────────────
function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function formatTimestamp(): string {
  return new Date().toLocaleString("id-ID", {
    timeZone: "Asia/Makassar",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ── Component ──────────────────────────────────────────────────────
export default function AssessmentPage() {
  const [phase, setPhase] = useState<Phase>("intro");
  const [activeBlock, setActiveBlock] = useState(0);
  const [blocks, setBlocks] = useState<BlockState[]>([
    { answers: {}, submitted: false, submitting: false, startedAt: null },
    { answers: {}, submitted: false, submitting: false, startedAt: null },
    { answers: {}, submitted: false, submitting: false, startedAt: null },
  ]);
  const [elapsed, setElapsed] = useState(0);
  const [totalStarted, setTotalStarted] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bonusAnswer, setBonusAnswer] = useState("");
  const [bonusSubmitted, setBonusSubmitted] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Resume support: ?start=N skips to block N with prior blocks marked as submitted.
  // Used when the candidate has already completed earlier blocks and needs to continue.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const startParam = params.get("start");
    if (!startParam) return;
    const startIdx = Math.max(1, Math.min(3, parseInt(startParam, 10))) - 1;
    if (!Number.isFinite(startIdx) || startIdx <= 0) return;

    const now = Date.now();
    setBlocks((prev) => {
      const next = [...prev];
      for (let i = 0; i < startIdx; i++) {
        next[i] = {
          answers: {},
          submitted: true,
          submitting: false,
          startedAt: now,
        };
      }
      next[startIdx] = {
        ...next[startIdx],
        startedAt: now,
      };
      return next;
    });
    setActiveBlock(startIdx);
    setTotalStarted(now);
    setPhase("blocks");
  }, []);

  // Timer
  useEffect(() => {
    if (phase !== "blocks") return;
    const block = blocks[activeBlock];
    if (!block || block.submitted) return;

    timerRef.current = setInterval(() => {
      if (block.startedAt) {
        setElapsed(Math.floor((Date.now() - block.startedAt) / 1000));
      }
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [phase, activeBlock, blocks]);

  const startBlock = useCallback(
    (index: number) => {
      setBlocks((prev) => {
        const next = [...prev];
        if (!next[index].startedAt) {
          next[index] = { ...next[index], startedAt: Date.now() };
        }
        return next;
      });
      setActiveBlock(index);
      setElapsed(0);
      if (!totalStarted) setTotalStarted(Date.now());
    },
    [totalStarted],
  );

  const updateAnswer = useCallback(
    (questionId: string, value: string) => {
      setBlocks((prev) => {
        const next = [...prev];
        next[activeBlock] = {
          ...next[activeBlock],
          answers: { ...next[activeBlock].answers, [questionId]: value },
        };
        return next;
      });
    },
    [activeBlock],
  );

  const submitBlock = useCallback(
    async (index: number) => {
      const block = blocks[index];
      const questions = BLOCKS[index];
      setError(null);

      // Check at least one answer
      const hasAny = questions.some(
        (q) => (block.answers[q.id] || "").trim().length > 0,
      );
      if (!hasAny) {
        setError("Isi minimal satu jawaban sebelum mengirim.");
        return;
      }

      setBlocks((prev) => {
        const next = [...prev];
        next[index] = { ...next[index], submitting: true };
        return next;
      });

      const duration = block.startedAt
        ? Math.floor((Date.now() - block.startedAt) / 1000)
        : 0;
      const durationMin = Math.floor(duration / 60);
      const durationSec = duration % 60;

      // Build email body
      let body = `<h2>${BLOCK_TITLES[index]}</h2>`;
      body += `<p><strong>Kandidat:</strong> ${CANDIDATE_NAME}</p>`;
      body += `<p><strong>Waktu:</strong> ${formatTimestamp()} WITA</p>`;
      body += `<p><strong>Durasi:</strong> ${durationMin}m ${durationSec}s</p>`;
      body += `<hr/>`;

      for (const q of questions) {
        const answer = block.answers[q.id] || "(tidak dijawab)";
        body += `<h3>${q.id.replace("_", ".")}</h3>`;
        body += `<p style="white-space: pre-wrap; font-family: monospace; background: #f5f5f5; padding: 12px; border-radius: 6px;">${answer.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p>`;
      }

      try {
        const res = await fetch("/api/assessment/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            to: "zero@balizero.com",
            subject: `[Assessment] ${CANDIDATE_NAME} — ${BLOCK_TITLES[index]} (${durationMin}m ${durationSec}s)`,
            body,
          }),
        });

        if (!res.ok) {
          // Fallback: save locally and show mailto link
          throw new Error(`Server error ${res.status}`);
        }

        setBlocks((prev) => {
          const next = [...prev];
          next[index] = {
            ...next[index],
            submitted: true,
            submitting: false,
          };
          return next;
        });

        // Auto advance to next block or done
        if (index < 2) {
          setActiveBlock(index + 1);
          startBlock(index + 1);
        }
      } catch {
        // Fallback: copy to clipboard
        const plainText = questions
          .map(
            (q) =>
              `${q.id.replace("_", ".")}:\n${block.answers[q.id] || "(tidak dijawab)"}`,
          )
          .join("\n\n---\n\n");

        try {
          await navigator.clipboard.writeText(plainText);
          setError(
            "Server tidak tersedia. Jawaban sudah di-copy ke clipboard. Kirim manual via email ke zero@balizero.com.",
          );
        } catch {
          setError(
            "Server tidak tersedia. Screenshot jawaban kamu dan kirim ke zero@balizero.com.",
          );
        }

        setBlocks((prev) => {
          const next = [...prev];
          next[index] = { ...next[index], submitting: false };
          return next;
        });
      }
    },
    [blocks, startBlock],
  );

  const submitBonus = useCallback(async () => {
    if (!bonusAnswer.trim()) return;

    const body = `<h2>BONUS — Visi Kandidat</h2>
      <p><strong>Kandidat:</strong> ${CANDIDATE_NAME}</p>
      <p><strong>Waktu:</strong> ${formatTimestamp()} WITA</p>
      <hr/>
      <p style="white-space: pre-wrap; font-family: monospace; background: #f5f5f5; padding: 12px; border-radius: 6px;">${bonusAnswer.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</p>`;

    try {
      await fetch("/api/assessment/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          to: "zero@balizero.com",
          subject: `[Assessment] ${CANDIDATE_NAME} — BONUS Visi`,
          body,
        }),
      });
      setBonusSubmitted(true);
    } catch {
      setError("Gagal mengirim bonus. Screenshot dan kirim manual.");
    }
  }, [bonusAnswer]);

  const allSubmitted = blocks.every((b) => b.submitted);
  const limit = BLOCK_DURATIONS[activeBlock] * 60;
  const remaining = Math.max(0, limit - elapsed);
  const isOvertime = elapsed > limit;

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#0a0a0b] text-[#e8e6e1]">
      {/* Header */}
      <header className="border-b border-white/5 bg-[#0a0a0b]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              className="w-10 h-10 rounded-full"
            />
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-semibold text-white tracking-wide">
                BALI ZERO
              </span>
              <span className="text-xs text-white/40">Assessment 2026</span>
            </div>
          </div>
          {phase === "blocks" && (
            <div className="flex items-center gap-4">
              <div className="text-xs text-white/40">
                {BLOCK_TITLES[activeBlock]}
              </div>
              <div
                className={`font-mono text-lg tabular-nums ${isOvertime ? "text-accent-red-brand animate-pulse" : remaining < 300 ? "text-amber-400" : "text-white/80"}`}
              >
                {isOvertime ? "+" : ""}
                {formatTime(isOvertime ? elapsed - limit : remaining)}
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-10">
        {/* ── INTRO ─────────────────────────────────── */}
        {phase === "intro" && (
          <div className="space-y-8 animate-fadeIn">
            <div className="flex flex-col items-center text-center space-y-6 py-8">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/static/balizero-logo-clean.png"
                alt="Bali Zero"
                className="w-40 h-40 rounded-full shadow-2xl shadow-[#c23c2c]/20"
              />
              <div className="space-y-2">
                <div className="text-xs uppercase tracking-[0.3em] text-accent-red-brand font-semibold">
                  Bali Zero — Official
                </div>
                <h1 className="text-4xl font-bold tracking-tight">
                  Assessment Teknis-Strategis
                </h1>
                <p className="text-white/50 text-lg">Bali Zero + Nuzantara</p>
              </div>
            </div>

            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-6 space-y-4">
              <p className="text-white/70">
                Selamat datang,{" "}
                <span className="text-white font-medium">{CANDIDATE_NAME}</span>
                .
              </p>
              <div className="space-y-2 text-sm text-white/60">
                <p>
                  Assessment ini terdiri dari{" "}
                  <strong className="text-white/80">3 blok</strong>,
                  masing-masing ~60 menit:
                </p>
                <ul className="space-y-2 ml-4">
                  {BLOCK_TITLES.map((t, i) => (
                    <li key={t} className="flex items-start gap-2">
                      <span className="text-accent-red-brand font-mono text-xs mt-0.5 shrink-0">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <div>
                        <span className="text-white/80 font-medium">{t}</span>
                        <p className="text-white/40 text-xs mt-0.5">
                          {BLOCK_DESCRIPTIONS[i]}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="border-t border-white/5 pt-4 space-y-2 text-sm text-white/50">
                <p>
                  Gunakan laptop, internet, AI, browser — tool apa saja yang
                  biasa kamu pakai untuk bekerja.
                </p>
                <p>
                  Setiap blok dikirim otomatis saat kamu selesai. Timer tidak
                  menghentikanmu — kualitas {">"} kecepatan.
                </p>
                <p className="text-white/40">
                  Ini bukan ujian sekolah. Ini simulasi hari kerja pertamamu.
                </p>
              </div>
            </div>

            <button
              onClick={() => setPhase("briefing")}
              className="bg-accent-red-brand hover:bg-[#a83225] text-white px-8 py-3 rounded-lg font-medium transition-colors"
            >
              Mulai — Baca Briefing
            </button>
          </div>
        )}

        {/* ── BRIEFING ──────────────────────────────── */}
        {phase === "briefing" && (
          <div className="space-y-8 animate-fadeIn">
            <div className="space-y-2">
              <h1 className="text-2xl font-bold tracking-tight">
                Briefing Material
              </h1>
              <p className="text-white/50">
                Baca dengan seksama. Kamu akan membutuhkan informasi ini.
              </p>
            </div>

            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-6 space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center text-xs">
                  1
                </div>
                <div>
                  <p className="text-white/80 font-medium text-sm">
                    Briefing Bali Zero + Nuzantara
                  </p>
                  <p className="text-white/40 text-xs">
                    Sistem, arsitektur, filosofi, peranmu — 15 menit baca
                  </p>
                </div>
                <a
                  href="/assessment/briefing"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-auto text-accent-red-brand hover:text-[#e04535] text-sm font-medium"
                >
                  Buka Briefing &rarr;
                </a>
              </div>

              <div className="flex items-center gap-3">
                <div className="w-6 h-6 rounded bg-white/10 flex items-center justify-center text-xs">
                  2
                </div>
                <div>
                  <p className="text-white/80 font-medium text-sm">
                    Codebase GitHub (read-only)
                  </p>
                  <p className="text-white/40 text-xs">
                    Kamu akan butuh ini di Blok 1 dan Blok 3
                  </p>
                </div>
                <a
                  href="https://github.com/balizero/nuzantara"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="ml-auto text-accent-red-brand hover:text-[#e04535] text-sm font-medium"
                >
                  Buka Repository &rarr;
                </a>
              </div>
            </div>

            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-3 text-sm text-amber-200/80">
              Ketika siap, klik tombol di bawah. Timer blok pertama langsung
              berjalan.
            </div>

            <button
              onClick={() => {
                setPhase("blocks");
                startBlock(0);
              }}
              className="bg-accent-red-brand hover:bg-[#a83225] text-white px-8 py-3 rounded-lg font-medium transition-colors"
            >
              Saya Siap — Mulai Blok 1
            </button>
          </div>
        )}

        {/* ── BLOCKS ────────────────────────────────── */}
        {phase === "blocks" && (
          <div className="space-y-8 animate-fadeIn">
            {/* Block tabs */}
            <div className="flex gap-2">
              {BLOCK_TITLES.map((t, i) => (
                <button
                  key={t}
                  onClick={() => {
                    if (blocks[i].submitted || blocks[i].startedAt) {
                      setActiveBlock(i);
                      setElapsed(
                        blocks[i].startedAt
                          ? Math.floor(
                              (Date.now() - blocks[i].startedAt!) / 1000,
                            )
                          : 0,
                      );
                    }
                  }}
                  disabled={!blocks[i].startedAt && i !== activeBlock}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    i === activeBlock
                      ? "bg-white/10 text-white"
                      : blocks[i].submitted
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        : "bg-white/[0.03] text-white/30"
                  } ${!blocks[i].startedAt && i !== activeBlock ? "cursor-not-allowed" : "cursor-pointer"}`}
                >
                  {blocks[i].submitted ? "v " : ""}
                  Blok {i + 1}
                </button>
              ))}
            </div>

            {/* Block content */}
            {!blocks[activeBlock].submitted ? (
              <div className="space-y-6">
                <div className="space-y-1">
                  <h2 className="text-xl font-bold">
                    {BLOCK_TITLES[activeBlock]}
                  </h2>
                  <p className="text-white/40 text-sm">
                    {BLOCK_DESCRIPTIONS[activeBlock]}
                  </p>
                </div>

                {BLOCKS[activeBlock].map((q) => (
                  <div
                    key={q.id}
                    className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-5 space-y-3"
                  >
                    <label className="text-sm text-white/70 whitespace-pre-line leading-relaxed">
                      {q.label}
                    </label>
                    <textarea
                      value={blocks[activeBlock].answers[q.id] || ""}
                      onChange={(e) => updateAnswer(q.id, e.target.value)}
                      placeholder={q.placeholder}
                      rows={8}
                      className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-3 text-sm text-white/90 placeholder:text-white/20 focus:outline-none focus:ring-1 focus:ring-[#c23c2c]/50 focus:border-accent-red-brand/30 resize-y min-h-[120px] font-mono"
                    />
                  </div>
                ))}

                {error && (
                  <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-sm text-red-200/80">
                    {error}
                  </div>
                )}

                <div className="flex items-center justify-between">
                  <p className="text-xs text-white/30">
                    Jawaban dikirim ke tim Bali Zero saat kamu klik Kirim.
                  </p>
                  <button
                    onClick={() => submitBlock(activeBlock)}
                    disabled={blocks[activeBlock].submitting}
                    className="bg-accent-red-brand hover:bg-[#a83225] disabled:bg-white/10 disabled:text-white/30 text-white px-8 py-3 rounded-lg font-medium transition-colors flex items-center gap-2"
                  >
                    {blocks[activeBlock].submitting ? (
                      <>
                        <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Mengirim...
                      </>
                    ) : (
                      `Kirim Blok ${activeBlock + 1}`
                    )}
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-8 text-center space-y-3">
                <div className="text-emerald-400 text-2xl">Terkirim</div>
                <p className="text-white/50 text-sm">
                  {BLOCK_TITLES[activeBlock]} sudah dikirim ke tim Bali Zero.
                </p>
                {activeBlock < 2 && !blocks[activeBlock + 1].startedAt && (
                  <button
                    onClick={() => startBlock(activeBlock + 1)}
                    className="bg-accent-red-brand hover:bg-[#a83225] text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors mt-4"
                  >
                    Lanjut ke Blok {activeBlock + 2}
                  </button>
                )}
              </div>
            )}

            {/* Bonus section — appears after all 3 blocks submitted */}
            {allSubmitted && (
              <div className="space-y-6 border-t border-white/5 pt-8">
                <div className="space-y-1">
                  <h2 className="text-xl font-bold">
                    Bonus — Hanya Jika Mau (+10 poin)
                  </h2>
                  <p className="text-white/40 text-sm">
                    Kalau punya 3 bulan dan kebebasan penuh untuk meningkatkan
                    satu aspek Bali Zero, apa yang akan kamu lakukan?
                  </p>
                </div>

                {!bonusSubmitted ? (
                  <div className="space-y-4">
                    <textarea
                      value={bonusAnswer}
                      onChange={(e) => setBonusAnswer(e.target.value)}
                      placeholder="Visimu untuk Bali Zero..."
                      rows={8}
                      className="w-full bg-black/30 border border-white/10 rounded-lg px-4 py-3 text-sm text-white/90 placeholder:text-white/20 focus:outline-none focus:ring-1 focus:ring-[#c23c2c]/50 focus:border-accent-red-brand/30 resize-y min-h-[120px] font-mono"
                    />
                    <div className="flex justify-between">
                      <button
                        onClick={() => setPhase("done")}
                        className="text-white/40 hover:text-white/60 text-sm"
                      >
                        Lewati &rarr; Selesai
                      </button>
                      <button
                        onClick={submitBonus}
                        className="bg-accent-red-brand hover:bg-[#a83225] text-white px-6 py-2 rounded-lg text-sm font-medium transition-colors"
                      >
                        Kirim Bonus
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-4 text-center text-emerald-400 text-sm">
                      Bonus terkirim.
                    </div>
                    <button
                      onClick={() => setPhase("done")}
                      className="bg-accent-red-brand hover:bg-[#a83225] text-white px-8 py-3 rounded-lg font-medium transition-colors w-full"
                    >
                      Selesai
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── DONE ──────────────────────────────────── */}
        {phase === "done" && (
          <div className="text-center space-y-6 py-20 animate-fadeIn">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              className="w-32 h-32 rounded-full mx-auto shadow-2xl shadow-[#c23c2c]/30"
            />
            <div className="text-4xl">Selesai</div>
            <h1 className="text-2xl font-bold">
              Terima kasih, {CANDIDATE_NAME}
            </h1>
            <p className="text-white/50 max-w-md mx-auto">
              Semua jawaban sudah dikirim ke tim Bali Zero. Kami akan
              menghubungimu untuk langkah selanjutnya.
            </p>
            {totalStarted && (
              <p className="text-white/30 text-sm">
                Total waktu: {Math.floor((Date.now() - totalStarted) / 60000)}{" "}
                menit
              </p>
            )}
          </div>
        )}
      </main>

      <style jsx global>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeIn {
          animation: fadeIn 0.4s ease-out;
        }
      `}</style>
    </div>
  );
}
