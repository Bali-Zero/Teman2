import { ImageResponse } from 'next/og';
import type { NextRequest } from 'next/server';

export const runtime = 'edge';

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const chapter = url.searchParams.get('chapter') ?? 'cover';
  const title = url.searchParams.get('title') ?? 'Bali Zero';

  return new ImageResponse(
    (
      <div
        style={{
          width: '1200px',
          height: '630px',
          background: '#0c0c0e',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'flex-end',
          padding: '60px',
          fontFamily: 'system-ui, sans-serif',
          position: 'relative',
        }}
      >
        {/* Gold accent bar */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '4px',
            background: 'linear-gradient(90deg, #d4845a, #c9a96e)',
          }}
        />
        {/* Chapter label */}
        <div
          style={{
            color: '#d4845a',
            fontSize: '14px',
            letterSpacing: '0.3em',
            textTransform: 'uppercase',
            marginBottom: '16px',
          }}
        >
          Bali Zero — {chapter}
        </div>
        {/* Title */}
        <div
          style={{
            color: '#ffffff',
            fontSize: '56px',
            fontWeight: '900',
            lineHeight: '1.1',
            marginBottom: '24px',
            maxWidth: '900px',
          }}
        >
          {title}
        </div>
        {/* Footer */}
        <div
          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
        >
          <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: '16px' }}>
            balizero.com/book
          </div>
          <div
            style={{
              color: '#d4845a',
              fontSize: '14px',
              letterSpacing: '0.1em',
            }}
          >
            5.000+ CLIENTI · DAL 2006
          </div>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
    }
  );
}
