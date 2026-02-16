import fs from 'fs';
import path from 'path';
import KBLIIntroOverlay from '@/components/kbli/KBLIIntroOverlay';

export default function KBLINavigatorPage() {
  const filePath = path.join(process.cwd(), 'public', 'kbli-navigator', 'index.html');
  const htmlContent = fs.readFileSync(filePath, 'utf8');

  // Script per sincronizzare l'History API tra iframe e browser principale
  const historyFixScript = `
    <script>
      window.addEventListener('message', function(e) {
        if (e.data.type === 'NAVIGATE') {
          history.pushState(null, '', '/kbli-navigator#' + e.data.path);
        }
      });
    </script>
  `;

  return (
    <div className="relative w-full h-screen bg-[#2a2a2a] overflow-hidden">
      <KBLIIntroOverlay />
      <iframe 
        srcDoc={htmlContent}
        className="w-full h-full border-none"
        style={{ pointerEvents: 'auto' }}
        title="KBLI 2025 Navigator"
        id="kbli-frame"
        allow="autoplay"
      />
    </div>
  );
}
