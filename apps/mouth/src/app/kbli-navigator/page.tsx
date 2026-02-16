import fs from 'fs';
import path from 'path';

export default function KBLINavigatorPage() {
  // Read and serve the static HTML file
  const filePath = path.join(process.cwd(), 'public', 'kbli-navigator', 'index.html');
  const htmlContent = fs.readFileSync(filePath, 'utf8');

  return <div dangerouslySetInnerHTML={{ __html: htmlContent }} />;
}
