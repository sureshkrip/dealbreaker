import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError } from "../api";
import type { PricePoint, ProductOut } from "../types";

const COLORS = ["#4ea1ff", "#37d67a", "#ffb020", "#ff5c5c", "#b98cff"];

export default function ProductDetail() {
  const { id } = useParams();
  const pid = Number(id);
  const nav = useNavigate();
  const [product, setProduct] = useState<ProductOut | null>(null);
  const [history, setHistory] = useState<Record<string, PricePoint[]>>({});
  const [error, setError] = useState("");
  const [newUrl, setNewUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [p, h] = await Promise.all([api.getProduct(pid), api.productPrices(pid)]);
      setProduct(p);
      setHistory(h);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pid]);

  if (error) return <div className="error">{error}</div>;
  if (!product) return <p className="muted">Loading…</p>;

  // Merge all URL histories into one time-series keyed by timestamp.
  const urlIds = Object.keys(history);
  const pointsByTime: Record<string, Record<string, number>> = {};
  for (const uid of urlIds) {
    for (const pt of history[uid]) {
      const t = new Date(pt.created_at).toLocaleDateString();
      pointsByTime[t] = pointsByTime[t] || { time: t as unknown as number };
      pointsByTime[t][`u${uid}`] = pt.price;
    }
  }
  const chartData = Object.entries(pointsByTime).map(([time, vals]) => ({ time, ...vals }));

  async function refresh(urlId: number) {
    setBusy(true);
    try {
      await api.refreshUrl(urlId);
      await load();
    } finally {
      setBusy(false);
    }
  }

  async function addUrl(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.addUrl(pid, newUrl.trim());
      setNewUrl("");
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
        <h1>{product.title}</h1>
        <button className="danger" onClick={removeProduct}>
          Delete
        </button>
      </div>

      <div className="panel row spread" style={{ alignItems: "flex-start" }}>
        <div className="row" style={{ alignItems: "flex-start", gap: 18 }}>
          {product.image && (
            <img
              src={product.image}
              alt=""
              style={{ width: 120, height: 120, objectFit: "contain", borderRadius: 8 }}
            />
          )}
          <div>
            <div className="muted">Current best price</div>
            <div className="price">
              {product.best_price != null ? `$${product.best_price.toFixed(2)}` : "—"}
            </div>
            <div className="muted" style={{ marginTop: 8 }}>
              {product.notify_price != null && `Target: $${product.notify_price.toFixed(2)} `}
              {product.notify_percent != null && `· Alert on ${product.notify_percent}% drop`}
            </div>
          </div>
        </div>
      </div>

      {chartData.length > 0 && (
        <div className="panel">
          <div className="muted" style={{ marginBottom: 8 }}>
            Price history
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartData}>
              <CartesianGrid stroke="#2a2f3a" strokeDasharray="3 3" />
              <XAxis dataKey="time" stroke="#98a0ad" fontSize={12} />
              <YAxis stroke="#98a0ad" fontSize={12} domain={["auto", "auto"]} />
              <Tooltip
                contentStyle={{
                  background: "#181b22",
                  border: "1px solid #2a2f3a",
                  borderRadius: 8,
                }}
              />
              {urlIds.map((uid, i) => (
                <Line
                  key={uid}
                  type="monotone"
                  dataKey={`u${uid}`}
                  name={
                    product.urls.find((u) => String(u.id) === uid)?.store_name || `Listing ${uid}`
                  }
                  stroke={COLORS[i % COLORS.length]}
                  dot={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="panel">
        <div className="muted" style={{ marginBottom: 4 }}>
          Listings
        </div>
        <table>
          <thead>
            <tr>
              <th>Store</th>
              <th>Price</th>
              <th>Availability</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {product.urls.map((u) => (
              <tr key={u.id}>
                <td>
                  <a href={u.url} target="_blank" rel="noreferrer">
                    {u.store_name}
                  </a>
                </td>
                <td>{u.latest_price != null ? `$${u.latest_price.toFixed(2)}` : "—"}</td>
                <td>
                  <span className={`badge ${u.availability}`}>
                    {u.availability.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="row" style={{ justifyContent: "flex-end" }}>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => refresh(u.id)}
                  >
                    Refresh
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <form className="row" style={{ marginTop: 16 }} onSubmit={addUrl}>
          <input
            value={newUrl}
            onChange={(e) => setNewUrl(e.target.value)}
            placeholder="Add another store URL for this product"
          />
          <button disabled={busy || !newUrl}>Add</button>
        </form>
      </div>
    </>
  );
}
