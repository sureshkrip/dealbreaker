import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, storeColorClass } from "../api";
import type { DealOut, UrlPreviewOut } from "../types";

const DISCOUNT_PRESETS = [5, 10, 15, 20, 30];
const CATEGORIES = ["Electronics", "Computing", "Audio & TV", "Home & Kitchen", "Gaming", "Apparel", "Other"];

export default function AddProduct() {
  const nav = useNavigate();
  const [entryMode, setEntryMode] = useState<"name" | "url">("name");

  // Shared fields
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [category, setCategory] = useState("Electronics");
  const [image, setImage] = useState("");
  const [initialPrice, setInitialPrice] = useState("");
  const [notifyPrice, setNotifyPrice] = useState("");
  const [notifyPercent, setNotifyPercent] = useState("");

  // URL Preview state
  const [preview, setPreview] = useState<UrlPreviewOut | null>(null);
  const [previewing, setPreviewing] = useState(false);

  // Live Deal search state
  const [dealMatches, setDealMatches] = useState<DealOut[]>([]);
  const [searchingDeals, setSearchingDeals] = useState(false);
  const [hasSearchedDeals, setHasSearchedDeals] = useState(false);

  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handlePreviewUrl() {
    if (!url.trim()) return;
    setPreviewing(true);
    setError("");
    try {
      const res = await api.previewUrl(url.trim());
      setPreview(res);
      if (res.title && !title) setTitle(res.title);
      if (res.image && !image) setImage(res.image);
      if (res.price != null) {
        setInitialPrice(String(res.price));
        if (!notifyPrice) {
          setNotifyPrice((res.price * 0.9).toFixed(2));
          setNotifyPercent("10");
        }
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setPreviewing(false);
    }
  }

  async function handleSearchDeals() {
    const q = (title || searchQuery).trim();
    if (!q) return;
    setSearchingDeals(true);
    setHasSearchedDeals(true);
    setError("");
    try {
      const results = await api.listLiveDeals({ q, limit: 8 });
      setDealMatches(results);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setSearchingDeals(false);
    }
  }

  function applyDiscountPreset(pct: number) {
    setNotifyPercent(String(pct));
    const base = Number(initialPrice);
    if (base > 0) {
      const target = Math.round(base * (1 - pct / 100) * 100) / 100;
      setNotifyPrice(target.toFixed(2));
    }
  }

  function selectDealMatch(d: DealOut) {
    if (d.image) setImage(d.image);
    if (d.price != null) {
      setInitialPrice(String(d.price));
      setNotifyPrice((d.price * 0.92).toFixed(2));
      setNotifyPercent("8");
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const product = await api.addProduct({
        url: entryMode === "url" ? url.trim() || null : null,
        title: title.trim() || null,
        search_query: (searchQuery.trim() || title.trim()) || null,
        category: category || null,
        image: image.trim() || null,
        initial_price: initialPrice ? Number(initialPrice) : null,
        notify_price: notifyPrice ? Number(notifyPrice) : null,
        notify_percent: notifyPercent ? Number(notifyPercent) : null,
      });
      nav(`/product/${product.id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="hero-banner">
        <div>
          <h1>🎯 Track a Product Across All Stores</h1>
          <p>
            Just enter the product name — <strong>no store or URL required!</strong>{" "}
            Dealbreaker automatically finds and monitors prices across Amazon, Best Buy,
            Walmart, Costco, Target, eBay &amp; more.
          </p>
        </div>
        <div className="pill-tabs">
          <button
            type="button"
            className={`pill-tab ${entryMode === "name" ? "active" : ""}`}
            onClick={() => setEntryMode("name")}
          >
            🔍 By Product Name (All Stores)
          </button>
          <button
            type="button"
            className={`pill-tab ${entryMode === "url" ? "active" : ""}`}
            onClick={() => setEntryMode("url")}
          >
            🔗 Single Store URL (Optional)
          </button>
        </div>
      </div>

      <form className="panel" onSubmit={submit}>
        {entryMode === "name" ? (
          <div>
            <label>What product do you want to buy?</label>
            <div className="row">
              <input
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  setSearchQuery(e.target.value);
                }}
                placeholder="e.g. Apple AirPods Pro, Sony WH-1000XM5, MacBook Air M3, LG C4 OLED…"
                required
              />
              <button
                type="button"
                className="secondary"
                disabled={!title.trim() || searchingDeals}
                onClick={handleSearchDeals}
                style={{ flexShrink: 0 }}
              >
                {searchingDeals ? "Scanning Stores…" : "🔥 Preview Current Store Prices"}
              </button>
            </div>
            <p className="muted" style={{ marginTop: 6 }}>
              ✨ <strong>Monitors all stores automatically:</strong> We'll scan Amazon,
              Best Buy, Walmart, Costco, Target, eBay &amp; Slickdeals for "{title || "your product"}"
              and track the lowest price across every retailer.
            </p>
          </div>
        ) : (
          <div>
            <label>Product Store URL</label>
            <div className="row">
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.amazon.com/... or https://www.bestbuy.com/..."
                required={!title}
              />
              <button
                type="button"
                className="secondary"
                disabled={!url.trim() || previewing}
                onClick={handlePreviewUrl}
                style={{ flexShrink: 0 }}
              >
                {previewing ? "Scraping…" : "✨ Fetch Preview"}
              </button>
            </div>
          </div>
        )}

        {/* Live URL Preview Box */}
        {preview && (
          <div
            className="panel"
            style={{
              background: "var(--panel-2)",
              marginTop: 16,
              padding: 16,
            }}
          >
            <div className="row spread">
              <div className="row" style={{ gap: 14 }}>
                {preview.image ? (
                  <img
                    src={preview.image}
                    alt=""
                    style={{
                      width: 64,
                      height: 64,
                      objectFit: "contain",
                      background: "#fff",
                      borderRadius: 10,
                      padding: 4,
                    }}
                  />
                ) : (
                  <div className="thumb-placeholder" style={{ width: 54, height: 54, fontSize: 22 }}>
                    📦
                  </div>
                )}
                <div>
                  <div className="row" style={{ gap: 8 }}>
                    <span className={`store-pill ${storeColorClass(preview.store_name)}`}>
                      {preview.store_name}
                    </span>
                    <span className={`badge ${preview.availability}`}>
                      {preview.availability.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div style={{ fontWeight: 700, marginTop: 6 }}>
                    {preview.title || "Product title not auto-detected — enter below"}
                  </div>
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div className="muted">Detected Price</div>
                <div className="price deal">
                  {preview.price != null ? `$${preview.price.toFixed(2)}` : "Enter below"}
                </div>
              </div>
            </div>
            {preview.error && <div className="warn-banner">{preview.error}</div>}
          </div>
        )}

        {/* Live Slickdeals Matches when searching by name */}
        {entryMode === "name" && hasSearchedDeals && (
          <div
            className="panel"
            style={{ background: "var(--panel-2)", marginTop: 16, padding: 16 }}
          >
            <div className="row spread" style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 700 }}>
                🔥 Live Slickdeals Matches ({dealMatches.length})
              </div>
              <span className="muted">
                Click any deal to pre-fill its price &amp; link, or keep your own settings
              </span>
            </div>
            {dealMatches.length === 0 ? (
              <div className="muted">
                No active Slickdeals posts right now for "{title}". Save this product below
                and Dealbreaker will keep watching for new deals!
              </div>
            ) : (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))",
                  gap: 12,
                }}
              >
                {dealMatches.map((d) => (
                  <div
                    key={d.id}
                    className="card"
                    style={{
                      padding: 12,
                      cursor: "pointer",
                      borderColor: url === d.url ? "var(--good)" : undefined,
                    }}
                    onClick={() => selectDealMatch(d)}
                  >
                    <div className="row spread">
                      <span className={`store-pill ${storeColorClass(d.store_name)}`}>
                        {d.store_name}
                      </span>
                      {d.price != null && (
                        <span style={{ fontWeight: 800, color: "var(--good)" }}>
                          ${d.price.toFixed(2)}
                        </span>
                      )}
                    </div>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        marginTop: 8,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {d.title}
                    </div>
                    <div className="muted" style={{ marginTop: 6, fontSize: 11.5 }}>
                      {url === d.url ? "✅ Selected for tracking" : "Click to use this deal"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Product Details & Overrides */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 16,
            marginTop: 8,
          }}
        >
          {entryMode === "url" && (
            <div>
              <label>Product Name (auto-filled or custom)</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Sony WH-1000XM5"
              />
            </div>
          )}
          <div>
            <label>Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>Current / Regular Price ($) (optional)</label>
            <input
              type="number"
              step="0.01"
              value={initialPrice}
              onChange={(e) => setInitialPrice(e.target.value)}
              placeholder="e.g. 299.99"
            />
          </div>
        </div>

        {/* Target Price & Alert Section */}
        <div
          className="panel"
          style={{
            background: "var(--panel-2)",
            marginTop: 20,
            padding: 18,
          }}
        >
          <div className="row spread" style={{ flexWrap: "wrap" }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>
                🎯 Set Your Target Buy Price &amp; Deal Alert
              </div>
              <div className="muted">
                Get alerted as soon as any store or deal drops to your goal
              </div>
            </div>
            <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
              <span className="muted" style={{ marginRight: 4 }}>
                Quick discount:
              </span>
              {DISCOUNT_PRESETS.map((pct) => (
                <button
                  key={pct}
                  type="button"
                  className={`discount-chip ${notifyPercent === String(pct) ? "active" : ""}`}
                  onClick={() => applyDiscountPreset(pct)}
                >
                  -{pct}% Off
                </button>
              ))}
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 16,
              marginTop: 8,
            }}
          >
            <div>
              <label>Target Buy Price ($)</label>
              <input
                type="number"
                step="0.01"
                value={notifyPrice}
                onChange={(e) => setNotifyPrice(e.target.value)}
                placeholder="e.g. 199.99"
              />
            </div>
            <div>
              <label>Alert on % Drop from High</label>
              <input
                type="number"
                step="1"
                value={notifyPercent}
                onChange={(e) => setNotifyPercent(e.target.value)}
                placeholder="e.g. 15"
              />
            </div>
            <div>
              <label>Image URL (optional override)</label>
              <input
                value={image}
                onChange={(e) => setImage(e.target.value)}
                placeholder="https://... (auto-detected from URL)"
              />
            </div>
          </div>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="row" style={{ marginTop: 20, gap: 12 }}>
          <button type="submit" disabled={busy || (!url.trim() && !title.trim())}>
            {busy
              ? "Scanning Stores & Starting Monitor…"
              : entryMode === "name"
                ? "🚀 Monitor Across All Stores"
                : "🚀 Start Monitoring Price"}
          </button>
          <button type="button" className="secondary" onClick={() => nav("/")}>
            Cancel
          </button>
        </div>
      </form>
    </>
  );
}
