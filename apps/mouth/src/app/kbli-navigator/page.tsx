import { redirect } from 'next/navigation';

export default function KBLINavigatorPage() {
  // Redirect to the static HTML file served from public/
  redirect('/kbli-navigator/index.html');
}
