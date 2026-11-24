# Database design (Phase 2)

All money fields are `DECIMAL(12,2)` (Django `DecimalField`), never float. Every financial record is owned by exactly one user, directly (`owner_id`) or through its parent (budget or goal). Deleting a user cascades to all of their records.

## Entity-relationship diagram

```mermaid
erDiagram
    USER ||--o{ CATEGORY : "creates (custom)"
    USER ||--o{ INCOME : owns
    USER ||--o{ EXPENSE : owns
    USER ||--o{ BUDGET : owns
    USER ||--o{ SAVINGS_GOAL : owns
    USER ||--o{ FINANCIAL_INSIGHT : receives
    USER ||--o{ NOTIFICATION : receives
    CATEGORY ||--o{ INCOME : "classifies (source)"
    CATEGORY ||--o{ EXPENSE : classifies
    CATEGORY ||--o{ BUDGET_CATEGORY_LIMIT : "limited by"
    CATEGORY |o--o{ FIXED_OBLIGATION : "optional"
    BUDGET ||--o{ BUDGET_CATEGORY_LIMIT : has
    BUDGET ||--o{ FIXED_OBLIGATION : has
    SAVINGS_GOAL ||--o{ SAVINGS_CONTRIBUTION : "ledger of"
    SAVINGS_CONTRIBUTION |o--o| SAVINGS_CONTRIBUTION : "reverses"

    USER {
        bigint id PK
        varchar username UK
        varchar email UK
        varchar password "hashed (PBKDF2)"
        varchar university
        smallint year_of_study
        date semester_start
        date semester_end
        bool notify_budget_alerts
        bool notify_insight_alerts
        smallint budget_warning_default
    }
    CATEGORY {
        bigint id PK
        bigint owner_id FK "NULL = system default"
        varchar name
        varchar slug
        varchar kind "income | expense"
        bool is_essential
        varchar keywords
    }
    INCOME {
        bigint id PK
        bigint owner_id FK
        bigint source_id FK
        decimal amount "> 0"
        date date
        varchar description
        varchar reference
        datetime created_at
        datetime updated_at
    }
    EXPENSE {
        bigint id PK
        bigint owner_id FK
        bigint category_id FK
        decimal amount "> 0"
        date date
        varchar payment_method
        varchar description
        varchar reference
        datetime created_at
        datetime updated_at
    }
    BUDGET {
        bigint id PK
        bigint owner_id FK
        varchar name
        varchar period "monthly | semester | custom"
        date start_date
        date end_date ">= start_date"
        decimal total_limit
        smallint warning_threshold "10-100"
    }
    BUDGET_CATEGORY_LIMIT {
        bigint id PK
        bigint budget_id FK
        bigint category_id FK
        decimal limit
    }
    FIXED_OBLIGATION {
        bigint id PK
        bigint budget_id FK
        bigint category_id FK "nullable"
        varchar name
        decimal amount
        date due_date
        bool is_paid
    }
    SAVINGS_GOAL {
        bigint id PK
        bigint owner_id FK
        varchar name
        decimal target_amount
        date target_date
        smallint priority
        varchar status "active | completed | archived"
    }
    SAVINGS_CONTRIBUTION {
        bigint id PK
        bigint goal_id FK
        decimal amount "non-zero, +/-"
        varchar entry_type "allocate | release | reversal"
        bigint reverses_id FK "unique, nullable"
        date date
        varchar note
    }
    FINANCIAL_INSIGHT {
        bigint id PK
        bigint owner_id FK
        varchar kind
        varchar severity
        varchar title
        text message
        json metrics
        text assumptions
        varchar reliability
        char data_fingerprint
        datetime created_at
    }
    NOTIFICATION {
        bigint id PK
        bigint owner_id FK
        varchar level
        varchar title
        varchar message
        varchar link
        varchar dedupe_key
        bool is_read
        datetime created_at
    }
```

## Constraints and indexes

| Table | Constraint / index | Why |
|---|---|---|
| user | unique `username`, unique `email` | one account per person |
| category | unique (`owner`, `kind`, `slug`); unique (`kind`, `slug`) where owner is NULL | no duplicate names per student or among defaults |
| income / expense | CHECK `amount > 0`; index (`owner`, `date`) | valid amounts; fast date-range queries per student |
| expense | index (`owner`, `category`) | fast category breakdowns |
| budget | CHECK `end_date >= start_date`; index (`owner`, `start_date`, `end_date`) | valid ranges; find active budgets quickly |
| budget_category_limit | unique (`budget`, `category`) | one limit per category per budget |
| savings_contribution | CHECK `amount <> 0`; unique `reverses_id` | no empty entries; an entry can be reversed only once |
| savings_goal | index (`owner`, `status`) | list active goals |
| insight / notification | index (`owner`, `created_at`), (`owner`, `is_read`) | recent insights; unread counts |

Category foreign keys use `ON DELETE PROTECT`, so a category in use cannot be deleted and silently orphan transactions.

> MySQL/MariaDB do not support conditional (partial) unique indexes. Django skips the "system category" unique constraint on MySQL; the same rule is enforced by the data migration and the category form.

## Design decisions and trade-offs

* **Custom user model from the first migration.** Django recommends this because switching later is very hard. It also lets us add semester dates and notification preferences without a separate profile table.
* **Separate Income and Expense tables** instead of one signed "transaction" table. Each has different fields (source vs category and payment method), and separate tables make totals impossible to mix up. The cost is a union in "recent activity", done in Python.
* **Categories as a table, not hard-coded choices.** Students can add their own, and keywords for the auto-categoriser live with the category.
* **Budget utilisation is calculated, not stored.** Spent amounts are summed from expenses at read time, so they are always correct after edits and deletions. With student-sized data this is fast thanks to the (`owner`, `date`) index.
* **Savings as an append-only ledger.** The goal's balance is the sum of its entries; corrections are reversal entries, giving a full audit trail and simple reconciliation.
* **Insights stored with a data fingerprint.** This keeps a dated history and avoids recomputing models on every page view.
* **No identifiable personal data beyond what login needs.** No phone, admission number or wallet credentials (proposal section 3.8).
