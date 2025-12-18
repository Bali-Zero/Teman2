
import fetch from 'node-fetch'; // or built-in if Node 18+

const API_URL = 'https://nuzantara-rag.fly.dev';
const EMAIL = 'zero@balizero.com';
const PIN = '010719';

async function main() {
  console.log('1. Authenticating...');
  const loginRes = await fetch(`${API_URL}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: EMAIL, pin: PIN })
  });
  
  if (!loginRes.ok) {
    console.error('Login failed:', await loginRes.text());
    process.exit(1);
  }
  
  const loginData = await loginRes.json();
  const token = loginData.data?.token;
  const userId = loginData.data?.user?.id;
  
  if (!token) {
    console.error('No token received');
    process.exit(1);
  }
  console.log('2. Authenticated. Token received.');

  console.log('3. Sending Surf Camp Query (Stream)...');
  const query = "Voglio aprire una scuola di surf a Canggu. 1. Posso usare un Virtual Office? 2. Che visto serve ai miei 2 istruttori australiani? 3. Capitale minimo versato? Usa KBLI corretti.";
  
  // Note: Backend might expect 'session_id' or 'conversation_history'.
  // Using generic ID for test.
  const payload = {
    query: query,
    user_id: userId || 'test_script',
    enable_vision: false
  };

  const streamRes = await fetch(`${API_URL}/api/agentic-rag/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  if (!streamRes.ok) {
        console.error('Stream Request Failed:', streamRes.status, await streamRes.text());
        process.exit(1);
  }

  // Handle SSE Stream
  console.log('4. Stream Connected. Reading Logic...');
  console.log('==========================================');

  const reader = streamRes.body; // Node-fetch body is a stream
  
  // Simple buffer handling for SSE
  for await (const chunk of reader) {
    const text = chunk.toString();
    const lines = text.split('\n');
    for (const line of lines) {
        if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6);
            try {
                const data = JSON.parse(jsonStr);
                
                // PRINT THE "MOVES"
                if (data.type === 'status') {
                    console.log(`[THINKING] ${data.data}`);
                } else if (data.type === 'token') {
                     process.stdout.write(data.content || data.data || '');
                } else if (data.type === 'sources') {
                    console.log('\n\n[SOURCES FOUND]:');
                    data.data.forEach(s => console.log(`- ${s.title} (${s.source || 'db'})`));
                } else if (data.type === 'error') {
                    console.error('\n[ERROR]', data.data);
                }
            } catch (e) {
                // Ignore parsing errors for partial chunks (simple script)
            }
        }
    }
  }
  console.log('\n==========================================');
  console.log('Done.');
}

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

// Check if node-fetch is needed (Node < 18)
// We will assume modern node environment or use global fetch if available
if (!globalThis.fetch) {
    console.error("This script requires Node 18+ or node-fetch");
}

main().catch(console.error);
