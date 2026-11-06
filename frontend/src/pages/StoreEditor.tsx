import { useEffect, useState } from "react";
import { api, ApiError, storeColorClass } from "../api";
import type { Store, UrlPreviewOut } from "../types";

const FIELDS = ["title", "price", "image", "availability"] as const;
const TYPES = ["selector", "regex", "json", "schema.org"];

export default function StoreEditor() {
  const [stores, setStores] = useState<Store[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState<Store["scrape_strategy"]>({});
  const [domainsInput, setDomainsInput] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  // Strategy tester state
  const [testUrl, setTestUrl] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<UrlPreviewOut | null>(null);

  async function load() {
    try {
      const list = await api.listStores();
      setStores(list);
      if (selected == null && list.length) selectStore(list[0]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function selectStore(s: Store) {
    setSelected(s.id);
    setDraft(JSON.parse(JSON.stringify(s.scrape_strategy || {})));
    setDomainsInput((s.domains || []).join(", "));
    setSaved(false);
    setTestResult(null);
  }

  function setField(field: string, key: "type" | "value", value: string) {
    setDraft((d) => {
      const next = { ...d };
      const current = next[field] || { type: "selector", value: "" };
      if (key === "value" && value === "" && !current.value) {
        delete next[field];
      } else {
        next[field] = { ...current, [key]: value };
      }
      return next;
    });
    setSaved(false);
  }

  function getCleanedStrategy(): Store["scrape_strategy"] {
    const cleaned: Store["scrape_strategy"] = {};
    for (const [k, v] of Object.entries(draft)) {
      if (v && v.value) cleaned[k] = v;
    }
    return cleaned;
  }

  async function save() {
    if (selected == null) return;
    const cleaned = getCleanedStrategy();
    const domains = domainsInput
      .split(",")
      .map((d) => d.trim().toLowerCase())
      .filter(Boolean);
    try {
      await api.updateStore(selected, {
        domains,
        scrape_strategy: cleaned,
      });
      setSaved(true);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  async function runTest() {
    if (selected == null || !testUrl.trim()) return;
    setTesting(true);
    setError("");
    try {
      const res = await api.testStoreStrategy(
        selected,
        testUrl.trim(),
        getCleanedStrategy(),
      );
      setTestResult(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setTesting(false);
    }
  }

  const current = stores.find((s) => s.id === selected);

  return (
    <>
      <div className="hero-banner">
        <div>
          <h1>🏪 Store Scrape Strategies &amp; Tester</h1>
          <p>
            Configure CSS selectors, regexes, or JSON-LD paths per retailer — and
            test them live against any product URL.
          </p>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      <div
        className="row"
        style={{
          alignItems: "flex-start",
          gap: 22,
          marginTop: 22,
          flexWrap: "wrap",
        }}
      >
        <div style={{ width: 250, flexShrink: 0 }}>
          {stores.map((s) => (
            <div
              key={s.id}
              className="card"
              style={{
                padding: "12px 14px",
                marginBottom: 10,
                borderColor: s.id === selected ? "var(--accent)" : undefined,
                cursor: "pointer",
              }}
              onClick={() => selectStore(s)}
            >
              <div className="row spread">
                <span className={`store-pill ${storeColorClass(s.name)}`}>
                  {s.name}
                </span>
                <span className="muted" style={{ fontSize: 11 }}>
                  {Object.keys(s.scrape_strategy || {}).length} rules
                </span>
              </div>
              <div className="muted" style={{ marginTop: 6, fontSize: 12 }}>
                {s.domains.join(", ") || "no domains"}
              </div>
            </div>
          ))}
        </div>

        {current && (
          <div className="panel" style={{ flex: 1, marginTop: 0, minWidth: 320 }}>
            <div className="spread row">
              <div className="row" style={{ gap: 10 }}>
                <span className={`store-pill ${storeColorClass(current.name)}`}>
                  {current.name}
                </span>
                <span style={{ fontWeight: 700, fontSize: 18 }}>
                  Strategy Configuration
                </span>
              </div>
              {saved && <span className="badge in_stock">✅ Saved</span>}
            </div>

            <div style={{ marginTop: 14 }}>
              <label>Matched Domains (comma-separated)</label>
              <input
                value={domainsInput}
                onChange={(e) => {
                  setDomainsInput(e.target.value);
                  setSaved(false);
                }}
                placeholder="amazon.com, amazon.ca"
              />
            </div>

            <p className="muted" style={{ marginTop: 14 }}>
              Leave a field blank to use the automatic schema.org / OpenGraph /
              microdata fallback. You can provide comma-separated fallback
              selectors (e.g. <code>#productTitle, h1</code> or{" "}
              <code>#landingImage|src</code>).
            </p>

            {FIELDS.map((field) => (
              <div key={field} style={{ marginTop: 14 }}>
                <label style={{ textTransform: "capitalize" }}>{field}</label>
                <div className="row">
                  <select
                    style={{ width: 145, flexShrink: 0 }}
                    value={draft[field]?.type || "selector"}
                    onChange={(e) => setField(field, "type", e.target.value)}
                  >
                    {TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                  <input
                    value={draft[field]?.value || ""}
                    onChange={(e) => setField(field, "value", e.target.value)}
                    placeholder={`${field} selector / pattern`}
                  />
                </div>
              </div>
            ))}

            <div style={{ marginTop: 18 }}>
              <button onClick={save}>💾 Save Store Strategy</button>
            </div>

            {/* Live Strategy Tester */}
            <div
              className="panel"
              style={{
                background: "var(--panel-2)",
                marginTop: 24,
                padding: 16,
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: 6 }}>
                🧪 Test Current Strategy on a Sample URL
              </div>
              <div className="row">
                <input
                  value={testUrl}
                  onChange={(e) => setTestUrl(e.target.value)}
                  placeholder={`https://www.${current.domains[0] || "store.com"}/...`}
                />
                <button
                  type="button"
                  className="secondary"
                  disabled={testing || !testUrl.trim()}
                  onClick={runTest}
                  style={{ flexShrink: 0 }}
                >
                  {testing ? "Testing…" : "🧪 Test Scrape"}
                </button>
              </div>

              {testResult && (
                <div style={{ marginTop: 14 }}>
                  <div className="row spread">
                    <div>
                      <div style={{ fontWeight: 700 }}>
                        Title: {testResult.title || "—"}
                      </div>
                      <div className="muted" style={{ marginTop: 4 }}>
                        Availability:{" "}
                        <span className={`badge ${testResult.availability}`}>
                          {testResult.availability}
                        </span>
                      </div>
                    </div>
                    <div className="price deal">
                      {testResult.price != null
                        ? `$${testResult.price.toFixed(2)}`
                        : "No price"}
                    </div>
                  </div>
                  {testResult.error && (
                    <div className="warn-banner">{testResult.error}</div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
