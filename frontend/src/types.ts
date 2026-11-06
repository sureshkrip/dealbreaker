export interface ProductListItem {
  id: number;
  title: string;
  image: string | null;
  favourite: boolean;
  search_query: string | null;
  category: string | null;
  notify_price: number | null;
  notify_percent: number | null;
  best_price: number | null;
  lowest_price: number | null;
  highest_price: number | null;
  price_change: number | null;
  price_change_percent: number | null;
  target_hit: boolean;
  store_count: number;
  store_names: string[];
  last_scraped_at: string | null;
}

export interface UrlOut {
  id: number;
  url: string;
  store_id: number;
  store_name: string;
  availability: string;
  latest_price: number | null;
  last_error: string | null;
  last_scraped_at: string | null;
}

export interface ProductOut {
  id: number;
  title: string;
  image: string | null;
  favourite: boolean;
  search_query: string | null;
  category: string | null;
  notify_price: number | null;
  notify_percent: number | null;
  best_price: number | null;
  lowest_price: number | null;
  highest_price: number | null;
  price_change: number | null;
  price_change_percent: number | null;
  target_hit: boolean;
  store_names: string[];
  last_scraped_at: string | null;
  urls: UrlOut[];
}

export interface UrlPreviewOut {
  url: string;
  title: string | null;
  price: number | null;
  image: string | null;
  availability: string;
  store_name: string;
  error: string | null;
}

export interface DealOut {
  id: string;
  title: string;
  url: string;
  price: number | null;
  original_price: number | null;
  discount_percent: number | null;
  store_name: string;
  image: string | null;
  published_at: string | null;
  coupon_code: string | null;
  summary: string | null;
  is_frontpage: boolean;
  source: string;
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
