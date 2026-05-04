# Run the init script (creates all tables + seeds restaurants + menu items)
psql -U tortilla_user -h localhost -d tortilla_db -f init_db.sql

# Python deps
uv pip install -r requirements.txt