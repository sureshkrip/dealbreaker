import type {
  PricePoint,
  ProductListItem,
  ProductOut,
  Store,
  UrlOut,
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
    throw new ApiError(401, "Unauthorized — check your token");
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
  addProduct: (body: {
    url: string;
    notify_price?: number | null;
    notify_percent?: number | null;
  }) => request<ProductOut>("/products", { method: "POST", body: JSON.stringify(body) }),
  updateProduct: (
    id: number,
    body: Partial<{
      title: string;
      favourite: boolean;
      notify_price: number | null;
      notify_percent: number | null;
    }>,
  ) => request<ProductOut>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteProduct: (id: number) => request<void>(`/products/${id}`, { method: "DELETE" }),
  productPrices: (id: number) =>
    request<Record<string, PricePoint[]>>(`/products/${id}/prices`),
  addUrl: (id: number, url: string) =>
    request<ProductOut>(`/products/${id}/urls`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  refreshUrl: (urlId: number) =>
    request<UrlOut>(`/products/urls/${urlId}/refresh`, { method: "POST" }),
  deleteUrl: (urlId: number) =>
    request<void>(`/products/urls/${urlId}`, { method: "DELETE" }),
  listStores: () => request<Store[]>("/stores"),
  updateStore: (
    id: number,
    body: Partial<{ name: string; domains: string[]; scrape_strategy: object }>,
  ) => request<Store>(`/stores/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  refreshAll: () => request<{ new_prices: number }>("/refresh", { method: "POST" }),
};
