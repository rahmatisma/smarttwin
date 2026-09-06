export async function fetchOptional<T>(label: string, request: Promise<T>): Promise<T | null> {
  try {
    return await request;
  } catch (error) {
    console.warn(`${label} tidak tersedia:`, error);
    return null;
  }
}

// A render deadline should not discard a successful response that arrives later.
export async function fetchOptionalWithin<T>(
  label: string,
  request: Promise<T>,
  timeoutMs = 1500,
  onLateResult?: (value: T) => void,
): Promise<T | null> {
  let timedOut = false;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const result = fetchOptional(label, request).then((value) => {
    if (timedOut && value !== null) onLateResult?.(value);
    return value;
  });
  const timeout = new Promise<null>((resolve) => {
    timeoutId = setTimeout(() => { timedOut = true; resolve(null); }, timeoutMs);
  });
  try {
    return await Promise.race([result, timeout]);
  } finally {
    clearTimeout(timeoutId);
  }
}
