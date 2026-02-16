import fs from 'fs';
import path from 'path';
import KBLIIntroOverlay from '@/components/kbli/KBLIIntroOverlay';

export default function KBLINavigatorPage() {
  // Legge il file HTML statico dal server
  const filePath = path.join(process.cwd(), 'public', 'kbli-navigator', 'index.html');
  const htmlContent = fs.readFileSync(filePath, 'utf8');

  return (
    <>
      <KBLIIntroOverlay />
      <div dangerouslySetInnerHTML={{ __html: htmlContent }} />
    </>
  );
}
