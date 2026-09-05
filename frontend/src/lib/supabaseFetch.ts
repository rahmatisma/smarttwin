/** Retry transient PostgREST clock skew using the same credentials. */
export function createSupabaseFetch(
  supabaseUrl: string,
  fetcher: typeof fetch = (...args) => fetch(...args),
  wait: (ms: number) => Promise<void> = (ms) =>
    new Promise((resolve) => setTimeout(resolve, ms)),
): typeof fetch {
  const restUrl = `${supabaseUrl.replace(/\/$/, "")}/rest/v1/`;

  return async (input, init) => {
    const url = input instanceof Request ? input.url : String(input);
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
    const signal = init?.signal ?? (input instanceof Request ? input.signal : undefined);
    let response = await fetcher(input, init);

    // Never replay writes or Auth requests, or retry unrelated auth failures.
    if (method !== "GET" || !url.startsWith(restUrl)) return response;

    for (const delay of [300, 600]) {
      if (response.status !== 401 || signal?.aborted) break;
      const body = await response.clone().json().catch(() => null);
      if (body?.code !== "PGRST303" || body?.message !== "JWT issued at future") break;
      await wait(delay);
      if (signal?.aborted) break;
      response = await fetcher(input, init);
    }

    return response;
  };
}
