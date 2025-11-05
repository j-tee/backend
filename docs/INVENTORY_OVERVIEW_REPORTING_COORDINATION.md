# Inventory Overview & Reporting Coordination (Frontend → Backend)

## Scope
- Capture the Manage Stocks overview refresh and the shared reporting workspace flourishes now live in the frontend.
- Document the response contracts that the updated UI consumes so backend teams can validate and sustain compatibility.
- Flag remaining storefront-aware reporting gaps and outline the backend work required to unblock the next iteration.

## Frontend Implementation Snapshot
- `src/features/dashboard/pages/ManageStocksPage.tsx` defaults to an **Overview** tab that surfaces the analytics-only `StockProductOverviewPanel.tsx` while CRUD continues to live inside `StockProductDetailModal.tsx`.
- `StockProductOverviewPanel.tsx` requests `fetchProductStockReconciliation` whenever the operator changes the selected stock product, warehouse, or batch. The panel renders reconciliation metrics alongside a storefront-level breakdown table.
- Reporting pages such as `src/features/reports/pages/StockMovementsPage.tsx` share a unified filter pipeline, quick filters, and drill-ins (`MovementDetailModal.tsx`, `ProductMovementSummaryModal.tsx`). Storefront context appears whenever the data is present.
- The UI remains read-only for analytics; CSV/PDF triggers reuse the same endpoints with an `export_format=csv|pdf` query parameter.

## API Contracts the UI Assumes

### 1. `GET /inventory/api/products/{product_id}/stock-reconciliation/`
- **Optional query parameters:** `batch_id`, `warehouse_id` (UUID strings). Omit parameters when not filtering.
- **Response fields consumed:**
  - `product.id`, `product.name`, `product.sku`.
  - `generated_at` timestamp rendered as snapshot time.
  - `filters.batch_name`, `filters.warehouse_name` for confirmation chips.
  - `warehouse.recorded_quantity`, `warehouse.inventory_on_hand`.
  - `warehouse.batches[]`: `batch_identifier`, `quantity`, `arrival_date` (batch selector tooltip content).
  - `storefront.total_on_hand`, `storefront.sellable_now`.
  - `storefront.entries[]` (aka `storefront.breakdown[]`):
    - `storefront` (UUID row key).
    - `storefront_name` (table label).
    - `location` (optional string shown beside the name).
    - `on_hand`, `sellable`, `linked_reservations`, `orphaned_reservations`, `transferred_quantity`, `sold_quantity`, `last_transfer_date`.
  - `reservations.linked_units`, `reservations.orphaned_units`, and `reservations.details[]` (auditing support cases).
  - `sales.completed_units`.
  - `adjustments.shrinkage_units`, `adjustments.correction_units`.
  - `formula.*`: `warehouse_unreserved_units`, `storefront_sellable_units`, `active_reservations_units`, `calculated_baseline`, `baseline_vs_recorded_delta`, `net_adjustment_units`, `formula_explanation`.
- **Type expectations:** Prefer integers/decimals; numeric strings are tolerated. Nulls or blanks display as “not available”.
- **Failure behaviour:** Non-2xx responses show a generic “Unable to fetch reconciliation snapshot” banner; no automatic retry occurs.

### 2. Reporting Endpoints (`/reports/api/**`)
- **Stock movements listing** `GET /reports/api/inventory/movements/`
  - **Query parameters:**
    - Required: `start_date`, `end_date` (`YYYY-MM-DD`).
    - Optional: `page`, `page_size`, `sort_by`, `sort_order`, `search`, `product_ids` (comma-separated UUIDs), `warehouse_id`, `category_id`, `movement_type`, `reference_type`.
  - **Response payload:**
    - Envelope: `success` boolean, `data` array, `meta` pagination object.
    - Movement row fields: `movement_id`, `movement_type`, `reference_type`, `reference_id`, `reference_number`, `created_at`, `product_id`, `product_name`, `sku`, `quantity`, `warehouse_id`, `warehouse_name`, `performed_by`.
    - Storefront context when present: `storefront_id`, `storefront_name`, `from_storefront`, `to_storefront`, `notes`.
