import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { clearToken, getToken, setToken } from "./api";
import AddProduct from "./pages/AddProduct";
import Dashboard from "./pages/Dashboard";
import LiveDeals from "./pages/LiveDeals";
import ProductDetail from "./pages/ProductDetail";
import StoreEditor from "./pages/StoreEditor";

const THEME_KEY = "dealbreaker_theme";

function Login({ onLogin }: { onLogin: () => void }) {
  const [token, setValue] = useState("");
  return (
    <div className="center-screen">
      <div className="panel login-box">
        <div className="row" style={{ gap: 10, marginBottom: 6 }}>
          <span className="brand-icon">⚡</span>
          <span className="brand-gradient" style={{ fontSize: 24, fontWeight: 800 }}>
            Dealbreaker
          </span>
        </div>
        <p className="muted">
          Personal price tracker &amp; Slickdeals monitor. Enter your admin token to
          continue.
        </p>
        <label>Admin token</label>
        <input
          type="password"
          value={token}
          onChange={(e) => setValue(e.target.value)}
          placeholder="ADMIN_TOKEN"
          onKeyDown={(e) => {
            if (e.key === "Enter" && token) {
              setToken(token);
              onLogin();
            }
          }}
        />
        <div style={{ marginTop: 18 }}>
          <button
            style={{ width: "100%" }}
            disabled={!token}
            onClick={() => {
              setToken(token);
              onLogin();
            }}
          >
            Sign in to Dealbreaker
          </button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [theme, setTheme] = useState<"dark" | "light">(
    () => (localStorage.getItem(THEME_KEY) as "dark" | "light") || "dark",
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand">
          <span className="brand-icon">⚡</span>
          <span className="brand-gradient">Dealbreaker</span>
        </NavLink>
        <nav>
          <NavLink
            to="/"
            end
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            🎯 Watchlist
          </NavLink>
          <NavLink
            to="/deals"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            🔥 Live Deals
          </NavLink>
          <NavLink
            to="/add"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            ➕ Track Product
          </NavLink>
          <NavLink
            to="/stores"
            className={({ isActive }) => (isActive ? "active" : "")}
          >
            🏪 Stores
          </NavLink>
          <button
            type="button"
            className="secondary sm"
            style={{ marginLeft: 6 }}
            onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            title="Switch color theme"
          >
            {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
          </button>
          <a
            href="#"
            onClick={(e) => {
              e.preventDefault();
              clearToken();
              setAuthed(false);
            }}
          >
            Sign out
          </a>
        </nav>
      </header>
      <div className="container">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/deals" element={<LiveDeals />} />
          <Route path="/add" element={<AddProduct />} />
          <Route path="/product/:id" element={<ProductDetail />} />
          <Route path="/stores" element={<StoreEditor />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </>
  );
}
