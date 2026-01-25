# ⚛️ NUZANTARA FRONTEND CODEBASE (Snapshot)

**Generated:** 2026-01-23
**Focus:** Chat Interface & App Shell

## 1. Chat Page (`apps/mouth/src/app/chat/page.tsx`)

````tsx
/**
 * Chat Page - Refactored Modular Architecture
 *
 * Lightweight orchestrator that composes custom hooks and UI components.
 * Reduced from 1938 lines to ~250 lines by extracting logic into hooks.
 *
 * @module ChatPage
 */

'use client';

import { Loader2 } from 'lucide-react';

// Custom Hooks
import { useChatPage } from '@/hooks/useChatPage';
import type { Message, AgentStep } from '@/types';

// Components
import { ChatHeader } from '@/components/chat/ChatHeader';
import { ChatSidebar } from '@/components/chat/ChatSidebar';
import { ChatMessageListVirtualized } from '@/components/chat/ChatMessageListVirtualized';
import { ChatInputBar } from '@/components/chat/ChatInputBar';
import { ImageGenModal } from '@/components/chat/ImageGenModal';
import { SearchDocsModal } from '@/components/search/SearchDocsModal';
import { Toast } from '@/components/chat/Toast';

/**
 * Chat Page Component - Modular Architecture
 *
 * This is a lightweight orchestrator that composes:
 * - Custom hooks for business logic (useChatPage)
 * - UI components for rendering
 *
 * Responsibilities:
 * - Layout and composition only
 * - No business logic (all in hooks)
 */
