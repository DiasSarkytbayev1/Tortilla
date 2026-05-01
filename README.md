# Tortilla Restaurant Chain Analytics

A restaurant chain operating on different locations that reports their daily transactions of sales (bills) in Excel form at the end of the day. We collect all these bills, join them on our database at the end of the day (temporal, dimensional view) and provide valuable statistics on what sells most, peak timeframes and differences between different locations.

## Project Overview

This system simulates a multi-location tortilla restaurant chain with:
- **100 shop locations** across 10 major Spanish cities
- **Daily sales reporting** in CSV/Excel format
- **Centralized data collection** and database integration
- **Business analytics** for sales insights and location performance

## Architecture

```
Tortilla/
├── src/
│   └── mock_csv_creator.py    # Daily sales data generator
├── tortilla_shops_reports/    # Generated daily reports
│   └── 2026-05-01/           # Date-specific daily sales
│       ├── shop_1.csv        # Individual shop daily bills
│       ├── shop_2.csv
│       └── ...               # 100 shop CSV files
├── database/                  # Database integration (planned)
│   └── mydatabase.db         # SQLite database for analytics
├── analytics/                 # Business intelligence (planned)
├── .venv/                    # UV virtual environment
└── README.md
```

## Data Flow

1. **Daily Reporting**: Each shop generates daily sales reports (bills)
2. **Data Collection**: Reports are collected and processed at end of day
3. **Database Integration**: Data is joined into temporal/dimensional views
4. **Analytics Generation**: Business insights and statistics are produced

## Business Insights Generated

- **Best-selling products** by location and time period
- **Peak timeframes** for customer traffic and sales
- **Location performance** comparisons and rankings
- **Revenue trends** and seasonal patterns
- **Customer behavior** analysis across different cities

## Setup with UV

1. **Create virtual environment:**
   ```bash
   uv venv
   ```

2. **Install dependencies:**
   ```bash
   uv pip install faker pandas
   ```

3. **Generate daily sales data:**
   ```bash
   uv run python src/mock_csv_creator.py
   ```

## Generated Data Format

Each shop's daily report contains individual transactions/bills:
```csv
shop_id,transaction_id,customer_name,city,address,timestamp,tortilla_type,price,quantity
1,uuid-customer-name,Madrid,Address,2026-05-01 14:30:00,classic,12.50,2
```

## Database Schema

The system uses a normalized database structure:
- **customers**: Customer information and registration
- **products**: Tortilla types and pricing
- **orders**: Daily sales transactions
- **order_items**: Individual items in each order

## Customization

To generate data for a specific date, modify line 112 in `mock_csv_creator.py`:
```python
generate_reports("YYYY-MM-DD")  # Change date as needed
```

## Dependencies

- `faker`: Generate realistic mock data
- `pandas`: Data manipulation and CSV export
- `uv`: Python package manager and virtual environment manager
- `sqlite3`: Database for analytics (built-in)
