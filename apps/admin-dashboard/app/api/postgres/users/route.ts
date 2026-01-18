import { NextResponse } from 'next/server';
import { Pool } from 'pg';
import { logger } from '@/lib/logger';

export const dynamic = 'force-dynamic';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const userId = searchParams.get('userId');
  const search = searchParams.get('search');

  try {
    const client = await pool.connect();
    try {
      if (userId) {
        // Fetch details for a specific user
        const factsQuery = `SELECT * FROM user_facts WHERE user_id = $1 ORDER BY created_at DESC`;
        const memoriesQuery = `SELECT * FROM memories WHERE user_id = $1 ORDER BY created_at DESC LIMIT 50`;
        const userQuery = `SELECT * FROM users WHERE id = $1`;

        const [userRes, factsRes, memoriesRes] = await Promise.all([
          client.query(userQuery, [userId]),
          client.query(factsQuery, [userId]),
          client.query(memoriesQuery, [userId]),
        ]);

        return NextResponse.json({
          user: userRes.rows[0],
          facts: factsRes.rows,
          memories: memoriesRes.rows,
        });
      } else {
        // List users
        let query = `SELECT id, email, full_name, created_at FROM users ORDER BY created_at DESC LIMIT 50`;
        let params: any[] = [];

        if (search) {
          query = `SELECT id, email, full_name, created_at FROM users WHERE email ILIKE $1 OR full_name ILIKE $1 ORDER BY created_at DESC LIMIT 50`;
          params = [`%${search}%`];
        }

        const result = await client.query(query, params);
        return NextResponse.json({ users: result.rows });
      }
    } finally {
      client.release();
    }
  } catch (error: any) {
    logger.error('User Context Error:', error);
    // Handle missing tables gracefully
    if (error.code === '42P01') {
      return NextResponse.json({ users: [], warning: 'User tables not found or schema mismatch' });
    }
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
