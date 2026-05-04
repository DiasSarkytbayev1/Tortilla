# Install PostgreSQL (15+ ships in Ubuntu 22.04+ repos)
sudo apt update && sudo apt install -y postgresql postgresql-contrib

# Start the service
sudo systemctl enable --now postgresql

# Create the database and user
sudo -u postgres psql <<'SQL'
CREATE USER tortilla_user WITH PASSWORD 'tortilla_pass';
CREATE DATABASE tortilla_db OWNER tortilla_user;
SQL
