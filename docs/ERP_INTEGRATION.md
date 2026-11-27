# Connecting QuoteProof to any ERP

QuoteProof does not assume an ERP. Each customer gets a **tenant profile**
(`profiles/<name>.toml`) that holds every customer-specific rule and the ERP
connection. No customer-specific logic lives in code.

## What QuoteProof needs from an ERP

Three read-only lookups, nothing more:

| Lookup | Used for | Required |
| --- | --- | --- |
| `item` by item number | list price, price floor, currency, export flag, sales block | yes |
| `customer_by_id` / `customer_by_name` | delivery block, credit hold, country | recommended |
| `customer_names` | outbound check: no other customer's name in a quotation | optional |

QuoteProof **never writes** to an ERP. The ERP answers are stored with the
review as evidence, each record with its source.

## Case 1: an unknown three-tier ERP with a SQL data tier

The usual Mittelstand situation: client, application server, SQL database, and
an application layer nobody documents. QuoteProof skips the application layer
and reads the database through any DB-API 2.0 driver.

1. Ask the customer's IT for a **read-only database user**, ideally limited to
   two views, e.g. `qp_v_items` and `qp_v_customers`. Views decouple QuoteProof
   from the ERP's table structure and keep the access narrow.
2. Copy `profiles/example-sql-3tier.toml` to `profiles/<customer>.toml`.
3. Set `driver` (`pyodbc` for MS SQL Server, `oracledb`, `psycopg`, `pymysql`,
   `ibm_db_dbi`, …) and install it.
4. Put the connection string into the environment variable named in
   `connection_env`. It never goes into the profile.
5. Map the view's column names in the `columns` tables. Placeholders are
   written as `:sku`, `:customer_id`, `:name`; QuoteProof translates them to
   the driver's parameter style.
6. Check it:

   ```bash
   QUOTEPROOF_ERP_DSN='…' python -m quoteproof.check_profile <customer> --sku 4711 --customer-id K-100
   ```

7. Run the API with `QUOTEPROOF_PROFILE=<customer>`.

Built-in safeguards of the SQL adapter, enforced when the profile loads:

- only a single `SELECT` or `WITH` statement, no `;`, no SQL comments;
- write, DDL and execution keywords (`INSERT`, `UPDATE`, `DELETE`, `MERGE`,
  `DROP`, `ALTER`, `CREATE`, `EXEC`, `INTO`, …) are rejected; read hints such
  as `WITH (NOLOCK)` are fine;
- values are always bound as parameters;
- German number formats (`1.850,00`) and ERP flags (`J`/`N`, `X`, `1`/`0`)
  are understood;
- a lookup that returns several rows for one item or customer is treated as
  unavailable, not guessed.

The read-only database user stays the second line of defence.

## Case 2: an ERP with an API (Odoo, SAP OData, Business Central, …)

Write a small adapter with three methods and register it:

```python
from quoteproof.erp import register_adapter

class OdooAdapter:
    adapter_id = "odoo"
    def __init__(self, options): ...
    def customer(self, customer_id, name): ...   # -> ERPCustomer | None
    def items(self, skus): ...                    # -> dict[str, ERPItem]
    def customer_names(self): ...                 # -> list[str]

register_adapter("odoo", OdooAdapter)
```

Then set `adapter = "odoo"` in the profile. Everything else, including the
controls and the audit trail, stays the same.

## Case 3: exports instead of a live connection

`adapter = "static"` with `file = "path/to/export.json"` reads customers and
items from a JSON export. This suits pilots, demos and customers who allow no
direct access. `profiles/demo-erp.toml` shows it.

## What happens when the ERP does not answer

QuoteProof fails closed. If the ERP is unreachable, the driver is missing, the
connection variable is unset or a lookup is ambiguous, the quotation receives
`QP-ERP-001` and goes to human review. It is never passed on missing evidence.
With `required = true`, a profile without a working adapter does the same.

## Controls added by the ERP and profile layer

| Code | Effect | Rule |
| --- | --- | --- |
| `QP-RULE-001` | review | A rule in the profile is a placeholder, not confirmed |
| `QP-ERP-001` | review | ERP evidence required but unavailable |
| `QP-ERP-002` | review | Item not found in the ERP |
| `QP-ERP-003` | review | Customer not found in the ERP |
| `QP-ERP-004` | block | Customer has a delivery block |
| `QP-ERP-005` | review | Customer on credit hold |
| `QP-ERP-006` | block | Item blocked for sale |
| `QP-PRICE-001` | block | Net unit price below ERP floor plus minimum margin |
| `QP-PRICE-002` | review | Unit price deviates from ERP list price beyond tolerance |
| `QP-PRICE-003` | review | ERP price currency differs; no implicit conversion |
| `QP-EXPORT-002` | block | ERP marks an item as controlled goods, the quotation does not |
| `QP-OUT-001` | block | Internal pricing language in the customer document |
| `QP-OUT-002` | block | An internal ERP cost figure in the customer document |
| `QP-OUT-003` | block | Another customer's name in the customer document |
| `QP-REV-001` | review | Lower price for an unchanged scope: the margin moved |
| `QP-REV-002` | block | Revision number not increased |
| `QP-REV-003` | block | Previous version belongs to another quotation |
| `QP-APPROVAL-001` | review | The approval covered a different decision basis |
| `QP-SANCTIONS-001` | block | Restricted-party match, legal form and punctuation ignored |
| `QP-SANCTIONS-002` | review | Close restricted-party match; a person rules it out |

## Approvals bound to a decision basis

Every review returns a `decision_basis_hash`: a SHA-256 fingerprint of the
quotation (customer, items, prices, terms, flags, the customer document) and
the active rules. An `ApprovalRecord` stores the hash it was given on. Send it
with a later version to `POST /review/revision`: if anything material changed,
the approval has lapsed (`QP-APPROVAL-001`). A yes covers exactly what was
shown, not what came after.
