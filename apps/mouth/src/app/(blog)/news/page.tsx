'use client';

import * as React from 'react';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import {
  Newspaper,
  Clock,
  ExternalLink,
  Check,
  X,
  Filter,
  RefreshCw,
  AlertCircle,
  TrendingUp,
  Building2,
  Plane,
  Calculator,
  Home,
  Sparkles,
} from 'lucide-react';

interface NewsItem {
  id: string;
  title: string;
  summary: string;
  content: string;
  source: string;
  sourceUrl: string;
  category: string;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'approved' | 'rejected';
  publishedAt: string;
  scrapedAt: string;
  imageUrl?: string;
}

const CATEGORY_CONFIG: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  immigration: { icon: Plane, color: 'text-rose-400 bg-rose-500/10', label: 'Immigration' },
  business: { icon: Building2, color: 'text-orange-400 bg-orange-500/10', label: 'Business' },
  tax: { icon: Calculator, color: 'text-amber-400 bg-amber-500/10', label: 'Tax' },
  property: { icon: Home, color: 'text-emerald-400 bg-emerald-500/10', label: 'Property' },
  lifestyle: { icon: Sparkles, color: 'text-purple-400 bg-purple-500/10', label: 'Lifestyle' },
  tech: { icon: TrendingUp, color: 'text-blue-400 bg-blue-500/10', label: 'Tech' },
};

const PRIORITY_COLORS = {
  high: 'bg-red-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
};

