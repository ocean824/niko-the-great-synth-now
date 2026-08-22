import { Client } from "pg";

import type { Env } from "./types";

export async function withDatabase<T>(env: Env, run: (client: Client) => Promise<T>): Promise<T> {
  const client = new Client({ connectionString: env.HYPERDRIVE.connectionString });
  await client.connect();
  try {
    return await run(client);
  } finally {
    await client.end();
  }
}
