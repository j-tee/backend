# DataLogique Systems Sales Dataset Reset

**Date:** October 7, 2025  
**Command:** `python manage.py regenerate_datalogique_sales`

This note documents the regeneration of realistic sales data for the DataLogique Systems demo tenant.

---

## 🎯 Goal
- Clear out the original placeholder sales that only contained draft carts.
- Seed believable transactional history covering completed, credit-partial, pending, and draft sales.
- Provide an easy command to re-run whenever the dataset needs a refresh.

---

## 🔁 Command Summary

The management command lives in `sales/management/commands/regenerate_datalogique_sales.py`.

```bash
/home/teejay/Documents/Projects/pos/backend/venv/bin/python manage.py regenerate_datalogique_sales \
  --completed 85 \
  --partial 25 \
  --pending 15 \
  --draft 15 \
  --seed 42
```

Flags are optional; defaults match the values above. Use a different `--seed` for another randomised mix.

What the command does:
1. Deletes existing `Sale`, `SaleItem`, and `Payment` records for DataLogique Systems.
2. Resets customer credit balances.
3. Ensures storefront, products, and key customers exist.
4. Generates a fresh set of transactions with realistic receipt numbers, line items, payments, and outstanding balances.

---

## 📊 Dataset Snapshot

| Metric | Value |
|--------|-------|
| Total sales | **140** |
| Completed | **85** |
| Partial credit | **25** |
| Pending credit | **15** |
| Draft carts | **15** |
| Completed revenue | **GHS 293,424.64** |
| Outstanding balance (partial + pending) | **GHS 115,678.80** |
| Payments recorded | **150** |

### Status Mix
- **Completed**: Paid in full across cash, card, and mobile money.
- **Partial**: Credit customers with partial payments (balances range 200 – 4,500).
- **Pending**: Fully unpaid credit invoices.
- **Draft**: Open carts with realistic line items but no receipt number.

---

## 🧱 Data Building Blocks

### Products
Ten core POS products spanning hardware, consumables, software, and networking equipment (see `PRODUCT_TEMPLATES` in the command).

### Customers
Six active customers, including walk-in retail and wholesale buyers with sensible credit limits and terms. All balances were reset before regeneration.

### Receipts
Receipt numbers follow the format `DLGS-YYYYMMDD-####` for easy human parsing and uniqueness.

### Payments
- Completed cash/card/mobile sales register a single matching `Payment` entry.
- Completed credit invoices (27 of the 85 completed sales) simulate bank-transfer repayments with 1–3 instalments each.
- Partial credit sales log one or two instalments and keep a remaining balance outstanding.
- Pending credit sales intentionally carry zero payments.

### Credit portfolio highlights
- `payment_type=CREDIT&status=COMPLETED` now returns fully settled invoices with multi-instalment histories (perfect for collection reports).
- `payment_type=CREDIT&status=PARTIAL` shows invoices mid-way through repayment with outstanding balances.
- `has_outstanding_balance=true` continues to surface both PARTIAL and PENDING credit sales.

---

## 🛠️ Customisation Tips
- **Different volumes:** adjust the `--completed`, `--partial`, `--pending`, or `--draft` flags.
- **Fresh randomness:** change `--seed` or omit it for a time-based seed.
- **Product mix:** tweak `PRODUCT_TEMPLATES` for new SKUs or price points.
- **Customer portfolio:** edit `CUSTOMER_TEMPLATES` for additional retailers/wholesalers.

Whenever you tweak the templates, re-run the command to re-seed the environment.

---

## ✅ Quick Validation Checklist
After running the command:

- [x] `Sale.objects.filter(business=...)` shows the counts above.
- [x] `amount_paid = total_amount` for completed sales.
- [x] Partial sales show both a payment and a remaining due amount.
- [x] Pending sales show `amount_paid = 0` while retaining full totals.
- [x] Draft sales have no receipt number and remain unpaid.

---

## 📣 Next Steps
- Hand this note + the command path to QA and frontend teams so they can freely reset a clean demo environment whenever required.
- Incorporate the command into any data reset scripts or CI fixtures if automated resets are needed.
