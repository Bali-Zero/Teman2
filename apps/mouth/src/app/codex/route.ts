import { CODEX_HTML } from './_codex-content';

// PIN-gated reading room for the Codex Akasha (private family page).
// Server-side gate: the codex HTML never reaches the client before the PIN.
// Gated responses must never be statically optimized or cached.
export const dynamic = 'force-dynamic';
const PIN = process.env.CODEX_PIN ?? '666';
const COOKIE_NAME = 'codex_sig';
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

const BASE_HEADERS: Record<string, string> = {
  'Content-Type': 'text/html; charset=utf-8',
  'X-Robots-Tag': 'noindex, nofollow',
  'Cache-Control': 'no-store',
};

async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function expectedSig(): Promise<string> {
  return sha256Hex(`akasha-${PIN}`);
}

function getCookie(req: Request, name: string): string | null {
  const header = req.headers.get('cookie') ?? '';
  for (const part of header.split(';')) {
    const [key, ...rest] = part.trim().split('=');
    if (key === name) return rest.join('=');
  }
  return null;
}

function doorHtml(error = false): string {
  return `<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Codex Akasha</title>
<style>
  body{margin:0;min-height:100dvh;display:flex;align-items:center;justify-content:center;
    background:radial-gradient(900px 600px at 50% 20%, #2a1e10, #150e07 70%, #0c0703);
    font-family:'Iowan Old Style','Palatino Linotype',Palatino,'Book Antiqua',Georgia,serif;color:#e0bb56}
  .door{position:relative;text-align:center;padding:70px 44px;max-width:420px;width:calc(100% - 48px);
    background:linear-gradient(160deg,#3d2716,#2a180b 45%,#1d0f06);border-radius:6px;
    box-shadow:0 22px 44px rgba(0,0,0,.6), inset 0 0 90px rgba(0,0,0,.55)}
  .door::before{content:"";position:absolute;inset:12px;border:2px solid #a37f35;opacity:.85;pointer-events:none}
  .door::after{content:"";position:absolute;inset:22px;border:1px solid #7d5f24;opacity:.8;pointer-events:none}
  h1{font-family:'Luminari','Herculanum',Copperplate,'Palatino Linotype',serif;font-weight:400;font-size:28px;
    letter-spacing:.14em;margin:18px 0 6px;
    text-shadow:0 1px 0 rgba(255,240,190,.28),0 -1px 1px rgba(0,0,0,.7)}
  p.q{font-size:12px;letter-spacing:.22em;text-transform:uppercase;color:#b3924d;margin:0 0 30px}
  input{width:140px;text-align:center;font-size:30px;letter-spacing:.35em;padding:10px 0 10px .35em;
    background:#150e07;border:1px solid #7d5f24;border-radius:4px;color:#f0d98a;font-family:inherit;outline:none}
  input:focus{border-color:#c99b34;box-shadow:0 0 0 2px rgba(201,155,52,.25)}
  button{display:block;margin:22px auto 0;background:linear-gradient(180deg,#f0d98a,#c99b34 55%,#8a651c);
    border:none;color:#241a0e;font-family:inherit;font-weight:700;font-size:13px;letter-spacing:.18em;
    text-transform:uppercase;padding:10px 26px;border-radius:4px;cursor:pointer}
  button:focus-visible,input:focus-visible{outline:2px solid #f0d98a;outline-offset:2px}
  .err{color:#c0604f;font-style:italic;font-size:14px;margin:16px 0 0}
  .foot{margin-top:30px;font-size:11px;letter-spacing:.3em;color:#8a6c38;text-transform:uppercase}
</style>
</head>
<body>
<form class="door" method="post" action="/codex">
  <svg width="72" height="72" viewBox="0 0 110 110" aria-hidden="true" style="display:block;margin:0 auto;">
    <circle cx="55" cy="55" r="33" fill="none" stroke="#c99b34" stroke-width="7"/>
    <g transform="translate(78,31) rotate(42)">
      <ellipse rx="9.5" ry="6" fill="#c99b34" stroke="#8a651c" stroke-width="1.6"/>
      <circle cx="2.5" cy="-1.5" r="1.4" fill="#2c2013"/>
    </g>
    <path d="M55 51 l4 6 -4 6 -4 -6 z" fill="#e0bb56"/>
  </svg>
  <h1>CODEX&nbsp;AKASHA</h1>
  <p class="q">Quis es? Da mihi signum.</p>
  <input name="pin" inputmode="numeric" autocomplete="one-time-code" maxlength="3" pattern="[0-9]{3}" aria-label="signum" autofocus>
  ${error ? '<p class="err">Signum falsum est.</p>' : ''}
  <button type="submit">Aperi</button>
  <p class="foot">liber vivit &middot; mmxxvi</p>
</form>
</body>
</html>`;
}

export async function GET(req: Request): Promise<Response> {
  const sig = getCookie(req, COOKIE_NAME);
  if (sig && sig === (await expectedSig())) {
    return new Response(CODEX_HTML, { headers: BASE_HEADERS });
  }
  return new Response(doorHtml(), { headers: BASE_HEADERS });
}

export async function POST(req: Request): Promise<Response> {
  const form = await req.formData().catch(() => null);
  const pin = form?.get('pin');
  if (typeof pin === 'string' && pin.trim() === PIN) {
    const sig = await expectedSig();
    return new Response(null, {
      status: 303,
      headers: {
        Location: '/codex',
        'Set-Cookie': `${COOKIE_NAME}=${sig}; Path=/codex; Max-Age=${COOKIE_MAX_AGE}; HttpOnly; Secure; SameSite=Lax`,
        'X-Robots-Tag': 'noindex, nofollow',
        'Cache-Control': 'no-store',
      },
    });
  }
  return new Response(doorHtml(true), { status: 401, headers: BASE_HEADERS });
}
