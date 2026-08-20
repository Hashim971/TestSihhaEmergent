import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { toast } from "sonner";
import { Search, ShoppingBag, ReceiptText } from "lucide-react";
import { RefillsDue } from "../components/pharmacy/RefillsDue";
import { CatalogGrid } from "../components/pharmacy/CatalogGrid";
import { CartDrawer } from "../components/pharmacy/CartDrawer";
import { PharmacyList } from "../components/pharmacy/PharmacyList";

const CATEGORIES = [
  { key: "", label: "All" },
  { key: "prescription", label: "Prescription" },
  { key: "otc", label: "Over the counter" },
  { key: "supplement", label: "Supplements" },
  { key: "device", label: "Devices" },
  { key: "personal_care", label: "Personal care" },
];

export default function Pharmacy() {
  const { activeProfile } = useAuth();
  const navigate = useNavigate();
  const [refills, setRefills] = useState(null);
  const [items, setItems] = useState(null);
  const [pharmacies, setPharmacies] = useState([]);
  const [cart, setCart] = useState(null);
  const [cartOpen, setCartOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [busyId, setBusyId] = useState(null);

  const loadCart = useCallback(() => api.get("/pharmacy/cart", { params: { profile_id: activeProfile.id } })
    .then(({ data }) => setCart(data)).catch(() => {}), [activeProfile.id]);

  const loadCatalog = useCallback(() => {
    setItems(null);
    api.get("/pharmacy/catalog", { params: { q: query || undefined, category: category || undefined, limit: 24 } })
      .then(({ data }) => setItems(data.items)).catch(() => setItems([]));
  }, [query, category]);

  useEffect(() => {
    api.get("/pharmacy/refills", { params: { profile_id: activeProfile.id, notify: true } })
      .then(({ data }) => setRefills(data)).catch(() => setRefills({ due: [], upcoming: [], unknown: [] }));
    api.get("/pharmacy/pharmacies").then(({ data }) => setPharmacies(data)).catch(() => {});
    loadCart();
  }, [activeProfile.id, loadCart]);

  useEffect(() => {
    const t = setTimeout(loadCatalog, 250);
    return () => clearTimeout(t);
  }, [loadCatalog]);

  const addToCart = async (item) => {
    setBusyId(item.item_id);
    try {
      const { data } = await api.post("/pharmacy/cart/items", { item_id: item.item_id, qty: 1,
        profile_id: activeProfile.id });
      setCart(data);
      setCartOpen(true);
    } catch (e) {
      const violations = e?.response?.data?.detail?.violations;
      if (violations) violations.forEach((v) => toast.error(v.message));
      else toast.error("Could not add that product");
    } finally {
      setBusyId(null);
    }
  };

  const cartCount = (cart?.items || []).reduce((n, l) => n + l.qty, 0);

  return (
    <div className="space-y-8 fade-up" data-testid="pharmacy-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Pharmacy</h1>
          <p className="text-ink-soft mt-1 max-w-2xl">
            Find which partner pharmacy has your medicine, then buy on their site or get directions to the branch.
            Sihha holds no stock and dispenses nothing.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => navigate("/pharmacy/orders")} data-testid="open-orders-btn" className="btn-outline">
            <ReceiptText className="h-4 w-4" /> Orders
          </button>
          <button onClick={() => setCartOpen(true)} data-testid="open-cart-btn" className="btn-primary">
            <ShoppingBag className="h-4 w-4" /> Basket{cartCount ? ` · ${cartCount}` : ""}
          </button>
        </div>
      </div>

      <RefillsDue refills={refills} onReorder={addToCart} onSearch={setQuery} busyId={busyId} />

      <div className="card p-5 space-y-4" data-testid="catalog-controls">
        <div className="relative">
          <Search className="h-4 w-4 text-ink-soft absolute left-3 top-1/2 -translate-y-1/2" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} data-testid="catalog-search-input"
            placeholder="Search by brand or generic name — e.g. Concor, Bisoprolol, بنادول"
            className="w-full border border-line rounded-full pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-forest" />
        </div>
        <div className="flex flex-wrap gap-2">
          {CATEGORIES.map((c) => (
            <button key={c.key} onClick={() => setCategory(c.key)} data-testid={`category-${c.key || "all"}`}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                category === c.key ? "bg-forest text-white border-forest" : "border-line text-ink-soft hover:bg-sand"}`}>
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <CatalogGrid items={items} onAdd={addToCart} busyId={busyId} />

      <div>
        <h2 className="text-lg font-semibold mb-3">Partner pharmacies</h2>
        <PharmacyList pharmacies={pharmacies} />
      </div>

      <CartDrawer open={cartOpen} onClose={() => setCartOpen(false)} cart={cart} reload={loadCart}
        onOrdered={() => { setCartOpen(false); navigate("/pharmacy/orders"); }} />
    </div>
  );
}
