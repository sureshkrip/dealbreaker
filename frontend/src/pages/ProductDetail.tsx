import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError, storeColorClass, timeAgo } from "../api";
import type { DealOut, PricePoint, ProductOut } from "../types";

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#06b6d4"];

export default function ProductDetail() {
  const { id } = useParams();
  const pid = Number(id);
  const nav = useNavigate();

  const [product, setProduct] = useState<ProductOut | null>(null);
  const [history, setHistory] = useState<Record<string, PricePoint[]>>({});
  const [liveDeals, setLiveDeals] = useState<DealOut[]>([]);
  const [loadingDeals, setLoadingDeals] = useState(false);

  const [error, setError] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [newUrlPrice, setNewUrlPrice] = useState("");
  const [busy, setBusy] = useState(false);

  // Inline target & title editing
  const [editingTarget, setEditingTarget] = useState(false);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftQuery, setDraftQuery] = useState("");
  const [draftNotifyPrice, setDraftNotifyPrice] = useState("");
  const [draftNotifyPercent, setDraftNotifyPercent] = useState("");

  // Manual price entry per URL row
  const [manualUrlId, setManualUrlId] = useState<number | null>(null);
  const [manualPriceVal, setManualPriceVal] = useState("");

  async function load() {
    try {
      const [p, h] = await Promise.all([
        api.getProduct(pid),
        api.productPrices(pid),
      ]);
      setProduct(p);
      setHistory(h);
      setDraftTitle(p.title);
      setDraftQuery(p.search_query || p.title);
      setDraftNotifyPrice(p.notify_price != null ? String(p.notify_price) : "");
      setDraftNotifyPercent(
        p.notify_percent != null ? String(p.notify_percent) : "",
      );
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function loadLiveDeals() {
    setLoadingDeals(true);
    try {
      setLiveDeals(await api.productDeals(pid));
    } catch {
      /* ignore feed error */
    } finally {
      setLoadingDeals(false);
    }
  }

  useEffect(() => {
    load();
    loadLiveDeals();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  if (error) return <div className="error">{error}</div>;
  if (!product) return <p className="muted">Loading product details…</p>;

  // Build rich chronological time-series so multiple checks on the same day plot distinctly.
  const urlIds = Object.keys(history);
  const rawEvents: { ts: number; label: string; uid: string; price: number }[] = [];
  for (const uid of urlIds) {
    for (const pt of history[uid] || []) {
      const d = new Date(pt.created_at);
      const ts = d.getTime();
      const label = d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
      rawEvents.push({ ts, label, uid, price: pt.price });
    }
  }
  rawEvents.sort((a, b) => a.ts - b.ts);

  // Bucket events within the same minute together
  const buckets: Record<string, Record<string, number | string>> = {};
  for (const ev of rawEvents) {
    if (!buckets[ev.label]) {
      buckets[ev.label] = { time: ev.label };
    }
    buckets[ev.label][`u${ev.uid}`] = ev.price;
  }
  const chartData = Object.values(buckets);

  async function refresh(urlId: number) {
    setBusy(true);
    try {
      await api.refreshUrl(urlId);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function saveTargetSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!product) return;
    setBusy(true);
    try {
      await api.updateProduct(pid, {
        title: draftTitle.trim() || product.title,
        search_query: draftQuery.trim() || null,
        notify_price: draftNotifyPrice ? Number(draftNotifyPrice) : null,
        notify_percent: draftNotifyPercent ? Number(draftNotifyPercent) : null,
      });
      setEditingTarget(false);
      await load();
      loadLiveDeals();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function submitManualPrice(urlId: number) {
    const val = Number(manualPriceVal);
    if (!val || val <= 0) return;
    setBusy(true);
    try {
      await api.recordManualPrice(urlId, val);
      setManualUrlId(null);
      setManualPriceVal("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function addUrl(e: React.FormEvent) {
    e.preventDefault();
    if (!newUrl.trim()) return;
    setBusy(true);
    try {
      await api.addUrl(
        pid,
        newUrl.trim(),
        newUrlPrice ? Number(newUrlPrice) : null,
      );
      setNewUrl("");
      setNewUrlPrice("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function attachDealToProduct(d: DealOut) {
    setBusy(true);
    try {
      await api.addUrl(pid, d.url, d.price);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function removeUrl(urlId: number) {
    setBusy(true);
    try {
      await api.deleteUrl(urlId);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function removeProduct() {
    await api.deleteProduct(pid);
    nav("/");
  }

  return (
    <>
      <div className="pagehead">
        <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
          <Link to="/" className="muted" style={{ fontWeight: 600 }}>
            ← Back to Watchlist
          </Link>
          {product.category && (
            <span className="store-pill store-default">{product.category}</span>
          )}
          {product.target_hit && (
            <span className="target-hit-badge">🎯 Target Price Reached!</span>
          )}
        </div>
        <div className="row">
          <button
            type="button"
            className="secondary sm"
            onClick={() => setEditingTarget((v) => !v)}
          >
            ✏️ Edit Target &amp; Info
          </button>
          <button type="button" className="danger sm" onClick={removeProduct}>
            🗑️ Delete Product
          </button>
        </div>
      </div>

      {/* Product Header Card */}
      <div className="panel row spread" style={{ alignItems: "center", flexWrap: "wrap" }}>
        <div className="row" style={{ alignItems: "center", gap: 20, flex: 1 }}>
          {product.image ? (
            <img
              src={product.image}
              alt=""
              style={{
                width: 110,
                height: 110,
                objectFit: "contain",
                borderRadius: 14,
                background: "#fff",
                padding: 8,
                border: "1px solid var(--border)",
              }}
            />
          ) : (
            <div className="thumb-placeholder" style={{ width: 96, height: 96, fontSize: 36 }}>
              {product.title.slice(0, 1).toUpperCase()}
            </div>
          )}
          <div style={{ flex: 1 }}>
            <h1 style={{ fontSize: 22, lineHeight: 1.3 }}>{product.title}</h1>
            <div className="row" style={{ marginTop: 8, flexWrap: "wrap", gap: 8 }}>
              {product.store_names.map((s) => (
                <span key={s} className={`store-pill ${storeColorClass(s)}`}>
                  {s}
                </span>
              ))}
              <span className="muted">
                · Last checked {timeAgo(product.last_scraped_at)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Inline Editor for Target Price & Title */}
      {editingTarget && (
        <form className="panel" onSubmit={saveTargetSettings}>
          <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 10 }}>
            ✏️ Edit Product &amp; Target Alert Settings
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
              gap: 14,
            }}
          >
            <div>
              <label>Product Title</label>
              <input
                value={draftTitle}
                onChange={(e) => setDraftTitle(e.target.value)}
                required
              />
            </div>
            <div>
              <label>Slickdeals Search Keyword</label>
              <input
                value={draftQuery}
                onChange={(e) => setDraftQuery(e.target.value)}
                placeholder="e.g. Sony WH-1000XM5"
              />
            </div>
            <div>
              <label>Target Buy Price ($)</label>
              <input
                type="number"
                step="0.01"
                value={draftNotifyPrice}
                onChange={(e) => setDraftNotifyPrice(e.target.value)}
                placeholder="e.g. 199.99"
              />
            </div>
            <div>
              <label>Alert on % Drop</label>
              <input
                type="number"
                step="1"
                value={draftNotifyPercent}
                onChange={(e) => setDraftNotifyPercent(e.target.value)}
                placeholder="e.g. 15"
              />
            </div>
          </div>
          <div className="row" style={{ marginTop: 16 }}>
            <button type="submit" disabled={busy}>
              💾 Save Changes
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => setEditingTarget(false)}
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* 4 Colorful Metric Cards */}
      <div className="kpi-grid">
        <div className="kpi-card indigo">
          <div className="kpi-label">
            <span>Current Best Price</span>
            <span>🏷️</span>
          </div>
          <div className="kpi-value">
            {product.best_price != null ? `$${product.best_price.toFixed(2)}` : "—"}
          </div>
          <div className="kpi-sub">
            {product.price_change_percent != null && product.price_change_percent !== 0 ? (
              <span
                style={{
                  color:
                    product.price_change_percent < 0 ? "var(--good)" : "var(--bad)",
                  fontWeight: 700,
                }}
              >
                {product.price_change_percent < 0 ? "↓" : "↑"}{" "}
                {Math.abs(product.price_change_percent)}% vs previous
              </span>
            ) : (
              "Across all tracked stores"
            )}
          </div>
        </div>

        <div className="kpi-card emerald">
          <div className="kpi-label">
            <span>All-Time Lowest</span>
            <span>⚡</span>
          </div>
          <div className="kpi-value" style={{ color: "var(--good)" }}>
            {product.lowest_price != null
              ? `$${product.lowest_price.toFixed(2)}`
              : "—"}
          </div>
          <div className="kpi-sub">Best recorded price so far</div>
        </div>

        <div className="kpi-card rose">
          <div className="kpi-label">
            <span>All-Time Highest</span>
            <span>📈</span>
          </div>
          <div className="kpi-value">
            {product.highest_price != null
              ? `$${product.highest_price.toFixed(2)}`
              : "—"}
          </div>
          <div className="kpi-sub">Peak recorded price</div>
        </div>

        <div className="kpi-card amber">
          <div className="kpi-label">
            <span>Your Target Goal</span>
            <span>🎯</span>
          </div>
          <div className="kpi-value" style={{ color: "var(--warn)" }}>
            {product.notify_price != null
              ? `$${product.notify_price.toFixed(2)}`
              : product.notify_percent != null
                ? `-${product.notify_percent}%`
                : "Not set"}
          </div>
          <div className="kpi-sub">
            {product.target_hit
              ? "🎉 Target reached — buy now!"
              : product.notify_price != null && product.best_price != null
                ? `$${(product.best_price - product.notify_price).toFixed(2)} above target`
                : "Click Edit Target to set goal"}
          </div>
        </div>
      </div>

      {/* Price History Chart */}
      <div className="panel">
        <div className="row spread" style={{ marginBottom: 14 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>
              📊 Price History &amp; Trend Monitor
            </div>
            <div className="muted">
              Tracks every price check across stores compared against your target
            </div>
          </div>
          {product.notify_price != null && (
            <span className="coupon-chip">
              🎯 Target Line: ${product.notify_price.toFixed(2)}
            </span>
          )}
        </div>

        {chartData.length === 0 ? (
          <div
            style={{
              padding: "32px 16px",
              textAlign: "center",
              background: "var(--panel-2)",
              borderRadius: 12,
            }}
          >
            <div style={{ fontWeight: 600 }}>No price points recorded yet</div>
            <p className="muted" style={{ margin: "6px 0 0" }}>
              Add a store URL below or click <strong>💲 Log Price</strong> on a listing
              to start plotting the price curve.
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <defs>
                {urlIds.map((uid, i) => {
                  const color = COLORS[i % COLORS.length];
                  return (
                    <linearGradient
                      key={uid}
                      id={`grad-${uid}`}
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop offset="5%" stopColor={color} stopOpacity={0.35} />
                      <stop offset="95%" stopColor={color} stopOpacity={0.02} />
                    </linearGradient>
                  );
                })}
              </defs>
              <CartesianGrid stroke="rgba(148, 163, 184, 0.15)" strokeDasharray="3 3" />
              <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
              <YAxis
                stroke="#94a3b8"
                fontSize={12}
                domain={["auto", "auto"]}
                tickFormatter={(v) => `$${v}`}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--panel)",
                  border: "1px solid var(--border-strong)",
                  borderRadius: 10,
                  color: "var(--text)",
                }}
                formatter={(val: number) => [`$${Number(val).toFixed(2)}`, "Price"]}
              />
              {product.notify_price != null && (
                <ReferenceLine
                  y={product.notify_price}
                  stroke="#f59e0b"
                  strokeDasharray="6 4"
                  strokeWidth={2}
                  label={{
                    value: `Target $${product.notify_price}`,
                    fill: "#f59e0b",
                    fontSize: 12,
                    position: "insideTopRight",
                  }}
                />
              )}
              {urlIds.map((uid, i) => {
                const color = COLORS[i % COLORS.length];
                return (
                  <Area
                    key={uid}
                    type="monotone"
                    dataKey={`u${uid}`}
                    name={
                      product.urls.find((u) => String(u.id) === uid)?.store_name ||
                      `Listing ${uid}`
                    }
                    stroke={color}
                    strokeWidth={3}
                    fill={`url(#grad-${uid})`}
                    dot={{ r: 5, fill: color, strokeWidth: 2, stroke: "#fff" }}
                    activeDot={{ r: 7 }}
                    connectNulls
                  />
                );
              })}
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Store Listings Table */}
      <div className="panel">
        <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 4 }}>
          🏪 Tracked Store Listings ({product.urls.length})
        </div>
        <div className="muted" style={{ marginBottom: 12 }}>
          Compare prices across retailers or log a coupon/member price manually
        </div>

        {product.urls.length > 0 && (
          <table>
            <thead>
              <tr>
                <th>Store</th>
                <th>Latest Price</th>
                <th>Stock Status</th>
                <th>Last Checked</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {product.urls.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div className="row" style={{ gap: 8 }}>
                      <span className={`store-pill ${storeColorClass(u.store_name)}`}>
                        {u.store_name}
                      </span>
                      <a
                        href={u.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ fontSize: 13, fontWeight: 600 }}
                      >
                        Open Store Page ↗
                      </a>
                    </div>
                    {u.last_error && (
                      <div
                        style={{
                          color: "var(--warn)",
                          fontSize: 12,
                          marginTop: 4,
                        }}
                      >
                        ⚠️ {u.last_error}
                      </div>
                    )}
                  </td>
                  <td>
                    <span
                      style={{
                        fontSize: 17,
                        fontWeight: 800,
                        color:
                          u.latest_price != null &&
                          u.latest_price === product.best_price
                            ? "var(--good)"
                            : "var(--text)",
                      }}
                    >
                      {u.latest_price != null ? `$${u.latest_price.toFixed(2)}` : "—"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${u.availability}`}>
                      {u.availability.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="muted">{timeAgo(u.last_scraped_at)}</td>
                  <td>
                    <div
                      className="row"
                      style={{ justifyContent: "flex-end", flexWrap: "wrap" }}
                    >
                      {manualUrlId === u.id ? (
                        <div className="row" style={{ gap: 6 }}>
                          <input
                            type="number"
                            step="0.01"
                            style={{ width: 95, padding: "5px 8px" }}
                            placeholder="$ Price"
                            value={manualPriceVal}
                            onChange={(e) => setManualPriceVal(e.target.value)}
                          />
                          <button
                            type="button"
                            className="sm success"
                            disabled={busy}
                            onClick={() => submitManualPrice(u.id)}
                          >
                            Save
                          </button>
                          <button
                            type="button"
                            className="sm secondary"
                            onClick={() => setManualUrlId(null)}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="secondary sm"
                            disabled={busy}
                            onClick={() => {
                              setManualUrlId(u.id);
                              setManualPriceVal(
                                u.latest_price != null ? String(u.latest_price) : "",
                              );
                            }}
                          >
                            💲 Log Price
                          </button>
                          <button
                            type="button"
                            className="secondary sm"
                            disabled={busy}
                            onClick={() => refresh(u.id)}
                          >
                            🔄 Refresh
                          </button>
                          <button
                            type="button"
                            className="danger sm"
                            disabled={busy}
                            onClick={() => removeUrl(u.id)}
                          >
                            ✕
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <form
          className="row"
          style={{ marginTop: 16, flexWrap: "wrap" }}
          onSubmit={addUrl}
        >
          <input
            style={{ flex: 2, minWidth: 240 }}
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            placeholder="Paste another store URL (Amazon, Best Buy, Walmart, eBay…) to compare"
          />
          <input
            type="number"
            step="0.01"
            style={{ width: 150 }}
            value={newUrlPrice}
            onChange={(e) => setNewUrlPrice(e.target.value)}
            placeholder="Price $ (optional)"
          />
          <button disabled={busy || !newUrl.trim()}>+ Add Store URL</button>
        </form>
      </div>

      {/* Live Slickdeals Deal Matches for This Product */}
      <div className="panel">
        <div className="row spread" style={{ marginBottom: 12 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 16 }}>
              🔥 Live Slickdeals Community Deals for "{product.search_query || product.title}"
            </div>
            <div className="muted">
              Automatically checks Slickdeals for active sales, promo codes &amp; rebates
              matching this product
            </div>
          </div>
          <button
            type="button"
            className="secondary sm"
            disabled={loadingDeals}
            onClick={loadLiveDeals}
          >
            {loadingDeals ? "Scanning…" : "🔄 Re-scan Deals"}
          </button>
        </div>

        {loadingDeals ? (
          <p className="muted">Scanning Slickdeals feed…</p>
        ) : liveDeals.length === 0 ? (
          <p className="muted">
            No active Slickdeals posts found right now for this keyword. Click{" "}
            <strong>✏️ Edit Target &amp; Info</strong> above if you want to broaden the
            search keyword.
          </p>
        ) : (
          <div className="grid" style={{ marginTop: 12 }}>
            {liveDeals.map((d) => (
              <div key={d.id} className="card">
                <div className="body">
                  <div className="row spread">
                    <span className={`store-pill ${storeColorClass(d.store_name)}`}>
                      {d.store_name}
                    </span>
                    {d.discount_percent != null && d.discount_percent > 0 && (
                      <span className="trend-badge trend-down">
                        ↓ {d.discount_percent}% OFF
                      </span>
                    )}
                  </div>
                  <div className="title" style={{ marginTop: 8 }} title={d.title}>
                    {d.title}
                  </div>
                  <div className="price-row">
                    {d.price != null ? (
                      <span className="price deal" style={{ fontSize: 20 }}>
                        ${d.price.toFixed(2)}
                      </span>
                    ) : (
                      <span className="price none">Promo Deal</span>
                    )}
                    {d.original_price != null && (
                      <span className="price-strike">
                        ${d.original_price.toFixed(2)}
                      </span>
                    )}
                  </div>
                  {d.coupon_code && (
                    <div style={{ marginTop: 6 }}>
                      <span className="coupon-chip">🎟️ {d.coupon_code}</span>
                    </div>
                  )}
                  <div className="card-footer" style={{ marginTop: 12 }}>
                    <a href={d.url} target="_blank" rel="noreferrer">
                      View Deal ↗
                    </a>
                    <button
                      type="button"
                      className="sm secondary"
                      disabled={busy}
                      onClick={() => attachDealToProduct(d)}
                    >
                      + Attach to Product
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
