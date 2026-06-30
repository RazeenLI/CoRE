# Referential Dependencies

- database: `chinook`
- dialect: `postgresql`

## Tables

| table | rows | columns | primary_key |
|---|---:|---|---|
| album | 347 | album_id, title, artist_id | album_id |
| artist | 275 | artist_id, name | artist_id |
| customer | 59 | customer_id, first_name, last_name, company, address, city, state, country, postal_code, phone, fax, email, support_rep_id | customer_id |
| employee | 8 | employee_id, last_name, first_name, title, reports_to, birth_date, hire_date, address, city, state, country, postal_code, phone, fax, email | employee_id |
| genre | 25 | genre_id, name | genre_id |
| invoice | 412 | invoice_id, customer_id, invoice_date, billing_address, billing_city, billing_state, billing_country, billing_postal_code, total | invoice_id |
| invoice_line | 2240 | invoice_line_id, invoice_id, track_id, unit_price, quantity | invoice_line_id |
| media_type | 5 | media_type_id, name | media_type_id |
| playlist | 18 | playlist_id, name | playlist_id |
| playlist_track | 8715 | playlist_id, track_id | playlist_id, track_id |
| track | 3503 | track_id, name, album_id, media_type_id, genre_id, composer, milliseconds, bytes, unit_price | track_id |

## Foreign Keys

| child_table | child_columns | parent_table | parent_columns | on_delete | on_update |
|---|---|---|---|---|---|
| album | artist_id | artist | artist_id | no_action | no_action |
| customer | support_rep_id | employee | employee_id | no_action | no_action |
| employee | reports_to | employee | employee_id | no_action | no_action |
| invoice | customer_id | customer | customer_id | no_action | no_action |
| invoice_line | invoice_id | invoice | invoice_id | no_action | no_action |
| invoice_line | track_id | track | track_id | no_action | no_action |
| playlist_track | playlist_id | playlist | playlist_id | no_action | no_action |
| playlist_track | track_id | track | track_id | no_action | no_action |
| track | album_id | album | album_id | no_action | no_action |
| track | genre_id | genre | genre_id | no_action | no_action |
| track | media_type_id | media_type | media_type_id | no_action | no_action |
