import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, storeColorClass } from "../api";
import type { DealOut } from "../types";

export default function LiveDeals() {
  const nav = useNavigate();
  const [deals, setDeals] = useState<DealOut[]>([]);
  const [mode, setMode] = useState<"frontpage" | "popular">("frontpage");
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [trackingId, setTrackingId] = useState<string | null>(null);

  async function loadDeals(searchQuery: string, feedMode: "frontpage" | "popular") {
    setLoading(true);
    setError("");
    try {
      const list = await api.listLiveDeals({
        q: searchQuery || undefined,
        mode: feedMode,
        limit: 24,
      });
      setDeals(list);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDeals(activeQuery, mode);
  }, [activeQuery, mode]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setActiveQuery(query.trim());
  }

  async function trackDeal(deal: DealOut) {
    setTrackingId(deal.id);
    try {
      const targetPrice =
        deal.price != null ? Math.round(deal.price * 0.95 * 100) / 100 : null;
      const product = await api.addProduct({
        url: deal.url,
        title: deal.title,
        image: deal.image,
        initial_price: deal.price,
        search_query: deal.title.split(" ").slice(0, 5).join(" "),
        notify_price: targetPrice,
      });
      nav(`/product/${product.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setTrackingId(null);
    }
  }

  return (
    <>
      <div className="hero-banner">
        <div>
          <h1>🔥 Live Deal Radar (Slickdeals Feed)</h1>
          <p>
            Discover real-time Frontpage &amp; community deals across Amazon, Best Buy,
            Walmart, Costco &amp; more — or search any product you want to buy and track it
            in 1 click.
          </p>
        </div>
        <div className="pill-tabs">
          <button
            type="button"
            className={`pill-tab ${!activeQuery && mode === "frontpage" ? "active" : ""}`}
            onClick={() => {
              setQuery("");
              setActiveQuery("");
              setMode("frontpage");
            }}
          >
            🔥 Frontpage Deals
          </button>
          <button
            type="button"
            className={`pill-tab ${!activeQuery && mode === "popular" ? "active" : ""}`}
            onClick={() => {
              setQuery("");
              setActiveQuery("");
              setMode("popular");
            }}
          >
            ⚡ Popular Rising Deals
          </button>
        </div>
      </div>

      <form className="panel row" onSubmit={handleSearch} style={{ marginTop: 18 }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search Slickdeals for a product you want to buy (e.g. OLED TV, AirPods Pro, Laptop, SSD)…"
        />
        <button type="submit">🔍 Find Deals</button>
        {activeQuery && (
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setQuery("");
              setActiveQuery("");
            }}
          >
            Clear
          </button>
        )}
      </form>

      {error && <div className="error">{error}</div>}
      {loading && (
        <div className="panel" style={{ textAlign: "center", padding: 40 }}>
          <div style={{ fontSize: 18, fontWeight: 700 }}>
            Scanning live deal feeds…
          </div>
          <p className="muted">Checking Slickdeals community &amp; staff posts</p>
        </div>
      )}

      {!loading && deals.length === 0 && (
        <div className="panel" style={{ textAlign: "center", padding: 36 }}>
          <div style={{ fontSize: 17, fontWeight: 700 }}>No matching live deals found</div>
          <p className="muted">
            Try a broader keyword or add the product directly to your Watchlist so
            Dealbreaker monitors it automatically.
          </p>
        </div>
      )}

      {!loading && deals.length > 0 && (
        <div className="grid">
          {deals.map((d) => (
            <div key={d.id} className="card">
              <div className="thumb">
                {d.image ? (
                  <img src={d.image} alt="" loading="lazy" />
                ) : (
                  <div className="thumb-placeholder">🏷️</div>
                )}
                <div className="card-badges-top">
                  <span className={`store-pill ${storeColorClass(d.store_name)}`}>
                    {d.store_name}
                  </span>
                  {d.is_frontpage && (
                    <span className="frontpage-badge">🔥 Frontpage</span>
                  )}
                </div>
              </div>
              <div className="body">
                <div className="title" title={d.title}>
                  {d.title}
                </div>

                <div className="price-row">
                  {d.price != null ? (
                    <span className="price deal">${d.price.toFixed(2)}</span>
                  ) : (
                    <span className="price none">See Deal Promo</span>
                  )}
                  {d.original_price != null && (
                    <span className="price-strike">
                      ${d.original_price.toFixed(2)}
                    </span>
                  )}
                  {d.discount_percent != null && d.discount_percent > 0 && (
                    <span className="trend-badge trend-down">
                      ↓ {d.discount_percent}% OFF
                    </span>
                  )}
                </div>

                {d.coupon_code && (
                  <div style={{ marginTop: 8 }}>
                    <span className="coupon-chip">🎟️ Code: {d.coupon_code}</span>
                  </div>
                )}

                {d.summary && (
                  <p
                    className="muted"
                    style={{
                      margin: "10px 0 12px",
                      fontSize: 12,
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {d.summary}
                  </p>
                )}

                <div className="card-footer">
                  <a
                    href={d.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontWeight: 600 }}
                  >
                    View Post ↗
                  </a>
                  <button
                    type="button"
                    className="sm success"
                    disabled={trackingId === d.id}
                    onClick={() => trackDeal(d)}
                  >
                    {trackingId === d.id ? "Adding…" : "+ Track Price"}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