- **Quick filter source** `GET /reports/api/inventory/movements/quick-filters/`
  - **Query parameters:** `filter_type` (`top_sellers|most_adjusted|high_transfers|shrinkage`), `start_date`, `end_date`, `limit`.
  - **Response fields:** `product_ids[]` plus `details[]` objects containing `product_id`, `product_name`, `sku`.
- **Product movement summary** `GET /reports/api/inventory/movements/product-summary/`
  - **Query parameters:** `product_id`, `start_date`, `end_date`.
  - **Response fields:** `total_movements`, `net_change`, `warehouse_breakdown[]`, `storefront_breakdown[]`, `top_reasons[]`.
- **Analytics aggregate** `GET /reports/api/inventory/movements/analytics/`
  - **Query parameters:** `start_date`, `end_date`, optional `warehouse_id`, `category_id`.
  - **Response fields:** `totals.*` cards plus chart series `by_day[]`, `by_movement_type[]`.
- **Export behaviour:** Same routes with `export_format=csv|pdf`, expected to stream downloadable files.

### 3. Drill-in Detail Endpoints
- **Sales detail** `GET /sales/api/sales/{sale_id}/`
  - Fields consumed: `sale_number`, `created_at`, `total_amount`, `payment_method`, `customer_name`, `items_detail[]` (`product_name`, `quantity`, `unit_price`, `total`, optional `tax`, `profit`), plus `storefront` or `storefront_name`.
- **Transfer detail** `GET /inventory/api/transfers/{transfer_id}/`
  - Expect both warehouse and storefront identifiers/names (`from_*`, `to_*`) and `items_detail[]` (`product_name`, `quantity`, optional `supplier`, `cost`).
- **Adjustment detail** `GET /inventory/api/adjustments/{adjustment_id}/`
  - Expect `warehouse_name`, `adjustment_type`, `reason`, and `items_detail[]` entries with optional `warehouse_name` and `direction`.

## Backend Implementation Requirements

### 1. Reconciliation Endpoint Audit & Enhancements
- **Objective:** Deliver storefront-level reconciliation data and computed metrics without requiring frontend business logic.
- **Endpoint:** `GET /inventory/api/products/{product_id}/stock-reconciliation/`.
- **Key changes:**
  - Populate `storefront.entries` (or `storefront.breakdown`) for every storefront that has held the product; include zero values for stability.
  - Return numeric `formula.*` values; use `null` rather than empty strings when unavailable.
  - Surface `reservations.details[]` for cart sessions or pending orders so support can explain disparities.
  - Ensure `warehouse.batches[]` includes `batch_identifier`, `quantity`, `arrival_date` to power batch filtering.
- **Acceptance checkpoints:**
  - Multi-storefront products yield one entry per storefront with sellable/reserved figures.
  - Applying `?batch_id=<uuid>` scopes metrics to that batch and echoes `filters.batch_name`.
  - Absent reservations respond with `0` or `null` consistently for `reservations.linked_units` and `reservations.orphaned_units`.
- **Sample response fragment:**
  ```json
  {
    "product": {"id": "uuid", "name": "Cold Brew", "sku": "CB-12"},
    "filters": {"batch_id": "uuid", "batch_name": "May Shipment"},
    "storefront": {
      "entries": [
        {
          "storefront": "uuid-1",
          "storefront_name": "Flagship",
          "location": "Downtown",
          "on_hand": 120,
          "sellable": 110,
          "linked_reservations": 5,
          "orphaned_reservations": 5,
          "transferred_quantity": 20,
          "sold_quantity": 60,
          "last_transfer_date": "2025-10-30T12:30:00Z"
        }
      ]
    },
    "formula": {
      "warehouse_unreserved_units": 80,
      "storefront_sellable_units": 190,
      "net_adjustment_units": -4,
      "formula_explanation": "sellable = on_hand - reservations"
    }
  }
  ```

### 2. Storefront-Aware Stock Movement Reporting
- **Objective:** Enable storefront filtering and display storefront context for every movement row and export.
- **Endpoints:**
  - `GET /reports/api/inventory/movements/`
  - `GET /reports/api/inventory/movements/quick-filters/`
  - `GET /reports/api/inventory/movements/product-summary/`
  - `GET /reports/api/inventory/movements/analytics/`
