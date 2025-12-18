
const fetch = require('node-fetch'); // Native in Node 18+, but ensuring compat

const BASE_URL = 'http://localhost:8080'; 
const AUTH_URL = `${BASE_URL}/api/auth`;
const STREAM_URL = `${BASE_URL}/api/agentic-rag/stream`;

const CONFIG = {
    email: 'test1@example.com',
    pin: '123456'
};

async function getAuthToken() {
    const res = await fetch(`${AUTH_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: CONFIG.email, pin: CONFIG.pin })
    });
    if (!res.ok) throw new Error(`Login failed: ${res.status}`);
    const data = await res.json();
    return data.data.token;
}

async function testStreamQuery(token, query, testName) {
    console.log(`\n🧪 TEST: ${testName}`);
    console.log(`   Query: "${query}"`);
    
    const res = await fetch(STREAM_URL, {
        method: 'POST',
        headers: { 
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ 
            query: query,
            session_id: `test-${Date.now()}`
        })
    });

    if (!res.ok) throw new Error(`Stream request failed: ${res.status}`);

    // Read the stream (Node.js compatible)
    let fullText = "";
    let toolsUsed = [];
    let firstTokenTime = null;
    const startTime = Date.now();

    for await (const chunk of res.body) {
        const textChunk = chunk.toString(); // Convert buffer to string
        const lines = textChunk.split('\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const jsonStr = line.slice(6);
                if (jsonStr === '[DONE]') continue;
                
                try {
                    const data = JSON.parse(jsonStr);
                    
                    if (data.type === 'token') {
                        if (!firstTokenTime) firstTokenTime = Date.now();
                        process.stdout.write(data.data); // Print streaming text
                        fullText += data.data;
                    } 
                    else if (data.type === 'tool_start') {
                        console.log(`\n   🛠️  TOOL START: ${data.data.name} (${JSON.stringify(data.data.args)})`);
                        toolsUsed.push(data.data.name);
                    }
                    else if (data.type === 'tool_end') {
                        console.log(`   ✅ TOOL END. Result length: ${data.data.result.length}`);
                    }
                    else if (data.type === 'error') {
                        console.log(`\n   ❌ STREAM ERROR: ${data.data.message}`);
                    }
                } catch (e) {
                    // Ignore parse errors for partial chunks
                }
            }
        }
    }
    
    const duration = Date.now() - startTime;
    const ttfb = firstTokenTime ? firstTokenTime - startTime : "N/A";
    
    console.log(`\n\n   ⏱️  Stats: Duration=${duration}ms, TTFB=${ttfb}ms`);
    console.log(`   🔧 Tools Triggered: ${toolsUsed.join(', ') || 'None'}`);
    
    return { fullText, toolsUsed };
}

(async () => {
    try {
        console.log("🚀 STARTING ADVANCED BACKEND TESTS");
        const token = await getAuthToken();
        console.log("🔑 Auth Token Acquired");

        // TEST 1: CALCULATOR
        await testStreamQuery(token, "Calculate the PPN (11%) of 500,000,000 IDR.", "Tool: Calculator");

        // TEST 2: PRICING
        await testStreamQuery(token, "How much does the Investor KITAS (2 years) cost exactly in USD?", "Tool: Pricing");

        // TEST 3: RAG (Streaming verification)
        await testStreamQuery(token, "What are the requirements for a PT PMA?", "Stream: RAG Flow");

        console.log("\n✅ ALL API TESTS COMPLETED");
    } catch (e) {
        console.error("\n💥 CRITICAL FAILURE:", e);
    }
})();
