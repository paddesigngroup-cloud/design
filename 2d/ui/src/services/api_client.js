const inflightRequests = new Map();
const responseCache = new Map();
const channelControllers = new Map();

function normalizeHeaders(headers) {
  const next = new Headers(headers || {});
  return next;
}

function buildCacheKey(method, url, body) {
  return `${String(method || "GET").toUpperCase()}::${url}::${body || ""}`;
}

function cloneJsonLike(value) {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

function readCached(cacheKey) {
  const entry = responseCache.get(cacheKey);
  if (!entry) return null;
  if (entry.expiresAt <= Date.now()) {
    responseCache.delete(cacheKey);
    return null;
  }
  return cloneJsonLike(entry.value);
}

function writeCached(cacheKey, value, ttlMs) {
  if (!ttlMs || ttlMs <= 0) return;
  responseCache.set(cacheKey, {
    value: cloneJsonLike(value),
    expiresAt: Date.now() + ttlMs,
  });
}

export function invalidateApiCache(pattern = "") {
  const needle = String(pattern || "").trim();
  if (!needle) {
    responseCache.clear();
    return;
  }
  for (const key of responseCache.keys()) {
    if (key.includes(needle)) {
      responseCache.delete(key);
    }
  }
}

export async function requestJson(url, options = {}) {
  const {
    method = "GET",
    headers,
    body,
    cacheTtlMs = 0,
    dedupe = true,
    abortChannel = "",
    signal,
  } = options;
  const normalizedMethod = String(method || "GET").toUpperCase();
  const bodyText = body == null || typeof body === "string" ? body || "" : JSON.stringify(body);
  const cacheKey = buildCacheKey(normalizedMethod, url, bodyText);

  if (normalizedMethod === "GET" && cacheTtlMs > 0) {
    const cached = readCached(cacheKey);
    if (cached !== null) return cached;
  }

  if (dedupe && inflightRequests.has(cacheKey)) {
    return cloneJsonLike(await inflightRequests.get(cacheKey));
  }

  if (abortChannel) {
    channelControllers.get(abortChannel)?.abort();
  }
  const controller = new AbortController();
  if (abortChannel) {
    channelControllers.set(abortChannel, controller);
  }
  if (signal) {
    signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  const requestPromise = (async () => {
    const response = await fetch(url, {
      method: normalizedMethod,
      headers: normalizeHeaders(headers),
      body: bodyText || undefined,
      signal: controller.signal,
    });
    if (!response.ok) {
      throw response;
    }
    if (response.status === 204) {
      return null;
    }
    const payload = await response.json();
    if (normalizedMethod === "GET" && cacheTtlMs > 0) {
      writeCached(cacheKey, payload, cacheTtlMs);
    }
    return payload;
  })();

  if (dedupe) {
    inflightRequests.set(cacheKey, requestPromise);
  }

  try {
    return cloneJsonLike(await requestPromise);
  } finally {
    inflightRequests.delete(cacheKey);
    if (abortChannel && channelControllers.get(abortChannel) === controller) {
      channelControllers.delete(abortChannel);
    }
  }
}

export function getJson(url, options = {}) {
  return requestJson(url, { ...options, method: "GET" });
}

export function sendJson(url, method, payload, options = {}) {
  return requestJson(url, {
    ...options,
    method,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    body: payload,
  });
}
