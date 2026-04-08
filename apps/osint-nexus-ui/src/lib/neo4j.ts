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
        const val = r.get(key);
        obj[key as string] = typeof val === 'object' && val !== null && 'toNumber' in val
          ? (val as { toNumber(): number }).toNumber()
          : val;
      });
      return obj as T;
    });
  } finally {
    await session.close();
  }
}
