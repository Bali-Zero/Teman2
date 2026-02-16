import KBLIIntroOverlay from '@/components/kbli/KBLIIntroOverlay';

export default function KBLINavigatorPage() {
  return (
    <div className="relative w-full h-screen bg-[#2a2a2a] overflow-hidden">
      <KBLIIntroOverlay />
      <iframe 
        src="/kbli-navigator/index.html" 
        className="w-full h-full border-none"
        title="KBLI 2025 Navigator"
        allow="autoplay"
      />
    </div>
  );
}
