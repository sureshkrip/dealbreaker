import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, storeColorClass, timeAgo } from "../api";
import type { ProductListItem } from "../types";

type FilterMode = "all" | "target_hit" | "drops" | "favourites";
type SortMode = "recent" | "drop" | "price_asc" | "target";

export default function Dashboard() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [filter, setFilter] = useState<FilterMode>("all");
  const [sortBy, setSortBy] = useState<SortMode>("recent");
  const [search, setSearch] = useState("");

  async function load() {
    try {
      setProducts(await api.listProducts());
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function refreshAll() {
    setRefreshing(true);
    try {
      await api.refreshAll();
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setRefreshing(false);
    }
  }

  async function toggleFavourite(e: React.MouseEvent, p: ProductListItem) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await api.updateProduct(p.id, { favourite: !p.favourite });
      setProducts((prev) =>
        prev.map((item) =>
          item.id === p.id ? { ...item, favourite: !p.favourite } : item,
        ),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  const totalCount = products.length;
  const dropsCount = products.filter(
    (p) => (p.price_change != null && p.price_change < 0) || (p.best_price != null && p.highest_price != null && p.best_price < p.highest_price),
  ).length;
  const targetHitCount = products.filter((p) => p.target_hit).length;
  const favCount = products.filter((p) => p.favourite).length;

  const filtered = products
    .filter((p) => {
      if (filter === "target_hit" && !p.target_hit) return false;
      if (
        filter === "drops" &&
        !(
          (p.price_change != null && p.price_change < 0) ||
          (p.best_price != null && p.highest_price != null && p.best_price < p.highest_price)
        )
      ) {
        return false;
      }
      if (filter === "favourites" && !p.favourite) return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        const matchTitle = p.title.toLowerCase().includes(q);
        const matchStore = (p.store_names || []).some((s) =>
          s.toLowerCase().includes(q),
        );
        const matchCat = (p.category || "").toLowerCase().includes(q);
        if (!matchTitle && !matchStore && !matchCat) return false;
      }
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "drop") {
        return (a.price_change_percent ?? 0) - (b.price_change_percent ?? 0);
      }
      if (sortBy === "price_asc") {
        return (a.best_price ?? 999999) - (b.best_price ?? 999999);
      }
      if (sortBy === "target") {
        return Number(b.target_hit) - Number(a.target_hit);
      }
      return b.id - a.id;
    });

  return (
    <>
      {/* Hero Banner */}
      <div className="hero-banner">
        <div>
          <h1>✨ Personal Price &amp; Deal Monitor</h1>
          <p>
            Track products you want to buy across stores, monitor real-time price
            drops, and catch Slickdeals alerts the moment your target price hits.
          </p>
        </div>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <button
            className="secondary"
            onClick={refreshAll}
            disabled={refreshing}
          >
            {refreshing ? "🔄 Checking Prices…" : "🔄 Refresh All Prices"}
          </button>
          <Link to="/deals">
            <button className="secondary">🔥 Live Deals</button>
          </Link>
          <Link to="/add">
            <button>+ Track New Product</button>
          </Link>
        </div>
      </div>

      {/* Colorful KPI Summary Cards */}
      <div className="kpi-grid">
        <div
          className="kpi-card indigo"
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("all")}
        >
          <div className="kpi-label">
            <span>Products Watching</span>
            <span>📦</span>
          </div>
          <div className="kpi-value">{totalCount}</div>
          <div className="kpi-sub">Active price monitors</div>
        </div>

        <div
          className="kpi-card emerald"
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("drops")}
        >
          <div className="kpi-label">
            <span>Price Drops Active</span>
            <span>📉</span>
          </div>
          <div className="kpi-value" style={{ color: "var(--good)" }}>
            {dropsCount}
          </div>
          <div className="kpi-sub">Below recorded high price</div>
        </div>

        <div
          className="kpi-card amber"
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("target_hit")}
        >
          <div className="kpi-label">
            <span>Target Prices Hit</span>
            <span>🎯</span>
          </div>
          <div className="kpi-value" style={{ color: "var(--warn)" }}>
            {targetHitCount}
          </div>
          <div className="kpi-sub">Ready to buy at your goal!</div>
        </div>

        <div
          className="kpi-card rose"
          style={{ cursor: "pointer" }}
          onClick={() => setFilter("favourites")}
        >
          <div className="kpi-label">
            <span>Favorites</span>
            <span>⭐</span>
          </div>
          <div className="kpi-value" style={{ color: "var(--pink)" }}>
            {favCount}
          </div>
          <div className="kpi-sub">Priority wishlist items</div>
        </div>
      </div>

      {/* Search, Filter Pills & Sort */}
      <div className="toolbar">
        <div className="pill-tabs">
          <button
            type="button"
            className={`pill-tab ${filter === "all" ? "active" : ""}`}
            onClick={() => setFilter("all")}
          >
            All ({totalCount})
          </button>
          <button
            type="button"
            className={`pill-tab ${filter === "target_hit" ? "active" : ""}`}
            onClick={() => setFilter("target_hit")}
          >
            🎯 Target Hit ({targetHitCount})
          </button>
          <button
            type="button"
            className={`pill-tab ${filter === "drops" ? "active" : ""}`}
            onClick={() => setFilter("drops")}
          >
            📉 Price Drops ({dropsCount})
          </button>
          <button
            type="button"
            className={`pill-tab ${filter === "favourites" ? "active" : ""}`}
            onClick={() => setFilter("favourites")}
          >
            ⭐ Favorites ({favCount})
          </button>
        </div>

        <div className="row" style={{ flex: 1, maxWidth: 460, minWidth: 260 }}>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by product, store, or category…"
          />
          <select
            style={{ width: 175, flexShrink: 0 }}
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortMode)}
          >
            <option value="recent">Sort: Newest</option>
            <option value="target">Sort: Target Hit</option>
            <option value="drop">Sort: Biggest Drop</option>
            <option value="price_asc">Sort: Lowest Price</option>
          </select>
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && (
        <div className="panel" style={{ textAlign: "center", padding: 40 }}>
          <p className="muted">Loading your tracked products…</p>
        </div>
      )}

      {!loading && products.length === 0 && (
        <div
          className="panel"
          style={{ textAlign: "center", padding: "48px 24px" }}
        >
          <div style={{ fontSize: 42, marginBottom: 10 }}>🛍️</div>
          <h2 style={{ margin: "0 0 8px" }}>Your Watchlist is Empty</h2>
          <p className="muted" style={{ maxWidth: 480, margin: "0 auto 20px" }}>
            Want to buy a new product? Enter the product name or store link and
            Dealbreaker will monitor price drops and live Slickdeals posts for you.
          </p>
          <div className="row" style={{ justifyContent: "center" }}>
            <Link to="/add">
              <button>🎯 Track Your First Product</button>
            </Link>
            <Link to="/deals">
              <button className="secondary">🔥 Explore Frontpage Deals</button>
            </Link>
          </div>
        </div>
      )}

      <div className="grid">
        {filtered.map((p) => {
          const primaryStore = p.store_names?.[0] || "Deal Watch";
          let progressPct = 0;
          if (p.notify_price != null && p.best_price != null && p.best_price > 0) {
            progressPct = Math.min(
              100,
              Math.max(12, Math.round((p.notify_price / p.best_price) * 100)),
            );
          }

          return (
            <Link
              key={p.id}
              to={`/product/${p.id}`}
              className={`card ${p.target_hit ? "target-hit-card" : ""}`}
            >
              <div className="thumb">
                {p.image ? (
                  <img src={p.image} alt="" loading="lazy" />
                ) : (
                  <div className="thumb-placeholder">
                    {p.title.slice(0, 1).toUpperCase()}
                  </div>
                )}

                <div className="card-badges-top">
                  <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                    <span className={`store-pill ${storeColorClass(primaryStore)}`}>
                      {primaryStore}
                      {p.store_count > 1 ? ` +${p.store_count - 1}` : ""}
                    </span>
                    {p.target_hit && (
                      <span className="target-hit-badge">🎯 Target Hit!</span>
                    )}
                  </div>
                  <button
                    type="button"
                    className={`fav-btn ${p.favourite ? "active" : ""}`}
                    onClick={(e) => toggleFavourite(e, p)}
                    title={p.favourite ? "Remove favorite" : "Mark favorite"}
                  >
                    {p.favourite ? "★" : "☆"}
                  </button>
                </div>
              </div>

              <div className="body">
                {p.category && (
                  <div
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      color: "var(--accent)",
                      marginBottom: 4,
                    }}
                  >
                    {p.category}
                  </div>
                )}
                <div className="title" title={p.title}>
                  {p.title}
                </div>

                <div className="price-row">
                  {p.best_price != null ? (
                    <span
                      className={`price ${
                        p.target_hit || (p.price_change != null && p.price_change < 0)
                          ? "deal"
                          : ""
                      }`}
                    >
                      ${p.best_price.toFixed(2)}
                    </span>
                  ) : (
                    <span className="price none">Watching Live Deals</span>
                  )}

                  {p.highest_price != null &&
                    p.best_price != null &&
                    p.highest_price > p.best_price && (
                      <span className="price-strike">
                        ${p.highest_price.toFixed(2)}
                      </span>
                    )}

                  {p.price_change_percent != null && p.price_change_percent !== 0 && (
                    <span
                      className={`trend-badge ${
                        p.price_change_percent < 0 ? "trend-down" : "trend-up"
                      }`}
                    >
                      {p.price_change_percent < 0 ? "↓" : "↑"}{" "}
                      {Math.abs(p.price_change_percent).toFixed(1)}%
                    </span>
                  )}
                </div>

                {/* All-Time Range */}
                {p.lowest_price != null && p.highest_price != null && (
                  <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                    Low:{" "}
                    <strong style={{ color: "var(--good)" }}>
                      ${p.lowest_price.toFixed(2)}
                    </strong>{" "}
                    · High: <strong>${p.highest_price.toFixed(2)}</strong>
                  </div>
                )}

                {/* Target Price Progress Bar */}
                {p.notify_price != null && (
                  <div className="target-box">
                    <div className="row spread">
                      <span>
                        🎯 Goal: <strong>${p.notify_price.toFixed(2)}</strong>
                      </span>
                      <span
                        style={{
                          fontWeight: 700,
                          color: p.target_hit ? "var(--good)" : "var(--text-soft)",
                        }}
                      >
                        {p.target_hit
                          ? "✅ Reached!"
                          : p.best_price != null
                            ? `$${(p.best_price - p.notify_price).toFixed(2)} away`
                            : "Monitoring"}
                      </span>
                    </div>
                    {p.best_price != null && (
                      <div className="progress-track">
                        <div
                          className={`progress-fill ${p.target_hit ? "hit" : ""}`}
                          style={{ width: `${progressPct}%` }}
                        />
                      </div>
                    )}
                  </div>
                )}

                <div className="card-footer">
                  <span>
                    {p.store_count} store{p.store_count === 1 ? "" : "s"}
                  </span>
                  <span>{timeAgo(p.last_scraped_at)}</span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </>
  );
}
