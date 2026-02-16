import fs from 'fs';
import path from 'path';
import KBLIIntroOverlay from '@/components/kbli/KBLIIntroOverlay';

export default function KBLINavigatorPage() {
  const filePath = path.join(process.cwd(), 'public', 'kbli-navigator', 'index.html');
  const htmlContent = fs.readFileSync(filePath, 'utf8');

  return (
    <div className="relative w-full h-screen bg-[#2a2a2a] overflow-hidden">
      <KBLIIntroOverlay />
      <iframe 
        srcDoc={htmlContent}
        className="w-full h-full border-none"
        title="KBLI 2025 Navigator"
        allow="autoplay"
      />
    </div>
  );
}
