export interface ProductListItem {
  id: number;
  title: string;
  image: string | null;
  favourite: boolean;
  best_price: number | null;
  store_count: number;
}

export interface UrlOut {
  id: number;
  url: string;
  store_id: number;
  store_name: string;
  availability: string;
  latest_price: number | null;
  last_scraped_at: string | null;
}

export interface ProductOut {
  id: number;
  title: string;
  image: string | null;
  favourite: boolean;
  notify_price: number | null;
  notify_percent: number | null;
  best_price: number | null;
  urls: UrlOut[];
}

export interface PricePoint {
  price: number;
  created_at: string;
}

export interface Store {
  id: number;
  name: string;
  slug: string;
  domains: string[];
  scrape_strategy: Record<string, { type: string; value: string }>;
}
