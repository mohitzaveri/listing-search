import type { Filters, SearchResponse } from './types';

/** An error the API explained to us. `field` is the input it blames, if any. */
export class ApiError extends Error {
  field?: string;

  constructor(message: string, field?: string) {
    super(message);
    this.field = field;
  }
}

// Listings don't change while the page is open, so each distinct query is fetched
// once. Storing the promise (not the result) also merges duplicate in-flight calls,
// e.g. a prefetch and a click on "Next" for the same page.
const MAX_CACHED = 50;
const cache = new Map<string, Promise<SearchResponse>>();

export function searchListings(filters: Filters, page: number): Promise<SearchResponse> {
  const query = toQuery(filters, page);
  let request = cache.get(query);
  if (!request) {
    request = fetchSearch(query);
    request.catch(() => cache.delete(query)); // never cache a failure
    cache.set(query, request);
    if (cache.size > MAX_CACHED) cache.delete(cache.keys().next().value!); // drop the oldest
  }
  return request;
}

/** Warm the cache for a page the user is likely to open next. */
export function prefetchListings(filters: Filters, page: number): void {
  searchListings(filters, page).catch(() => {});
}

function toQuery(filters: Filters, page: number): string {
  const query = new URLSearchParams({ page: String(page) });
  for (const [key, value] of Object.entries(filters)) {
    if (value.trim() !== '') query.set(key, value.trim()); // blank = "any"
  }
  return query.toString();
}

async function fetchSearch(query: string): Promise<SearchResponse> {
  let response: Response;
  try {
    response = await fetch(`/api/listings/search?${query}`);
  } catch {
    throw new ApiError('Could not reach the server. Is the backend running?');
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(
      body?.error?.message ?? `Search failed (HTTP ${response.status}). Is the backend running?`,
      body?.error?.field,
    );
  }
  return body as SearchResponse;
}
