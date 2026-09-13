const PROMISE =
  "Kepatuhan usaha Anda, dikerjakan tim kami, dicek ulang oleh manusia.";

const SERVICES = [
  {
    name: "LKPM",
    detail:
      "Laporan Kegiatan Penanaman Modal disiapkan dan dilaporkan melalui OSS sesuai jadwal.",
  },
  {
    name: "Pajak bulanan",
    detail:
      "SPT Masa PPh dan PPN dihitung, disiapkan, dan dilaporkan setiap bulan.",
  },
  {
    name: "PSE",
    detail:
      "Pendaftaran Penyelenggara Sistem Elektronik lingkup privat untuk situs dan aplikasi usaha Anda.",
  },
];

const WA_GREETING =
  "Halo Nuzantara, saya ingin bertanya tentang kepatuhan usaha saya.";

function whatsappHref(): string | null {
  const digits = (process.env.NEXT_PUBLIC_NUZANTARA_WA ?? "").replace(
    /\D/g,
    "",
  );
  if (!digits) return null;
  return `https://wa.me/${digits}?text=${encodeURIComponent(WA_GREETING)}`;
}

export default function NuzantaraPage() {
  const waHref = whatsappHref();

  return (
    <>
      <main className="mx-auto w-full max-w-2xl flex-1 px-6 py-20">
        <h1 className="text-4xl font-bold tracking-tight">Nuzantara</h1>
        <p className="mt-4 text-lg text-[var(--text-secondary)]">{PROMISE}</p>

        <section className="mt-12" aria-labelledby="layanan">
          <h2 id="layanan" className="text-xl font-semibold">
            Apa yang kami kerjakan
          </h2>
          <ul className="mt-4 space-y-3">
            {SERVICES.map((s) => (
              <li key={s.name}>
                <span className="font-semibold">{s.name}</span>: {s.detail}
              </li>
            ))}
          </ul>
        </section>

        <section className="mt-12" aria-labelledby="kontak">
          <h2 id="kontak" className="text-xl font-semibold">
            Hubungi kami
          </h2>
          {waHref ? (
            <a
              href={waHref}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-block rounded-md bg-[var(--accent-whatsapp)] px-5 py-3 font-semibold text-[var(--accent-whatsapp-ink)]"
            >
              Chat lewat WhatsApp
            </a>
          ) : (
            <p className="mt-4" data-placeholder="NEXT_PUBLIC_NUZANTARA_WA">
              WhatsApp: {"<nomor WhatsApp>"}
            </p>
          )}
        </section>
      </main>

      <footer className="mx-auto w-full max-w-2xl px-6 py-8 text-sm text-[var(--text-secondary)]">
        <p>Nuzantara adalah layanan dari {"<nama PT>"}, sebuah PT PMA.</p>
        <p className="mt-1">Bahasa Indonesia</p>
      </footer>
    </>
  );
}
