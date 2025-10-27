# POS Stock Detail Header — Frontend Checklist

_Last updated: 2025-10-09_

Use this guide when wiring the product/batch detail modal in the POS. It maps every banner metric to the correct backend endpoint and shows how to compute the reconciliation line without double-counting warehouse stock, storefront inventory, or reservations.

---

## 1. Snapshot of the correct UI

The header should surface **one warehouse batch** (a `StockProduct`) and optionally multiple storefronts that carry the product. For SKU `ELEC-0007` the truthful headline numbers on 2025-10-09 were:

| Label | Value | Source |
| --- | --- | --- |
| Warehouse on hand | **26** | `GET /inventory/api/stock-products/<stock_product_id>/` → `quantity` |
| Storefront on hand | **23** total (Cow Lane 3, Adenta 20) | `/inventory/api/storefronts/<storefront_id>/stock-products/<product_id>/availability/` → `total_available` |
| Sellable now | **23** | Same availability payload → `unreserved_quantity` |
| Units sold | **10** | `/sales/api/sales/?product=<uuid>&status=COMPLETED` → sum `sale_items[].quantity` |
| Active reservations | **0** | Availability payload → `reserved_quantity` |
| Adjustments (out / in) | **0 / 0** | `/inventory/api/stock-adjustments/?stock_product=<uuid>&status=COMPLETED` |

These numbers reconcile back to the original intake (26) once sales and storefront transfers are accounted for.

---

## 2. Data contracts at a glance

### Warehouse batch (`StockProduct`)
- Endpoint: `GET /inventory/api/stock-products/<stock_product_id>/`
- Critical fields: `quantity`, `product`, `retail_price`, `wholesale_price`, `warehouse_name`, `created_at`
- Use `quantity` for the “Warehouse on hand” chip.

### Storefront availability
- Endpoint: `GET /inventory/api/storefronts/<storefront_id>/stock-products/<product_id>/availability/`
- Fields: `total_available`, `reserved_quantity`, `unreserved_quantity`, `batches[]`, `reservations[]`
- Use `total_available` for “Storefront on hand” and `unreserved_quantity` for “Sellable now”.
- For multi-store views: sum `total_available` and `reserved_quantity` across the storefront list the user can access.

### Sales history
- Endpoint: `GET /sales/api/sales/?product=<uuid>&status=COMPLETED`
- Fields: Use `sale_items[].quantity` and optionally `sale_items[].stock_product` to filter by batch.
- Sum the `quantity` of sale items whose `product` matches the modal’s product. That total feeds “Units sold”.

### Stock adjustments (optional but recommended)
- Endpoint: `GET /inventory/api/stock-adjustments/?stock_product=<uuid>&status=COMPLETED`
- Negative `quantity` → shrinkage (theft, damage, sampling). Positive `quantity` → corrections / returns.
- Surface as “Adjustments out” and “Adjustments in” badges if needed.
- Server-side helpers exist (`StockProduct.get_adjustment_summary()`) if you later request a simplified API.

---

## 3. Banner formula

Your reconciliation bar underneath the chips should evaluate to the original intake. Treat shrinkage as a positive term and corrections as negative:

```
warehouse_on_hand
+ storefront_on_hand
+ units_sold
+ adjustments_out      # abs(negative adjustments)
- adjustments_in       # positive adjustments
- reservations         # current holds
= initial_intake       # or expected batch total
```

When there are no adjustments or active reservations the formula collapses to the simpler form.

For ELEC-0007 on 2025-10-09:

```
26 (warehouse)
+ 23 (storefront)
+ 10 (sold)
+ 0 (adjustments out)
- 0 (adjustments in)
- 0 (reservations)
= 59  → matches original processed quantity
```

---

## 4. Implementation walkthrough

```ts
// 1. Batch info (warehouse)
const { data: stockProduct } = await api.get(
  `/inventory/api/stock-products/${stockProductId}/`
);

// 2. Storefront availability (loop through storefronts relevant to the signed-in user)
const availability = await Promise.all(
  storefrontIds.map(async (storefrontId) => {
    const { data } = await api.get(
      `/inventory/api/storefronts/${storefrontId}/stock-products/${stockProduct.product}/availability/`
    );
    return { storefrontId, availability: data };
  })
);

const storefrontOnHand = availability.reduce(
  (sum, entry) => sum + entry.availability.total_available,
  0
);

const reservations = availability.reduce(
  (sum, entry) => sum + entry.availability.reserved_quantity,
  0
);

// 3. Units sold
const sales = await api.get(
  `/sales/api/sales/?product=${stockProduct.product}&status=COMPLETED`
);

const unitsSold = sales.results // adjust for your pagination strategy
  .flatMap((sale) => sale.sale_items)
  .filter((item) => item.product === stockProduct.product)
  .reduce((sum, item) => sum + Number(item.quantity), 0);

// 4. Adjustments (optional)
const adjustments = await api.get(
  `/inventory/api/stock-adjustments/?stock_product=${stockProductId}&status=COMPLETED`
);

const { adjustmentsIn, adjustmentsOut } = adjustments.results.reduce(
  (acc, adj) => {
    const qty = Number(adj.quantity);
    if (qty >= 0) acc.adjustmentsIn += qty; // count corrections separately
    else acc.adjustmentsOut += Math.abs(qty); // shrinkage is positive in the banner
    return acc;
  },
  { adjustmentsIn: 0, adjustmentsOut: 0 }
);

// 5. Reconciliation string for the banner
const initialIntake =
  stockProduct.quantity +
  storefrontOnHand +
  unitsSold +
  adjustmentsOut -
  adjustmentsIn -
  reservations;
```

Display each component as a chip and render the banner line:

```
Warehouse (26) + Storefront (23) + Sold (10)
+ Adjustments out (0) - Adjustments in (0) - Reservations (0)
= 59 — Initial intake 26
```

> **Reminder**: “Sellable now” is just the `unreserved_quantity` from the availability payload. Do not recompute it after subtracting reservations or sales—the backend already handles that math atomically when a sale completes or abandons.

---

## 5. Troubleshooting cheatsheet

| Symptom | Likely cause | Quick fix |
| --- | --- | --- |
| “Warehouse on hand” shows 0 | Using storefront endpoint instead of stock-product endpoint | Fetch `quantity` from `/inventory/api/stock-products/<id>/` |
| “Units sold” frozen at 3 | Counting transfers or draft sales | Sum `sale_items` only where `sale.status ∈ {COMPLETED, PARTIAL}` |
| Banner doesn’t balance | Missing adjustments or reservations | Pull `/stock-adjustments/` and use `reserved_quantity` from availability |
| Sellable now differs from chip | Recomputing `unreserved_quantity` on the client | Use exact value from availability endpoint |

Keep this guide beside the reconciliation doc to ensure the POS stays in sync with the backend math. Ping the backend team if any field names or payloads change—we can expose a consolidated serializer if the client needs fewer round trips.
