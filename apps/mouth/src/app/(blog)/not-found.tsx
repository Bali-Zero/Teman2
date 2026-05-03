import Link from 'next/link';
import { FileQuestion, ArrowLeft, Search } from 'lucide-react';

export default function BlogNotFound() {
  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-full bg-accent-blue-editorial/10 flex items-center justify-center">
            <FileQuestion className="w-8 h-8 text-accent-blue-editorial" />
          </div>
        </div>
        <h1 className="text-3xl font-bold text-white mb-3">Article not found</h1>
        <p className="text-muted-cool mb-8">
          The article you&apos;re looking for doesn&apos;t exist or may have been moved.
        </p>
        <div className="flex justify-center gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg bg-accent-blue-editorial text-white text-sm font-medium hover:bg-[#1a3fd9] transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            All Articles
          </Link>
          <Link
            href="/news"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg border border-white/10 text-white text-sm font-medium hover:bg-white/5 transition-colors"
          >
            <Search className="w-4 h-4" />
            Latest News
          </Link>
        </div>
      </div>
    </div>
  );
}