export default function NewsPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved'>('all');
  const [isAdmin, setIsAdmin] = useState(false);

  // Check if admin (simple check - in production use auth)
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    setIsAdmin(urlParams.get('admin') === 'true');
  }, []);

  // Fetch news
  const fetchNews = async () => {
    setLoading(true);
    try {
      const statusParam = filter === 'all' ? '' : `?status=${filter}`;
      const res = await fetch(`/api/news${statusParam}`);
      const data = await res.json();
      if (data.success) {
        setNews(data.data);
      }
    } catch (error) {
      console.error('Failed to fetch news:', error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchNews();
  }, [filter]);

  // Update news status
  const updateStatus = async (id: string, status: 'approved' | 'rejected') => {
    try {
      const res = await fetch('/api/news', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, status }),
      });
      const data = await res.json();
      if (data.success) {
        setNews(prev => prev.map(n => n.id === id ? { ...n, status } : n));
      }
    } catch (error) {
      console.error('Failed to update status:', error);
    }
  };

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffHours < 1) return 'Just now';
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  };

  // Filter news for public view (only approved)
  const displayNews = isAdmin ? news : news.filter(n => n.status === 'approved');

  return (
    <div className="min-h-screen bg-[#051C2C]">
      {/* Hero Section */}
      <section className="border-b border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="max-w-3xl">
            <div className="mb-8">
              <Image
                src="/images/balizero-logo.png"
                alt="Bali Zero"
                width={80}
                height={80}
                className="rounded-full"
              />
            </div>
            <span className="text-[#2251ff] text-xs font-semibold uppercase tracking-wider mb-4 block">
              Intel Feed
            </span>
            <h1 className="font-serif text-4xl lg:text-5xl text-white leading-[1.1] mb-6">
              Latest{' '}
              <span className="text-[#e85c41]">Indonesia News</span>
            </h1>
            <p className="text-lg text-white/70 mb-8">
              Real-time updates on immigration, business, tax, and property in Indonesia.
              Curated by Zantara AI from 630+ sources.
            </p>

            {/* Admin Controls */}
            {isAdmin && (
              <div className="flex items-center gap-4 mb-8 p-4 rounded-xl bg-[#2251ff]/10 border border-[#2251ff]/30">
                <AlertCircle className="w-5 h-5 text-[#2251ff]" />
                <span className="text-[#2251ff] font-medium">Admin Mode</span>
                <div className="flex gap-2 ml-auto">
                  <button
                    onClick={() => setFilter('all')}
                    className={`px-3 py-1 rounded-lg text-sm ${filter === 'all' ? 'bg-white text-[#051C2C]' : 'text-white/60 hover:text-white'}`}
                  >
                    All
                  </button>
                  <button
                    onClick={() => setFilter('pending')}
                    className={`px-3 py-1 rounded-lg text-sm ${filter === 'pending' ? 'bg-yellow-500 text-black' : 'text-white/60 hover:text-white'}`}
                  >
                    Pending Review
                  </button>
                  <button
                    onClick={() => setFilter('approved')}
                    className={`px-3 py-1 rounded-lg text-sm ${filter === 'approved' ? 'bg-green-500 text-black' : 'text-white/60 hover:text-white'}`}
                  >
                    Approved
                  </button>
                </div>
                <button
                  onClick={fetchNews}
                  className="p-2 rounded-lg hover:bg-white/10"
                >
                  <RefreshCw className="w-4 h-4 text-white" />
                </button>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* News Grid */}
      <section className="py-16">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="rounded-xl bg-[#0a2540] p-6 animate-pulse">
                  <div className="h-4 bg-white/10 rounded mb-4 w-1/4"></div>
                  <div className="h-6 bg-white/10 rounded mb-3"></div>
                  <div className="h-4 bg-white/10 rounded mb-2"></div>
                  <div className="h-4 bg-white/10 rounded w-3/4"></div>
                </div>
              ))}
            </div>
          ) : displayNews.length === 0 ? (
            <div className="text-center py-16">
              <Newspaper className="w-16 h-16 text-white/20 mx-auto mb-4" />
              <p className="text-white/60 text-lg">No news items found</p>
              {isAdmin && filter === 'pending' && (
                <p className="text-white/40 text-sm mt-2">All items have been reviewed!</p>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {displayNews.map((item) => {
                const catConfig = CATEGORY_CONFIG[item.category] || CATEGORY_CONFIG.business;
                const Icon = catConfig.icon;

                return (
                  <div
                    key={item.id}
                    className={`rounded-xl border bg-[#0a2540] p-6 transition-all hover:border-[#2251ff]/50 ${
                      item.status === 'pending' ? 'border-yellow-500/50' :
                      item.status === 'rejected' ? 'border-red-500/50 opacity-50' :
                      'border-white/10'
                    }`}
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <div className={`w-8 h-8 rounded-lg ${catConfig.color} flex items-center justify-center`}>
                          <Icon className="w-4 h-4" />
                        </div>
                        <span className="text-white/60 text-xs">{catConfig.label}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className={`w-2 h-2 rounded-full ${PRIORITY_COLORS[item.priority]}`} title={`${item.priority} priority`} />
                        <span className="text-white/40 text-xs flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatDate(item.publishedAt)}
                        </span>
                      </div>
                    </div>

                    {/* Content */}
                    <h3 className="text-white font-medium mb-3 line-clamp-2 hover:text-[#2251ff] transition-colors">
                      {item.title}
                    </h3>
                    <p className="text-white/60 text-sm mb-4 line-clamp-3">
                      {item.summary}
                    </p>

                    {/* Source */}
                    <div className="flex items-center justify-between">
                      <a
                        href={item.sourceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#2251ff] text-xs flex items-center gap-1 hover:underline"
                      >
                        {item.source}
                        <ExternalLink className="w-3 h-3" />
                      </a>

                      {/* Admin Actions */}
                      {isAdmin && item.status === 'pending' && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => updateStatus(item.id, 'approved')}
                            className="p-2 rounded-lg bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors"
                            title="Approve"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => updateStatus(item.id, 'rejected')}
                            className="p-2 rounded-lg bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors"
                            title="Reject"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      )}

                      {isAdmin && item.status !== 'pending' && (
                        <span className={`text-xs px-2 py-1 rounded ${
                          item.status === 'approved' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                        }`}>
                          {item.status}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* CTA Section */}
      <section className="border-t border-white/10">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-8 py-16">
          <div className="text-center">
            <h2 className="font-serif text-2xl text-white mb-4">
              Need Help Understanding These Updates?
            </h2>
            <p className="text-white/60 mb-8 max-w-2xl mx-auto">
              Our team can help you navigate the latest regulations and take action.
            </p>
            <div className="flex flex-wrap gap-4 justify-center">
              <Link
                href="/chat"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#2251ff] text-white font-medium hover:bg-[#1a41cc] transition-colors"
              >
                <Image src="/images/zantara-lotus.png" alt="" width={24} height={24} />
                Ask Zantara AI
              </Link>
              <Link
                href="/services"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border border-white/20 text-white font-medium hover:bg-white/10 transition-colors"
              >
                Our Services
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