- **Key changes:**
  - Accept `storefront_id=<uuid>` and `storefront_ids=<uuid,uuid>` filters where relevant and apply them in the data layer.
  - Include storefront metadata (`storefront_id`, `storefront_name`, transfers’ `from_storefront`, `to_storefront`) in `data[]`; return explicit `null` when unknown.
  - Mirror storefront fields in CSV/PDF exports for parity.
  - Ensure aggregation endpoints and quick filters honour storefront filters.
- **Acceptance checkpoints:**
  - Filtering by `storefront_id` limits results to that storefront and exposes its name per movement row.
  - Export files generated with storefront filters contain the matching storefront columns.
  - Analytics totals and charts recalculate when storefront filters are supplied.
- **Sample request:** `GET /reports/api/inventory/movements/?start_date=2025-10-01&end_date=2025-10-31&storefront_id=uuid-flagship&product_ids=uuid-1`
- **Sample movement row:**
  ```json
  {
    "movement_id": "uuid",
    "movement_type": "sale",
    "reference_type": "sale",
    "reference_number": "S-1045",
    "product_id": "uuid-1",
    "product_name": "Cold Brew",
    "storefront_id": "uuid-flagship",
    "storefront_name": "Flagship",
    "quantity": 4,
    "created_at": "2025-10-21T09:10:00Z"
  }
  ```

### 3. Detail Endpoint Parity
- **Objective:** Keep drill-in modals consistent across sales, transfers, and adjustments.
- **Endpoints:**
  - `GET /sales/api/sales/{sale_id}/`
  - `GET /inventory/api/transfers/{transfer_id}/`
  - `GET /inventory/api/adjustments/{adjustment_id}/`
- **Key changes:**
  - Guarantee storefront identifiers or names for sales; return `null` rather than falling back to warehouse values for storefront-originated sales.
  - Transfers should expose `notes`, `linked_transfer_reference`, and both warehouse and storefront name/ID pairs.
  - Adjustments must include an explicit per-line `direction` (`increase` | `decrease`) so the UI can colour-code without extra logic.
- **Acceptance checkpoints:**
  - Sales drill-ins display storefront info whenever the sale originated from a storefront.
  - Transfer details show operator notes and any linked request references.
  - Adjustment line items carry a `direction` flag that QA can verify in the UI.

### 4. Consistent Pagination Envelope & Error Handling
- **Objective:** Align all report responses around a shared envelope for simpler frontend parsing and validation.
- **Endpoints:** All routes under `/reports/api/**`.
- **Key changes:**
  - Standardise responses to `{ "success": true, "data": [...], "meta": { "page": 1, "page_size": 20, "total": 120, "total_pages": 6 } }`.
  - On validation errors (e.g., invalid `storefront_id`), return HTTP 400 with `{ "success": false, "errors": { "storefront_id": "Storefront not found" } }`.
- **Acceptance checkpoints:**
  - Every reports endpoint responds with the same envelope structure.
  - Error payloads expose machine-readable keys for frontend mapping.

## Validation Checklist
- Seed a product with multiple batches, warehouses, and storefront transfers; verify `GET /inventory/api/products/{product_id}/stock-reconciliation/` returns batch metadata, warehouse filters, and storefront rows.
- Call `/reports/api/inventory/movements/?start_date=...&end_date=...&storefront_id=<uuid>` and confirm responses filter correctly and include storefront metadata.
- Fetch `/sales/api/sales/{sale_id}/` for a storefront-originated sale to verify storefront fields feed `MovementDetailModal`.
- Trigger CSV/PDF exports after adding storefront parameters to ensure streamed downloads still succeed with the updated query strings.

## File Reference Index
- `src/features/dashboard/pages/ManageStocksPage.tsx`
- `src/features/dashboard/components/StockProductOverviewPanel.tsx`
- `src/services/inventoryService.ts`
- `src/features/reports/pages/StockMovementsPage.tsx`
- `src/services/reportsService.ts`
- `src/features/reports/components/MovementDetailModal.tsx`
