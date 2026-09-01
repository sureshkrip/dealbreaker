import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";

export default function AddProduct() {
  const nav = useNavigate();
  const [url, setUrl] = useState("");
  const [notifyPrice, setNotifyPrice] = useState("");
  const [notifyPercent, setNotifyPercent] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const product = await api.addProduct({
        url: url.trim(),
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
      <div className="pagehead">
        <h1>Add a product</h1>
      </div>
      <form className="panel" onSubmit={submit}>
        <label>Product URL</label>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://store.example/product/123"
          required
        />
        <div className="row" style={{ gap: 16 }}>
          <div style={{ flex: 1 }}>
            <label>Notify at price (optional)</label>
            <input
              type="number"
              step="0.01"
              value={notifyPrice}
              onChange={(e) => setNotifyPrice(e.target.value)}
              placeholder="e.g. 49.99"
            />
          </div>
          <div style={{ flex: 1 }}>
            <label>Notify on % drop (optional)</label>
            <input
              type="number"
              step="1"
              value={notifyPercent}
              onChange={(e) => setNotifyPercent(e.target.value)}
              placeholder="e.g. 20"
            />
          </div>
        </div>
        {error && <div className="error">{error}</div>}
        <div style={{ marginTop: 18 }}>
          <button disabled={busy || !url}>
            {busy ? "Scraping…" : "Track product"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: 12 }}>
          We'll scrape the title, image and price. If the price doesn't come through,
          set a scrape strategy for that store under <strong>Stores</strong>.
        </p>
      </form>
    </>
  );
}
