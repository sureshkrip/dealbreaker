import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";
import type { ProductListItem } from "../types";

export default function Dashboard() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

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

  return (
    <>
      <div className="pagehead">
        <h1>Tracked products</h1>
        <div className="row">
          <button className="secondary" onClick={refreshAll} disabled={refreshing}>
            {refreshing ? "Refreshing…" : "Refresh all"}
          </button>
          <Link to="/add">
            <button>Add product</button>
          </Link>
        </div>
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <p className="muted">Loading…</p>}
      {!loading && products.length === 0 && (
        <p className="muted">No products yet. Add one to start tracking prices.</p>
      )}

      <div className="grid">
        {products.map((p) => (
          <Link key={p.id} to={`/product/${p.id}`} className="card">
            <div className="thumb">
              {p.image ? <img src={p.image} alt="" /> : <span className="muted">No image</span>}
            </div>
            <div className="body">
              <div className="title">{p.title}</div>
              {p.best_price != null ? (
                <div className="price">${p.best_price.toFixed(2)}</div>
              ) : (
                <div className="price none">No price yet</div>
              )}
              <div className="muted">
                {p.store_count} listing{p.store_count === 1 ? "" : "s"}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
