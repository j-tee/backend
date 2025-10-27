# Frontend Handoff — POS Sale Catalog Source of Truth

_Last updated: 2025-10-08_

## TL;DR

The POS search drawer is still hydrating its product list from raw storefront inventory totals. That dataset includes products that were manually fulfilled without matching `StockProduct` metadata, so ghost items such as **ELEC-0009** sneak into the UI with a `GH¢0.00` price. The backend now exposes a sale catalog endpoint that filters those ghosts out. The frontend must switch to that endpoint and treat `stock_product_ids` as the gating criterion before rendering a product.

---

## 1. What’s happening today

| Symptom | Cause | Consequence |
| --- | --- | --- |
| `ELEC-0009` (and similar) appear in search even though there is no `StockProduct` row | The React POS continues to read from `/inventory/api/storefronts/<id>/inventory/` (or cached GraphQL equivalent) which only checks `StoreFrontInventory.quantity` | Cashiers see products with `0.00` price and the add-to-cart call fails when it can’t resolve a stock product |
| Price buttons show `GH¢0.00` for affected items | Old UI pulls price from the deprecated `Product` record or defaults to zero when absent | Sales team can accidentally sell at zero unless they override |
| Checkout errors with `No stock product found` when trying to add ghost items | Backend validation enforces existence of `StockProduct` and rejects the request | Checkout stalls, user retraces steps |

**Key takeaway:** Any UI list that originates from `StoreFrontInventory` must stop rendering items whose `stock_product_ids` array is empty. The backend now gives you a curated list that already enforces this rule.

---

## 2. New source of truth — `sale-catalog` endpoint

```
GET /inventory/api/storefronts/{storefront_id}/sale-catalog/
GET /inventory/api/storefronts/{storefront_id}/sale-catalog/?include_zero=true  # optional
```

### Query params
- `include_zero` (bool, optional): set to `true` only when you need to show out-of-stock SKUs (for managers/audit views). For cashiers, omit it so the list stays clean.

### Response shape
```json
{
  "storefront": "8d1c...",
  "products": [
    {
      "product_id": "2a7f...",
      "product_name": "Cat6 Ethernet Cable 305m",
      "sku": "ELEC-0011",
      "category_name": "Electrical Cables",
      "available_quantity": 12,
      "retail_price": "12.50",
      "wholesale_price": "10.50",
      "stock_product_ids": [
        "b114...",
        "5bcf..."
      ],
      "last_stocked_at": "2025-10-08T14:23:11.902Z"
    }
  ]
}
```

#### Contract guarantees
- Every entry has at least one `stock_product_id`; products without stock metadata never appear.
- `available_quantity` is the summed, unreserved storefront quantity (same value you previously derived manually).
- `retail_price` and `wholesale_price` come from the most recent stock product; they’re strings because DRF serializes decimals as strings — cast to numbers on the client for math.
- `last_stocked_at` lets you display “last restock” badges if desired.

---

## 3. Action items for the frontend team

1. **Replace the data source** for the POS search/results grid with `sale-catalog`.
2. **Stop rendering inventory rows** when `stock_product_ids.length === 0` (defensive guard even with the new endpoint).
3. **Display prices from `retail_price` / `wholesale_price`**, not from `Product` records.
4. **Update quick-add / barcode workflows** to use the first stock product ID from `stock_product_ids` when calling `POST /sales/api/sales/{sale_id}/add-item/`.
5. **Purge cached responses** or stale Redux slices keyed by the old endpoint (`storefrontInventory`, `catalogItems`, etc.).
6. **Handle `include_zero=true` only** in management views (if you have separate toggles) so normal cashiers aren’t flooded with zero-quantity items.

---

## 4. Suggested implementation steps

### 4.1 Networking layer
- Create a dedicated client helper, e.g. `fetchSaleCatalog(storefrontId: string, opts?: { includeZero?: boolean })`.
- Wire it into the POS bootstrap (wherever you currently call `loadStorefrontInventory`).
- Cache/storefront the payload under a new slice (`saleCatalog`) to avoid confusing it with the old inventory structure.

### 4.2 UI state management
- Update selectors so product search, barcode scan, and quick-add all read from `saleCatalog.products`.
- When the user types in the search box, filter on `product_name`, `sku`, and maybe `category_name`; do **not** fall back to legacy arrays.
- If you need a map keyed by SKU for barcode lookup, build it from the `products` array on load.

### 4.3 Checkout integration
- Update the cart-add routine to send `stock_product_id` using `catalogItem.stock_product_ids[0]` (or let the user choose if you surface multiple batches).
- If the array is empty (should not happen), show a blocking toast: “This item is missing a stock batch — contact inventory.” Don’t attempt the API call.
- Use `retail_price` as the default unit price when populating the cart line. If the cashier overrides the price, keep your existing override flow.

### 4.4 Safeguards in UI
- Wherever you render quantity pills (“30 in stock”), use `available_quantity` from the catalog directly.
- Consider showing a subtle warning icon when `available_quantity` is 0 — that only happens when you explicitly call `include_zero=true`.
- Surface `last_stocked_at` in the detail drawer so staff can tell whether the item is ancient.

---

## 5. QA / validation checklist

- [ ] Hit the new endpoint in DevTools and confirm `products` excludes `ELEC-0009` (no `StockProduct`, so it should be absent).
- [ ] Verify search results match the endpoint payload exactly — no extra ghosts.
- [ ] Scan a barcode for a catalog item; ensure the cart add uses the correct `stock_product_id` and succeeds.
- [ ] Attempt to sell a previously ghost item (e.g. `ELEC-0009`) — it should no longer appear anywhere in the UI.
- [ ] Complete a sale and confirm inventory decrements as expected.
- [ ] Toggle any “show out of stock” filters and check that only then do zero-quantity rows appear.

---

## 6. Appendix: TypeScript scaffolding

```ts
export interface SaleCatalogItem {
  product_id: string;
  product_name: string;
  sku: string;
  category_name?: string | null;
  available_quantity: number;
  retail_price: string;      // cast to number via parseFloat when needed
  wholesale_price?: string | null;
  stock_product_ids: string[];
  last_stocked_at?: string | null;
}

export interface SaleCatalogResponse {
  storefront: string;
  products: SaleCatalogItem[];
}
```

---

## 7. References

- Backend tests that enforce the contract: `inventory.tests.StorefrontSaleCatalogAPITest`
- Serializer defining the payload: `inventory.serializers.StorefrontSaleProductSerializer`
- Endpoint implementation: `inventory.views.StoreFrontViewSet.sale_catalog`

Ping backend if you need additional fields (e.g. landed cost or batch info); the data is all in the viewset and can be exposed quickly.
