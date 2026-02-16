import fs from 'fs';
import path from 'path';
import KBLINavigatorClient from '@/components/kbli/KBLINavigatorClient';

export const metadata = {
  title: 'KBLI 2025 Navigator | Balizero',
  description: 'Intelligent Indonesian Business Classification Navigator with Zantara AI.',
};

export default function KBLINavigatorPage() {
  const filePath = path.join(process.cwd(), 'public', 'kbli-navigator', 'index.html');
  let htmlContent = '';
  
  try {
    htmlContent = fs.readFileSync(filePath, 'utf8');
  } catch (err) {
    console.error('Error reading KBLI Navigator index.html:', err);
    htmlContent = '<html><body><h1>KBLI Navigator Load Error</h1></body></html>';
  }

  return <KBLINavigatorClient htmlContent={htmlContent} />;
}
