import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Bali Zero',
  description: '',
  robots: { index: false, follow: false },
};

export default function ExclusivePage() {
  return (
    <div
      style={{
        minHeight: '100dvh',
        background: '#0a0a0a',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
      }}
    >
      {/* Logo */}
      <div
        style={{
          marginBottom: '32px',
          fontSize: '11px',
          fontWeight: 700,
          letterSpacing: '0.3em',
          textTransform: 'uppercase',
          color: '#C9A84C',
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        Bali Zero
      </div>

      {/* Video container — 9:16 portrait, max 420px wide */}
      <div
        style={{
          width: '100%',
          maxWidth: '420px',
          aspectRatio: '9/16',
          borderRadius: '12px',
          overflow: 'hidden',
          background: '#111',
          boxShadow: '0 32px 80px rgba(0,0,0,0.7)',
        }}
      >
        <video
          src="/exclusive/video.mp4"
          controls
          playsInline
          autoPlay
          muted
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
      </div>

      {/* Subtle footer */}
      <div
        style={{
          marginTop: '28px',
          fontSize: '11px',
          color: 'rgba(255,255,255,0.2)',
          fontFamily: 'system-ui, sans-serif',
          letterSpacing: '0.05em',
        }}
      >
        zantara@balizero.com
      </div>
    </div>
  );
}
