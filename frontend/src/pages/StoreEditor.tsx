import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Store } from "../types";

const FIELDS = ["title", "price", "image", "availability"] as const;
const TYPES = ["selector", "regex", "json", "schema.org"];

export default function StoreEditor() {
  const [stores, setStores] = useState<Store[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [draft, setDraft] = useState<Store["scrape_strategy"]>({});
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

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
    setSaved(false);
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

  async function save() {
    if (selected == null) return;
    // Drop fields with empty values.
    const cleaned: Store["scrape_strategy"] = {};
    for (const [k, v] of Object.entries(draft)) {
      if (v && v.value) cleaned[k] = v;
    }
    try {
      await api.updateStore(selected, { scrape_strategy: cleaned });
      setSaved(true);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  const current = stores.find((s) => s.id === selected);

  return (
    <>
      <div className="pagehead">
        <h1>Stores &amp; scrape strategies</h1>
      </div>
      {error && <div className="error">{error}</div>}
      <div className="row" style={{ alignItems: "flex-start", gap: 20, marginTop: 20 }}>
        <div style={{ width: 220, flexShrink: 0 }}>
          {stores.map((s) => (
            <div
              key={s.id}
              className="card"
              style={{
                padding: "10px 12px",
                marginBottom: 8,
                borderColor: s.id === selected ? "var(--accent)" : undefined,
                cursor: "pointer",
              }}
              onClick={() => selectStore(s)}
            >
              <div style={{ fontWeight: 600 }}>{s.name}</div>
              <div className="muted">{s.domains.join(", ") || "no domains"}</div>
            </div>
          ))}
        </div>

        {current && (
          <div className="panel" style={{ flex: 1, marginTop: 0 }}>
            <div className="spread row">
              <div style={{ fontWeight: 600, fontSize: 18 }}>{current.name}</div>
              {saved && <span className="badge in_stock">Saved</span>}
            </div>
            <p className="muted">
              Leave a field blank to use the schema.org / OpenGraph fallback.
              <br />
              Selector examples: <code>#productTitle</code>, <code>.price .a-offscreen</code>,{" "}
              <code>img#main|src</code> (append <code>|attr</code> for an attribute).
            </p>
            {FIELDS.map((field) => (
              <div key={field} style={{ marginTop: 14 }}>
                <label style={{ textTransform: "capitalize" }}>{field}</label>
                <div className="row">
                  <select
                    style={{ width: 140 }}
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
              <button onClick={save}>Save strategy</button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
