# ER Diagram: expected
```mermaid
erDiagram
    CUSTOMER {
        integer customer_id PK "not_null"
        string first_name "not_null"
        string last_name "not_null"
        string company "nullable"
        string address "nullable"
        string city "nullable"
        string state "nullable"
        string country "nullable"
        string postal_code "nullable"
        string phone "nullable"
        string fax "nullable"
        string email "not_null"
        integer support_rep_id "nullable"
    }
    INVOICE {
        integer invoice_id PK "not_null"
        integer customer_id FK "not_null"
        timestamp invoice_date "not_null"
        string billing_address "nullable"
        string billing_city "nullable"
        string billing_state "nullable"
        string billing_country "nullable"
        string billing_postal_code "nullable"
        decimal total "not_null"
    }
    ARTIST {
        integer artist_id PK "not_null"
        string name "nullable"
    }
    ALBUM {
        integer album_id PK "not_null"
        string title "not_null"
        integer artist_id FK "not_null"
    }
    TRACK {
        integer track_id PK "not_null"
        string name "not_null"
        integer album_id FK "nullable"
        integer media_type_id "not_null"
        integer genre_id "nullable"
        string composer "nullable"
        integer milliseconds "not_null"
        integer bytes "nullable"
        decimal unit_price "not_null"
    }
    INVOICE_LINE {
        integer invoice_line_id PK "not_null"
        integer invoice_id FK "not_null"
        integer track_id FK "not_null"
        decimal unit_price "not_null"
        integer quantity "not_null"
    }

    ARTIST ||--o{ ALBUM : "artist_id -> artist_id"
    CUSTOMER ||--o{ INVOICE : "customer_id -> customer_id"
    INVOICE ||--o{ INVOICE_LINE : "invoice_id -> invoice_id"
    TRACK ||--o{ INVOICE_LINE : "track_id -> track_id"
    ALBUM ||--o{ TRACK : "album_id -> album_id"

```
