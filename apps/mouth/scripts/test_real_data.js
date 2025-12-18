
const axios = require('axios'); 

const BASE_URL = 'http://localhost:8080'; 
const AUTH_URL = `${BASE_URL}/api/auth`;
const RAG_URL = `${BASE_URL}/api/agentic-rag`;

const CONFIG = {
    email: 'test1@example.com',
    pin: '123456'
};

async function runTest() {
    console.log('--- ZANTARA REAL DATA TEST ---');
    try {
        const loginRes = await fetch(`${AUTH_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: CONFIG.email, pin: CONFIG.pin })
        });
        const loginData = await loginRes.json();
        const token = loginData.data?.token;
        if (!token) throw new Error('Token missing');

        const query = "What are the specific tax obligations (PPN & PPh) for a PT PMA in Bali engaging in Crypto Trading?";
        console.log(`Sending Query: "${query}"`);
        
        const res = await fetch(`${RAG_URL}/query`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ query: query })
        });
        
        const data = await res.json();
        console.log("---------------------------------------------------");
        console.log("ANSWER:", data.answer);
        console.log("SOURCES:", data.sources?.length || 0);
        console.log("---------------------------------------------------");

    } catch (error) {
        console.error('FAIL:', error);
    }
}

runTest();
