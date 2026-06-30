# Referential Dependencies

- database: `chinook`
- dialect: `postgresql`

## Tables

| table | rows | columns | primary_key |
|---|---:|---|---|
| customer | 10 | customer_id, first_name, last_name, company, address, city, state, country, postal_code, phone, fax, email, support_rep_id | customer_id |
| invoice | 10 | invoice_id, customer_id, invoice_date, billing_address, billing_city, billing_state, billing_country, billing_postal_code, total | invoice_id |
| artist | 10 | artist_id, name | artist_id |
| album | 10 | album_id, title, artist_id | album_id |
| track | 10 | track_id, name, album_id, media_type_id, genre_id, composer, milliseconds, bytes, unit_price | track_id |
| invoice_line | 10 | invoice_line_id, invoice_id, track_id, unit_price, quantity | invoice_line_id |

## Foreign Keys

| child_table | child_columns | parent_table | parent_columns | on_delete | on_update |
|---|---|---|---|---|---|
| album | artist_id | artist | artist_id | no_action | no_action |
| invoice | customer_id | customer | customer_id | no_action | no_action |
| invoice_line | invoice_id | invoice | invoice_id | no_action | no_action |
| invoice_line | track_id | track | track_id | no_action | no_action |
| track | album_id | album | album_id | no_action | no_action |
