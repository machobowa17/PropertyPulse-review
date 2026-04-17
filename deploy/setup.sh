#!/usr/bin/env bash
# PropertyPulse — First-time setup (run after provision.sh + code clone)
#
# Prerequisites:
#   - provision.sh has been run and you've logged out/in (docker group)
#   - Code is at /opt/propertypulse
#   - .env file exists with production values
#   - DB dump file is at /opt/propertypulse/ukproperty.dump (optional — can restore later)
#
# Usage:
#   cd /opt/propertypulse && ./deploy/setup.sh YOUR_DOMAIN.co.uk

set -euo pipefail

DOMAIN="${1:-}"
APP_DIR="/opt/propertypulse"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

if [ -z "$DOMAIN" ]; then
  echo "Usage: ./deploy/setup.sh YOUR_DOMAIN.co.uk"
  exit 1
fi

if [ ! -f "$APP_DIR/.env" ]; then
  echo "ERROR: .env file not found. Copy .env.production to .env and fill in values."
  exit 1
fi

cd "$APP_DIR"

echo "=== PropertyPulse Setup for ${DOMAIN} ==="
echo ""

# ── 1. Patch nginx configs with actual domain ───────────────────────────────
echo "[1/7] Configuring nginx for ${DOMAIN}..."
sed -i "s/server_name _;/server_name ${DOMAIN} www.${DOMAIN};/g" frontend/nginx-ssl.conf
sed -i "s|/etc/letsencrypt/live/DOMAIN/|/etc/letsencrypt/live/${DOMAIN}/|g" frontend/nginx-ssl.conf

# Also update ALLOWED_ORIGINS in .env if still has placeholder
sed -i "s|YOUR_DOMAIN|${DOMAIN}|g" "$APP_DIR/.env"

# ── 2. Build Docker images (ARM64) ──────────────────────────────────────────
echo "[2/7] Building Docker images (this takes a few minutes on first run)..."
$COMPOSE build

# ── 3. Start database + redis first ─────────────────────────────────────────
echo "[3/7] Starting database and Redis..."
$COMPOSE up -d db redis
echo "  Waiting for PostgreSQL to be ready..."
for i in $(seq 1 30); do
  $COMPOSE exec db pg_isready -U ukproperty -q 2>/dev/null && break
  sleep 2
done
$COMPOSE exec db pg_isready -U ukproperty

# ── 4. Restore database dump ────────────────────────────────────────────────
DUMP_FILE="$APP_DIR/ukproperty.dump"
if [ -f "$DUMP_FILE" ]; then
  echo "[4/7] Restoring database dump..."
  echo "  This may take 30+ minutes for a large DB. Run in tmux!"
  # Create the database first (pg_restore needs it to exist)
  $COMPOSE exec db psql -U ukproperty -c "SELECT 1;" -d ukproperty 2>/dev/null || \
    $COMPOSE exec db createdb -U ukproperty ukproperty 2>/dev/null || true
  # Enable PostGIS
  $COMPOSE exec db psql -U ukproperty -d ukproperty -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null || true
  # Restore
  $COMPOSE exec -T db pg_restore -U ukproperty -d ukproperty \
    --no-owner --no-privileges --jobs=2 --if-exists --clean \
    < "$DUMP_FILE" 2>&1 | tail -5
  echo "  Database restore complete."
else
  echo "[4/7] No dump file found at $DUMP_FILE — skipping."
  echo "  Upload your dump and run:"
  echo "    $COMPOSE exec -T db pg_restore -U ukproperty -d ukproperty --no-owner --no-privileges --jobs=2 < ukproperty.dump"
fi

# ── 5. Get initial SSL certificate (Let's Encrypt) ──────────────────────────
echo "[5/7] Obtaining Let's Encrypt certificate..."

# First boot: nginx-ssl.conf references cert files that don't exist yet.
# Use the plain HTTP nginx.conf temporarily for the ACME challenge.
echo "  Starting nginx in HTTP-only mode for ACME challenge..."
$COMPOSE up -d frontend  # Uses prod override which mounts nginx-ssl.conf

# But ssl.conf will fail because certs don't exist. Override with HTTP-only temporarily:
docker cp "$APP_DIR/frontend/nginx.conf" ukproperty_frontend:/etc/nginx/conf.d/default.conf
docker exec ukproperty_frontend nginx -s reload 2>/dev/null || docker restart ukproperty_frontend
sleep 3

# Verify port 80 is reachable
curl -sf http://localhost/nginx-health > /dev/null && echo "  HTTP server ready for ACME challenge" || echo "  WARNING: HTTP not responding yet"

# Request certificate via certbot
$COMPOSE run --rm certbot \
  certbot certonly --webroot \
    --webroot-path=/var/www/certbot \
    --email "admin@${DOMAIN}" \
    --agree-tos \
    --no-eff-email \
    -d "${DOMAIN}" \
    -d "www.${DOMAIN}"

echo "  SSL certificate obtained. Switching nginx to HTTPS mode..."

# Now restore the SSL config (certs exist now)
docker cp "$APP_DIR/frontend/nginx-ssl.conf" ukproperty_frontend:/etc/nginx/conf.d/default.conf
docker exec ukproperty_frontend nginx -s reload
echo "  HTTPS enabled."

# ── 6. Start all services ───────────────────────────────────────────────────
echo "[6/7] Starting all services..."
$COMPOSE up -d

# ── 7. Verify ────────────────────────────────────────────────────────────────
echo "[7/7] Verifying services..."
sleep 8
echo ""
echo "Service status:"
$COMPOSE ps
echo ""
echo "Health checks:"
$COMPOSE exec db pg_isready -U ukproperty -q && echo "  PostgreSQL: OK" || echo "  PostgreSQL: FAIL"
$COMPOSE exec redis redis-cli ping | grep -q PONG && echo "  Redis: OK" || echo "  Redis: FAIL"
curl -sf http://localhost:8000/api/docs > /dev/null && echo "  API: OK" || echo "  API: starting up..."
curl -sf https://localhost/nginx-health -k > /dev/null && echo "  Nginx HTTPS: OK" || echo "  Nginx HTTPS: starting up..."

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  Your site is live at: https://${DOMAIN}"
echo "============================================"
echo ""
echo "Useful commands:"
echo "  $COMPOSE logs -f api        # tail API logs"
echo "  $COMPOSE exec db psql -U ukproperty  # psql shell"
echo "  $COMPOSE restart api        # restart API"
echo "  ./deploy/update.sh          # deploy code update"
echo ""
