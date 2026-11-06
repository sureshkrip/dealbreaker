import type {
  DealOut,
  PricePoint,
  ProductListItem,
  ProductOut,
  Store,
  UrlOut,
  UrlPreviewOut,
} from "./types";

const TOKEN_KEY = "dealbreaker_token";

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    throw new ApiError(401, "Unauthorized — check your admin token");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  listProducts: () => request<ProductListItem[]>("/products"),
  getProduct: (id: number) => request<ProductOut>(`/products/${id}`),
  previewUrl: (url: string) =>
    request<UrlPreviewOut>("/products/preview", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  addProduct: (body: {
    url?: string | null;
    title?: string | null;
    image?: string | null;
    initial_price?: number | null;
    search_query?: string | null;
    category?: string | null;
    notify_price?: number | null;
    notify_percent?: number | null;
  }) =>
    request<ProductOut>("/products", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateProduct: (
    id: number,
    body: Partial<{
      title: string;
      image: string | null;
      favourite: boolean;
      search_query: string | null;
      category: string | null;
      notify_price: number | null;
      notify_percent: number | null;
    }>,
  ) =>
    request<ProductOut>(`/products/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteProduct: (id: number) =>
    request<void>(`/products/${id}`, { method: "DELETE" }),
  productPrices: (id: number) =>
    request<Record<string, PricePoint[]>>(`/products/${id}/prices`),
  productDeals: (id: number) =>
    request<DealOut[]>(`/products/${id}/deals`),
  addUrl: (id: number, url: string, price?: number | null) =>
    request<ProductOut>(`/products/${id}/urls`, {
      method: "POST",
      body: JSON.stringify({ url, price: price ?? null }),
    }),
  refreshUrl: (urlId: number) =>
    request<UrlOut>(`/products/urls/${urlId}/refresh`, { method: "POST" }),
  recordManualPrice: (urlId: number, price: number) =>
    request<UrlOut>(`/products/urls/${urlId}/price`, {
      method: "POST",
      body: JSON.stringify({ price }),
    }),
  deleteUrl: (urlId: number) =>
    request<void>(`/products/urls/${urlId}`, { method: "DELETE" }),
  listStores: () => request<Store[]>("/stores"),
  updateStore: (
    id: number,
    body: Partial<{ name: string; domains: string[]; scrape_strategy: object }>,
  ) =>
    request<Store>(`/stores/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  testStoreStrategy: (
    storeId: number,
    url: string,
    scrape_strategy?: object,
  ) =>
    request<UrlPreviewOut>(`/stores/${storeId}/test`, {
      method: "POST",
      body: JSON.stringify({ url, scrape_strategy }),
    }),
  listLiveDeals: (params?: { q?: string; mode?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.q) qs.set("q", params.q);
    if (params?.mode) qs.set("mode", params.mode);
    if (params?.limit) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<DealOut[]>(`/deals${suffix}`);
  },
  refreshAll: () =>
    request<{ new_prices: number }>("/refresh", { method: "POST" }),
};

export function storeColorClass(storeName: string): string {
  const s = (storeName || "").toLowerCase();
  if (s.includes("amazon") || s.includes("woot")) return "store-amazon";
  if (s.includes("best buy") || s.includes("bestbuy")) return "store-bestbuy";
  if (s.includes("walmart") || s.includes("sam's")) return "store-walmart";
  if (s.includes("target") || s.includes("costco")) return "store-target";
  if (s.includes("ebay")) return "store-ebay";
  if (s.includes("b&h") || s.includes("newegg") || s.includes("micro")) return "store-tech";
  return "store-default";
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "Never checked";
  const date = new Date(iso);
  if (isNaN(date.getTime())) return "";
  const diffSec = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (diffSec < 60) return "Just now";
  const mins = Math.floor(diffSec / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}
