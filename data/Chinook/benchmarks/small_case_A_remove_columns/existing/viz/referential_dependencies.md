# Referential Dependencies

- database: `chinook`
- dialect: `postgresql`

## Tables

| table | rows | columns | primary_key |
|---|---:|---|---|
| customer | 10 | customer_id, first_name, last_name, company, address, city, state, postal_code, phone, fax, support_rep_id | customer_id |
| invoice | 10 | invoice_id, customer_id, invoice_date, billing_address, billing_city, billing_state, billing_country, billing_postal_code, total | invoice_id |

## Foreign Keys

| child_table | child_columns | parent_table | parent_columns | on_delete | on_update |
|---|---|---|---|---|---|
| invoice | customer_id | customer | customer_id | no_action | no_action |
