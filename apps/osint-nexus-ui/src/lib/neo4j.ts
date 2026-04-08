import neo4j, { Driver } from 'neo4j-driver';

let driver: Driver | null = null;

export function getDriver(): Driver {
  if (!driver) {
    driver = neo4j.driver(
      process.env.NEO4J_URI!,
      neo4j.auth.basic(process.env.NEO4J_USER!, process.env.NEO4J_PASSWORD!)
    );
  }
  return driver;
}

/** Recursively convert Neo4j Integer objects ({low, high}) to JS numbers */
function toNative(val: unknown): unknown {
  if (val === null || val === undefined) return val;
  if (typeof val === 'object' && val !== null && 'toNumber' in val) {
    return (val as { toNumber(): number }).toNumber();
  }
  if (Array.isArray(val)) return val.map(toNative);
  if (typeof val === 'object' && val !== null) {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(val)) {
      out[k] = toNative(v);
    }
    return out;
  }
  return val;
}

export async function runQuery<T>(
  cypher: string,
  params: Record<string, unknown> = {}
): Promise<T[]> {
  const session = getDriver().session();
  try {
    const result = await session.run(cypher, params);
    return result.records.map((r) => {
      const obj: Record<string, unknown> = {};
      r.keys.forEach((key) => {
        obj[key as string] = toNative(r.get(key));
      });
      return obj as T;
    });
  } finally {
    await session.close();
  }
}
