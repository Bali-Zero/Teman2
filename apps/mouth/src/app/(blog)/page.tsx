import { redirect } from 'next/navigation';

/**
 * Homepage redirects to /news
 */
export default function HomePage() {
  redirect('/news');
}
