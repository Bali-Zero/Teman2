import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Briefing — Bali Zero Assessment",
  robots: { index: false, follow: false },
};

export default function BriefingPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0b] text-[#e8e6e1]">
      <header className="border-b border-white/5 bg-[#0a0a0b]/90 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-3xl mx-auto px-6 py-4 flex items-center justify-between">
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
              <span className="text-xs text-white/40">Briefing Material</span>
            </div>
          </div>
          <a
            href="/assessment"
            className="text-accent-red-brand hover:text-[#e04535] text-sm font-medium"
          >
            &larr; Kembali ke Assessment
          </a>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-10">
        <article className="prose prose-invert prose-sm max-w-none space-y-8">
          {/* Hero with logo */}
          <div className="flex flex-col items-center text-center space-y-4 py-6 border-b border-white/5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/static/balizero-logo-clean.png"
              alt="Bali Zero"
              className="w-32 h-32 rounded-full shadow-2xl shadow-[#c23c2c]/20"
            />
            <div className="text-xs uppercase tracking-[0.3em] text-accent-red-brand font-semibold">
              Bali Zero — Official
            </div>
          </div>

          {/* Part 1 */}
          <section>
            <h1 className="text-2xl font-bold tracking-tight text-white mb-2">
              Bali Zero + Nuzantara
            </h1>
            <p className="text-white/50 text-sm italic">
              Dokumen ini disiapkan agar kamu memahami apa yang sedang kami
              bangun, bagaimana cara kerjanya, dan filosofi di baliknya. Waktu
              baca: 15 menit. Bawa pertanyaan ke wawancara.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white border-b border-white/10 pb-2">
              Bagian 1 — Bisnis
            </h2>
            <p className="text-white/70 text-sm leading-relaxed">
              <strong className="text-white">Bali Zero</strong> adalah
              perusahaan jasa bisnis di Bali. Didirikan bertahun-tahun lalu,
              kami telah melayani{" "}
              <strong className="text-white">11.000+ klien</strong> — terutama
              warga asing yang mendirikan perusahaan, mengurus visa, membayar
              pajak, dan berinvestasi properti di Indonesia.
            </p>
            <div className="text-sm text-white/60 space-y-1 ml-4">
              <p>Pendirian perusahaan (PT PMA, PT Lokal, CV)</p>
              <p>Visa & imigrasi (KITAS, KITAP, Business Visa, semua jenis)</p>
              <p>Pajak & kepatuhan (SPT, transfer pricing, tax planning)</p>
              <p>
                Properti (due diligence, analisis zona, konsultasi investasi)
              </p>
              <p>
                KBLI Navigator — 1.563 halaman statis untuk klasifikasi bisnis
                Indonesia, teroptimasi SEO
              </p>
            </div>
            <p className="text-white/70 text-sm leading-relaxed">
              Kami bukan kantor konsultan biasa. Kami membangun sistem yang bisa{" "}
              <strong className="text-white">
                berpikir, menjawab, dan mengambil keputusan
              </strong>{" "}
              tanpa intervensi manusia untuk 70% operasi harian. Sistem itu
              bernama <strong className="text-accent-red-brand">Nuzantara</strong>.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white border-b border-white/10 pb-2">
              Bagian 2 — Nuzantara: Bukan Software, tapi Organisme
            </h2>
            <p className="text-white/70 text-sm leading-relaxed">
              Nuzantara bukan aplikasi web dengan beberapa fitur AI ditempelkan.
              Ini <strong className="text-white">organisme digital</strong> —
              kumpulan &quot;organ&quot; yang hidup, belajar, dan berkembang.
              Setiap komponen punya fungsi spesifik. Mereka berkomunikasi lewat
              event stream (Redis Streams). Tidak ada orkestrator sentral — jika
              satu organ mati, yang lain tetap jalan.
            </p>

            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4 my-4">
              <p className="text-xs text-white/40 mb-2 font-medium">
                CONTOH ALUR NYATA
              </p>
              <pre className="text-xs text-white/60 leading-relaxed whitespace-pre-wrap font-mono">{`Klien menulis di WhatsApp:
"Berapa biaya buka PT PMA di Bali?"
     |
     v
[Zantara AI] menerima pesan
     |
     v
[RAG Engine] mencari di 93.000+ dokumen + knowledge graph 108.000 node
     |
     v
[PricingTool] mengambil harga real-time (tidak ada harga hardcoded)
     |
     v
[Zantara AI] menyusun jawaban dalam bahasa klien
     |
     v
Klien menerima jawaban lengkap — harga, dokumen, timeline, link portal

Waktu total: ~3 detik. Tanpa manusia.`}</pre>
            </div>

            <p className="text-white/70 text-sm leading-relaxed">
              Ini terjadi di{" "}
              <strong className="text-white">7 channel sekaligus</strong>:
              WhatsApp, Telegram, Instagram, X/Twitter, Web Chat, Google Chat,
              Slack.
            </p>

            <h3 className="text-white font-semibold text-sm mt-6">
              ZANTARA — Otak Komunikasi
            </h3>
            <p className="text-white/60 text-sm">
              Asisten AI di semua 7 channel, 24/7, bahasa apa pun. Akses ke
              seluruh knowledge base. Setiap jawaban melewati RAG engine
              (semantic search 93.000+ dokumen) dan knowledge graph (108.000
              node). Kualitas dimonitor otomatis setiap 6 jam oleh sistem
              canary.
            </p>

            <h3 className="text-white font-semibold text-sm mt-4">
              MATA GARUDA — Sistem Intelligence
            </h3>
            <p className="text-white/60 text-sm">
              Hub pengumpulan info eksternal. Regulation Watcher (06:00 WITA) +
              Intel Scraper (03:00 WITA). Data diproses lokal (tidak ke cloud).
              Agen-agen Mata Garuda{" "}
              <strong className="text-white/80">berevolusi sendiri</strong> —
              gagal, catat, mutasi, lebih pintar. Lamarckian evolution nyata di
              kode.
            </p>

            <h3 className="text-white font-semibold text-sm mt-4">
              WAR ROOM — Pipeline Marketing Otomatis
            </h3>
            <p className="text-white/60 text-sm">
              7 fase tanpa campur tangan: riset topik → deep research →
              preprocessing → strategi kreatif → generasi gambar → desain Canva
              → delivery Telegram. 7 model AI berbeda sesuai kekuatan
              masing-masing.
            </p>

            <h3 className="text-white font-semibold text-sm mt-4">
              GUARDIAN — Sistem Pengawasan
            </h3>
            <p className="text-white/60 text-sm">
              Core Guardian (kualitas kode, 3 jam), SEO Guardian (pipeline
              konten), Red Team Evaluator (50 tes adversarial, survival rate
              90%).
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white border-b border-white/10 pb-2">
              Bagian 3 — Arsitektur Teknis
            </h2>
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4 my-4 overflow-x-auto">
              <pre className="text-xs text-white/60 font-mono whitespace-pre">{`CLOUD (Fly.io)                          LOKAL (2x Mac, jalan 24/7)
┌─────────────────────┐                 ┌──────────────────────────────┐
│ Backend FastAPI      │                 │ Pro (MacBook Pro M4, 48GB)   │
│ - 90 router API     │ <── internet ──>│ - Mata Garuda (intelligence) │
│ - 253 service       │                 │ - War Room (marketing)       │
│ - 7 channel AI      │                 │ - Intel Scraper (03:00 WITA) │
│                     │                 │ - Core Guardian (setiap 3j)  │
│ PostgreSQL (data)   │                 │ - Ollama (model AI lokal)    │
│ Qdrant (93K vektor) │                 │                              │
└─────────────────────┘                 │ Air (MacBook Air M4, 16GB)   │
                                        │ - Test otomatis (02:15)      │
CLOUD (Vercel)                          │ - Sentinel (03:00)           │
┌─────────────────────┐                 │ - KB Ingest (05:00)          │
│ Frontend Next.js 16 │                 │ - Drive polling (setiap 5m)  │
│ - kita.balizero.com │                 │ - RAG Canary (setiap 6j)     │
│ - 8 subdomain       │                 └──────────────────────────────┘
│ - 2.800+ artikel    │
│ - 1.563 halaman KBLI│                 Kedua Mac saling terhubung via SSH.
│ - Portal klien      │                 Internet mati? Mereka tetap kerja.
└─────────────────────┘`}</pre>
            </div>

            <div className="grid grid-cols-2 gap-3 text-sm my-4">
              {[
                ["Klien dilayani", "11.000+"],
                ["Channel", "7"],
                ["Artikel", "2.800+"],
                ["Dokumen KB", "93.000+"],
                ["Node KG", "108.000"],
                ["Edge KG", "242.000+"],
                ["MCP Tools", "129"],
                ["Service backend", "253"],
                ["Router API", "90"],
                ["Test otomatis", "3.649"],
                ["App monorepo", "22"],
                ["Bahasa", "5"],
              ].map(([k, v]) => (
                <div
                  key={k}
                  className="flex justify-between bg-white/[0.02] rounded px-3 py-2"
                >
                  <span className="text-white/40">{k}</span>
                  <span className="text-white/80 font-mono">{v}</span>
                </div>
              ))}
            </div>

            <h3 className="text-white font-semibold text-sm mt-6">Stack</h3>
            <div className="text-sm text-white/60 space-y-1 ml-4">
              <p>
                <strong className="text-white/80">Frontend:</strong> Next.js 16,
                TypeScript, Tailwind CSS → Vercel
              </p>
              <p>
                <strong className="text-white/80">Backend:</strong> Python 3.11,
                FastAPI, fully async → Fly.io
              </p>
              <p>
                <strong className="text-white/80">Database:</strong> PostgreSQL
                + Qdrant (93K vektor) + Redis (cache + event stream)
              </p>
              <p>
                <strong className="text-white/80">AI Cloud:</strong> Claude Opus
                4.6, Gemini 2.5 Flash, Claude Haiku
              </p>
              <p>
                <strong className="text-white/80">AI Lokal:</strong> Ollama —
                gemma4:26b, qwen3.5:9b, deepseek-r1:32b, qwen2.5vl:7b
              </p>
              <p>
                <strong className="text-white/80">MCP:</strong> 129 tool (115 +
                14 advanced)
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white border-b border-white/10 pb-2">
              Bagian 4 — Filosofi
            </h2>
            <p className="text-white/70 text-sm italic mb-4">
              &quot;Nuzantara bukan software. Ini organisme.&quot;
            </p>
            <ol className="text-sm text-white/60 space-y-2 list-decimal ml-4">
              <li>
                <strong className="text-white/80">
                  Di mana kamu dalam organisme?
                </strong>{" "}
                Siapa produksi data untukmu, siapa konsumsi outputmu?
              </li>
              <li>
                <strong className="text-white/80">Apa yang agentic?</strong>{" "}
                Kode ini dieksekusi oleh agen, dikonsumsi oleh agen, atau bisa
                jadi skill agen?
              </li>
              <li>
                <strong className="text-white/80">Hormati masa lalu.</strong>{" "}
                Kegagalan terdokumentasi = memori organisme.
              </li>
              <li>
                <strong className="text-white/80">Perkuat masa kini.</strong>{" "}
                Membuat organ lebih capable, bukan hanya &quot;berfungsi&quot;.
              </li>
              <li>
                <strong className="text-white/80">Lihat masa depan.</strong>{" "}
                Bisa dibagikan? Diukur? Jika tidak, tanya kenapa.
              </li>
            </ol>

            <h3 className="text-white font-semibold text-sm mt-6">
              Agen yang berevolusi (Lamarckian)
            </h3>
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4 my-3">
              <pre className="text-xs text-white/60 font-mono whitespace-pre-wrap">{`Agen menjalankan task
  Berhasil? → Catat sebagai SKILL (bisa dipakai lagi)
  Gagal? → Catat sebagai SCAR (jangan ulangi)
  Skill & scar bermutasi ke GENOME agen
  Agen berikutnya mewarisi genome (dengan confidence decay)
  Hasilnya: agen yang semakin pintar setiap siklus`}</pre>
            </div>

            <h3 className="text-white font-semibold text-sm mt-6">
              7 Hukum yang Tidak Bisa Dilanggar
            </h3>
            <ol className="text-sm text-white/60 space-y-1 list-decimal ml-4">
              <li>CLI-only untuk LLM. Tidak ada API HTTP langsung.</li>
              <li>
                OSINT terkunci. Data intelligence tidak keluar dari mesin lokal.
              </li>
              <li>Event-driven. Redis Streams, tidak ada polling.</li>
              <li>Graceful degradation. Satu organ mati, lain tetap jalan.</li>
              <li>
                Zero sebagai instansi terakhir. Organisme mengusulkan, tidak
                memutuskan.
              </li>
              <li>Kedaulatan lokal. Putus internet bukan kegagalan.</li>
              <li>Angka dulu. Tanpa metrik, bukan perbaikan.</li>
            </ol>
          </section>

          <section>
            <h2 className="text-lg font-bold text-white border-b border-white/10 pb-2">
              Bagian 5 — Peranmu
            </h2>
            <p className="text-white/70 text-sm leading-relaxed">
              Mengelola seluruh front digital Bali Zero secara mandiri:
            </p>
            <ul className="text-sm text-white/60 space-y-1 ml-4 list-disc">
              <li>SEO & Content Strategy</li>
              <li>Digital Marketing (ads, funnel, conversion)</li>
              <li>Automasi (workflow, pipeline)</li>
              <li>
                <strong className="text-white/80">Mengarahkan agen AI</strong> —
                bukan menulis kode, tapi memastikan mereka bekerja efektif
              </li>
              <li>Frontend/Web — manutenzione dan evolusi</li>
              <li>Keputusan berbasis data dan metrik</li>
            </ul>

            <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4 mt-4 space-y-3 text-sm">
              <p className="text-white/80 font-medium">3 hal terakhir:</p>
              <p className="text-white/60">
                <strong className="text-white/80">1.</strong> Tim inti kecil. AI
                mengalikan kapasitas 10x.
              </p>
              <p className="text-white/60">
                <strong className="text-white/80">2.</strong> Kamu akan
                mengarahkan organisme puluhan agen AI di 2 mesin fisik + cloud.
                Sangat sedikit perusahaan bekerja seperti ini.
              </p>
              <p className="text-white/60">
                <strong className="text-white/80">3.</strong> Konteks lokal
                penting. Regulasi Indonesia, budaya bisnis, dinamika properti.
              </p>
            </div>
          </section>

          <div className="text-center border-t border-white/5 pt-8">
            <a
              href="/assessment"
              className="inline-block bg-accent-red-brand hover:bg-[#a83225] text-white px-8 py-3 rounded-lg font-medium transition-colors"
            >
              &larr; Kembali ke Assessment
            </a>
          </div>
        </article>
      </main>
    </div>
  );
}