export default function ChatPage() {
  const {
    // State
    isInitialLoading,
    displayMessages,
    userName,
    userAvatar,
    showUserMenu,
    toast,
    isPending,
    currentStatus,
    streamingSteps,
    imageModalOpen,

    // Refs
    messagesEndRef,
    fileInputRef,

    // Hooks
    chatInput,
    sidebar,
    conversations,
    teamStatus,
    audioRecorder,

    // Handlers
    handleSend,
    handleNewChat,
    handleConversationClick,
    handleDeleteConversation,
    handleAvatarChange,
    handleImageGenSubmit,
    toggleClock,
    showToast,
    setShowUserMenu,
    setToast,
    setImageModalOpen,
  } = useChatPage();

  // Loading state
  if (isInitialLoading) {
    return (
      <div className="flex h-screen bg-[#202020] text-white items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#202020] text-white">
      {/* Hidden file input for avatar upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleAvatarChange}
        accept="image/*"
        className="hidden"
      />

      {/* Toast Notification */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Sidebar */}
      <ChatSidebar
        isOpen={sidebar.sidebarOpen}
        onClose={sidebar.closeSidebar}
        onNewChat={handleNewChat}
        onConversationClick={handleConversationClick}
        onDeleteConversation={handleDeleteConversation}
        onSearchDocsOpen={sidebar.openSearchDocs}
        conversations={conversations.conversations}
        currentConversationId={conversations.currentConversationId}
        isLoading={conversations.isLoading}
      />

      {/* Search Docs Modal */}
      <SearchDocsModal
        open={sidebar.isSearchDocsOpen}
        onClose={sidebar.closeSearchDocs}
        onInsert={(text) => {
          chatInput.setInput(chatInput.input ? `${chatInput.input}\n${text}` : text);
        }}
        initialQuery={chatInput.input}
      />

      {/* Image Generation Modal */}
      <ImageGenModal
        isOpen={imageModalOpen}
        onClose={() => setImageModalOpen(false)}
        onSubmit={handleImageGenSubmit}
      />

      <main className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <ChatHeader
          isSidebarOpen={sidebar.sidebarOpen}
          onToggleSidebar={sidebar.toggleSidebar}
          isClockIn={teamStatus.isClockIn}
          isClockLoading={teamStatus.isLoading}
          onToggleClock={toggleClock}
          messagesCount={displayMessages.length}
          isWsConnected={true}
          userName={userName}
          userAvatar={userAvatar}
          showUserMenu={showUserMenu}
          onToggleUserMenu={() => setShowUserMenu(!showUserMenu)}
          userMenuRef={fileInputRef}
          avatarInputRef={fileInputRef}
          onAvatarUpload={handleAvatarChange}
          onShowToast={showToast}
        />

        {/* Messages Area */}
        <ChatMessageListVirtualized
          messages={displayMessages.map(
            (m): Message => ({
              id: m.id,
              role: m.role,
              content: m.content,
              timestamp: m.timestamp,
              sources: m.sources,
              imageUrl: m.imageUrl,
              steps: m.steps
                ? (
                  (m.steps.map((step) => ({
                    type: step.type as AgentStep['type'],
                    data: step.data,
                    timestamp: step.timestamp,
                  })) as AgentStep[])
                ) : undefined,
              currentStatus: m.isPending || m.isStreaming ? currentStatus : undefined,
              verification_score: undefined,
              metadata: m.metadata,
            })
          )}
          isLoading={isPending}
          thinkingElapsedTime={0}
          userAvatar={userAvatar}
          messagesEndRef={messagesEndRef}
          onFollowUpClick={(question) => {
            chatInput.setInput(question);
            setTimeout(() => handleSend(), 10);
          }}
          onSetInput={chatInput.setInput}
          onOpenSearchDocs={sidebar.openSearchDocs}
        />

        {/* Input Bar */}
        <ChatInputBar
          input={chatInput.input}
          setInput={chatInput.setInput}
          isLoading={isPending}
          showImagePrompt={imageModalOpen}
          setShowImagePrompt={setImageModalOpen}
          onSend={handleSend}
          onImageGenerate={() => setImageModalOpen(true)}
          showAttachMenu={false}
          setShowAttachMenu={() => {}}
          attachMenuRef={chatInput.imageInputRef}
          fileInputRef={chatInput.imageInputRef}
          onFileChange={async (e) => {
            chatInput.handleImageAttach(e);
          }}
          isRecording={audioRecorder.isRecording}
          recordingTime={audioRecorder.recordingTime}
          onStartRecording={audioRecorder.startRecording}
          onStopRecording={audioRecorder.stopRecording}
          onToggleRecording={async () => {
            if (audioRecorder.isRecording) {
              audioRecorder.stopRecording();
            } else {
              try {
                await audioRecorder.startRecording();
              } catch (error) {
                const errorMessage = error instanceof Error ? error.message : String(error);
                if (errorMessage.includes('Permission denied')) {
                  showToast(
                    'Microphone access denied. Please allow microphone access in your browser settings.',
                    'error'
                  );
                } else if (errorMessage.includes('NotFoundError')) {
                  showToast(
                    'No microphone found. Please connect a microphone and try again.',
                    'error'
                  );
                } else {
                  showToast('Failed to access microphone. Please try again.', 'error');
                }
              }
            }
          }}
        />
      </main>
    </div>
  );
}

## 2. Root Layout (`apps/mouth/src/app/layout.tsx`)

```tsx
import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import { Toaster } from 'sonner';
import { headers } from 'next/headers';
import { OrganizationJsonLd, LocalBusinessJsonLd, WebsiteJsonLd } from '@/components/seo';
import { QueryProvider } from '@/components/providers/QueryProvider';
import { WebVitalsMonitor } from '@/components/providers/WebVitalsMonitor';
import { SERVICES_DATA } from '@/data/services_data';
import { getArticleBySlug } from '@/lib/blog/articles';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

// Production URL - uses environment variable or falls back to production domain
const appUrl =
  process.env.NEXT_PUBLIC_PUBLIC_URL ||
  (typeof window !== 'undefined' ? window.location.origin : 'https://balizero.com');

export const metadata: Metadata = {
  metadataBase: new URL(appUrl),
  title: {
    default: 'Bali Zero | Visa, Business & Immigration Experts in Bali, Indonesia',
    template: '%s | Bali Zero',
  },
  description:
    'Expert visa, immigration, company setup, and business consulting services in Bali, Indonesia. PT PMA registration, KITAS, Golden Visa, tax compliance. Trusted by 1000+ expats.',
  keywords:
    [
      // Primary keywords
      'bali visa',
      'indonesia visa',
      'kitas bali',
      'pt pma indonesia',
      'company setup bali',
      'business license indonesia',
      'golden visa indonesia',
      // Long-tail keywords
      'how to get kitas in bali',
      'start business in indonesia foreigner',
      'retirement visa indonesia',
      'digital nomad visa bali',
      'pt pma registration process',
      'indonesian work permit',
      // Local SEO
      'visa agent bali',
      'immigration consultant bali',
      'notaris bali',
      'tax consultant bali',
      'company formation bali',
      // Brand
      'bali zero',
      'zantara ai',
      'bali zero team',
    ],
  authors: [{ name: 'Bali Zero Team', url: 'https://balizero.com' }],
  creator: 'Bali Zero',
  publisher: 'Bali Zero',
  category: 'Business Services',
  // Icons are auto-detected by Next.js from app/icon.png and app/apple-icon.png
  // No explicit configuration needed - Next.js 13+ App Router handles this automatically
  openGraph: {
    type: 'website',
    locale: 'en_US',
    alternateLocale: ['id_ID'],
    url: appUrl,
    title: 'Bali Zero | #1 Visa & Business Experts in Bali, Indonesia',
    description:
      'Expert visa, immigration, company setup, and business consulting services in Bali. PT PMA, KITAS, Golden Visa, tax compliance. Trusted by 1000+ expats.',
    siteName: 'Bali Zero',
    images: [
      {
        url: '/static/og-image.jpg',
        width: 1200,
        height: 630,
        alt: 'Bali Zero - Visa & Business Experts in Bali',
        type: 'image/jpeg',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Bali Zero | Visa & Business Experts in Bali',
    description:
      'Expert visa, immigration, company setup services in Bali. Trusted by 1000+ expats.',
    images: ['/static/og-image.jpg'],
    creator: '@balizero',
    site: '@balizero',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  alternates: {
    canonical: appUrl,
    languages: {
      'en-US': appUrl,
      'id-ID': `${appUrl}/id`,
    },
  },
  verification: {
    google: process.env.GOOGLE_SITE_VERIFICATION || '',
    // Add when ready: yandex, bing
  },
  other: {
    // AI/LLM optimization - for ChatGPT, Claude, Perplexity, Gemini
    'ai-content-declaration': 'human-created',
    'llms-txt': '/llms.txt',
    'ai-plugin': '/.well-known/ai-plugin.json',
    // Semantic information for AI
    subject: 'Visa, Immigration, Business Consulting, Indonesia, Bali',
    coverage: 'Indonesia, Bali, Southeast Asia',
    distribution: 'Global',
    rating: 'General',
    'revisit-after': '7 days',
    // Business identity
    contact: 'info@balizero.com',
    'reply-to': 'info@balizero.com',
    'geo.region': 'ID-BA',
    'geo.placename': 'Bali, Indonesia',
    'geo.position': '-8.4095;115.1889',
    ICBM: '-8.4095, 115.1889',
  },
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>)
{
  // Get current pathname to inject page-specific JSON-LD schemas
  const headersList = await headers();
  const pathname = headersList.get('x-pathname') || headersList.get('x-invoke-path') || '';
  const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || 'https://balizero.com';

  // Array to collect all page-specific schemas
  const pageSchemas: any[] = [];

  // 1. SERVICE DETAIL PAGES: /services/[slug]
  const serviceMatch = pathname.match(/^
/services/([^
/]+)$/);
  const serviceSlug = serviceMatch ? serviceMatch[1] : null;
  const service = serviceSlug ? SERVICES_DATA[serviceSlug] : null;

  if (service) {
    const serviceType = serviceSlug === 'visa' ? 'GovernmentService' : 'ProfessionalService';

    const serviceSchema = {
      '@context': 'https://schema.org',
      '@type': serviceType,
      name: service.name,
      description: service.description,
      provider: {
        '@type': 'Organization',
        name: 'Bali Zero',
        url: baseUrl,
        logo: `${baseUrl}/assets/logo/balizero-logo.png`,
        contactPoint: {
          '@type': 'ContactPoint',
          telephone: '+62-859-0436-9574',
          contactType: 'customer service',
          availableLanguage: ['English', 'Indonesian'],
        },
      },
      areaServed: {
        '@type': 'Country',
        name: 'Indonesia',
      },
      offers: service.packages
        .filter((pkg) => pkg.price !== 'Contact')
        .map((pkg) => ({
          '@type': 'Offer',
          name: pkg.name,
          description: pkg.description,
          price: pkg.price.replace(/\./g, ''),
          priceCurrency: 'IDR',
          availability: 'https://schema.org/InStock',
          validFrom: '2026-01-01',
        })),
      serviceType: service.name,
      hoursAvailable: service.timeline,
    };

    const faqSchema = {
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: service.faqs.map((faq) => ({
        '@type': 'Question',
        name: faq.question,
        acceptedAnswer: {
          '@type': 'Answer',
          text: faq.answer,
        },
      })),
    };

    pageSchemas.push(serviceSchema, faqSchema);
  }

  // 2. ARTICLE PAGES: /[category]/[slug]
  const articleMatch = pathname.match(/^
/([^n/]+)/([^
/]+)$/);
  if (articleMatch) {
    const [, category, slug] = articleMatch;
    try {
      const article = await getArticleBySlug(category, slug);
      if (article) {
        const articleUrl = `${baseUrl}/${category}/${slug}`;
        const imageUrl = article.coverImage?.startsWith('http')
          ? article.coverImage
          : `${baseUrl}${article.coverImage || '/static/og-image.jpg'}`;

        // Article schema
        const articleSchema = {
          '@context': 'https://schema.org',
          '@type': 'Article',
          headline: article.title,
          description: article.excerpt || article.subtitle || article.title,
          url: articleUrl,
          image: {
            '@type': 'ImageObject',
            url: imageUrl,
            width: 1200,
            height: 630,
          },
          datePublished: article.publishedAt?.toISOString() || article.createdAt.toISOString(),
          dateModified: article.updatedAt.toISOString(),
          author: {
            '@type': article.author.role === 'AI Immigration Advisor' ? 'Organization' : 'Person',
            name: article.author.name || 'Bali Zero Editorial',
            url: baseUrl,
          },
          publisher: {
            '@type': 'Organization',
            name: 'Bali Zero',
            logo: {
              '@type': 'ImageObject',
              url: `${baseUrl}/static/balizero-logo-clean.png`,
              width: 200,
              height: 200,
            },
          },
          mainEntityOfPage: {
            '@type': 'WebPage',
            '@id': articleUrl,
          },
          keywords: article.tags?.join(', '),
          wordCount: article.readingTime ? article.readingTime * 200 : undefined,
          articleSection: category,
          inLanguage: 'en-US',
        };

        // Breadcrumb schema
        const breadcrumbSchema = {
          '@context': 'https://schema.org',
          '@type': 'BreadcrumbList',
          itemListElement: [
            {
              '@type': 'ListItem',
              position: 1,
              name: 'Home',
              item: baseUrl,
            },
            {
              '@type': 'ListItem',
              position: 2,
              name: 'Insights',
              item: `${baseUrl}/insights`,
            },
            {
              '@type': 'ListItem',
              position: 3,
              name: article.category,
              item: `${baseUrl}/insights/${article.category}`,
            },
            {
              '@type': 'ListItem',
              position: 4,
              name: article.title,
              item: articleUrl,
            },
          ],
        };

        pageSchemas.push(articleSchema, breadcrumbSchema);
      }
    } catch (error) {
      // Silently fail - don't block page rendering if article can't be loaded
      // Error logged server-side if needed, but not blocking page render
    }
  }

  // 3. SERVICES LIST PAGE: /services
  if (pathname === '/services') {
    const servicesListSchema = {
      '@context': 'https://schema.org',
      '@type': 'ItemList',
      name: 'Bali Zero Services',
      description: 'Complete visa, immigration, company setup, and business consulting services in Bali, Indonesia',
      itemListElement: Object.values(SERVICES_DATA).map((svc, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        item: {
          '@type': 'Service',
          name: svc.name,
          description: svc.description,
          url: `${baseUrl}/services/${svc.slug}`,
        },
      })),
    };
    pageSchemas.push(servicesListSchema);
  }

  // 4. CONTACT PAGE: /contact
  if (pathname === '/contact') {
    const contactPageSchema = {
      '@context': 'https://schema.org',
      '@type': 'ContactPage',
      name: 'Contact Bali Zero',
      description: 'Get in touch with Bali Zero for visa, immigration, and business consulting services in Bali, Indonesia',
      url: `${baseUrl}/contact`,
      mainEntity: {
        '@type': 'Organization',
        name: 'Bali Zero',
        url: baseUrl,
        contactPoint: [
          {
            '@type': 'ContactPoint',
            telephone: '+62-859-0436-9574',
            contactType: 'customer service',
            availableLanguage: ['English', 'Indonesian'],
            areaServed: 'ID',
          },
          {
            '@type': 'ContactPoint',
            email: 'info@balizero.com',
            contactType: 'customer service',
            availableLanguage: ['English', 'Indonesian'],
          },
        ],
      },
    };
    pageSchemas.push(contactPageSchema);
  }

  // 5. TEAM PAGE: /team
  if (pathname === '/team') {
    const aboutPageSchema = {
      '@context': 'https://schema.org',
      '@type': 'AboutPage',
      name: 'Bali Zero Team',
      description: 'Meet the expert team at Bali Zero - visa, immigration, and business consulting professionals in Bali, Indonesia',
      url: `${baseUrl}/team`,
      mainEntity: {
        '@type': 'Organization',
        name: 'Bali Zero',
        alternateName: 'Bali Zero Team',
        url: baseUrl,
        description:
          'Expert visa, immigration, company setup, and business consulting services in Bali, Indonesia. Trusted by 1000+ expats.',
        foundingDate: '2020',
        numberOfEmployees: {
          '@type': 'QuantitativeValue',
          value: '10-50',
        },
        address: {
          '@type': 'PostalAddress',
          addressLocality: 'Bali',
          addressRegion: 'Bali',
          addressCountry: 'ID',
        },
      },
    };
    pageSchemas.push(aboutPageSchema);
  }

  return (
    <html lang="en" className="dark">
      <head>
        {/* AI Discovery Links */}
        <link rel="alternate" type="text/plain" href="/llms.txt" title="LLM Context" />
        <link
          rel="alternate"
          type="application/json"
          href="/.well-known/ai-plugin.json"
          title="AI Plugin"
        />
        <link rel="alternate" type="text/yaml" href="/openapi.yaml" title="OpenAPI Spec" />

        {/* Global JSON-LD for SEO */}
        <OrganizationJsonLd />
        <LocalBusinessJsonLd />
        <WebsiteJsonLd />

        {/* Page-specific JSON-LD schemas - Injected in <head> for Schema.org Validator */}
        {pageSchemas.map((schema, index) => {
          const schemaType = schema['@type'] || 'schema';
          const uniqueId = `json-ld-${schemaType.toLowerCase()}-${index}`;
          return (
            <script
              key={uniqueId}
              id={uniqueId}
              type="application/ld+json"
              dangerouslySetInnerHTML={{
                __html: JSON.stringify(schema).replace(/</g, '\u003c'),
              }}
            />
          );
        })}
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[var(--background)] text-[var(--foreground)]`}
      >
        <QueryProvider>
          <WebVitalsMonitor />
          {children}
          <Toaster
            position="bottom-right"
            theme="dark"
            richColors
            closeButton
            toastOptions={{
              style: {
                background: 'var(--background-elevated)',
                border: '1px solid var(--border)',
                color: 'var(--foreground)',
              },
            }}
          />
        </QueryProvider>
      </body>
    </html>
  );
}
````
