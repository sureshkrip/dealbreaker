import { useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { clearToken, getToken, setToken } from "./api";
import AddProduct from "./pages/AddProduct";
import Dashboard from "./pages/Dashboard";
import ProductDetail from "./pages/ProductDetail";
import StoreEditor from "./pages/StoreEditor";

function Login({ onLogin }: { onLogin: () => void }) {
  const [token, setValue] = useState("");
  return (
    <div className="center-screen">
      <div className="panel login-box">
        <div className="brand" style={{ fontSize: 24, fontWeight: 700 }}>
          Dealbreaker
        </div>
        <p className="muted">Enter your admin token to continue.</p>
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
        <div style={{ marginTop: 16 }}>
          <button
            disabled={!token}
            onClick={() => {
              setToken(token);
              onLogin();
            }}
          >
            Sign in
          </button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());

  if (!authed) return <Login onLogin={() => setAuthed(true)} />;

  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand" style={{ color: "var(--text)" }}>
          Dealbreaker
        </NavLink>
        <nav>
          <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
            Products
          </NavLink>
          <NavLink to="/add" className={({ isActive }) => (isActive ? "active" : "")}>
            Add
          </NavLink>
          <NavLink to="/stores" className={({ isActive }) => (isActive ? "active" : "")}>
            Stores
          </NavLink>
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
          <Route path="/add" element={<AddProduct />} />
          <Route path="/product/:id" element={<ProductDetail />} />
          <Route path="/stores" element={<StoreEditor />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </>
  );
}
