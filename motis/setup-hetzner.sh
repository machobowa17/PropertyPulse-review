#!/bin/bash
# Hetzner CAX21 initial setup for MOTIS
# Run as root after creating the server
# Usage: ssh root@<hetzner-ip> 'bash -s' < setup-hetzner.sh

set -euo pipefail

echo "=== Hetzner MOTIS Server Setup ==="

# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Install Docker Compose plugin
apt-get install -y docker-compose-plugin

# Create motis user
useradd -m -s /bin/bash -G docker motis || true

# Create directory structure
MOTIS_DIR="/opt/motis"
mkdir -p "$MOTIS_DIR/data"
chown -R motis:motis "$MOTIS_DIR"

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "1. Copy motis files: scp -r motis/* motis@<hetzner-ip>:/opt/motis/"
echo "2. SSH as motis: ssh motis@<hetzner-ip>"
echo "3. Download data: cd /opt/motis && bash download-data.sh"
echo "4. Import: docker compose --profile import up motis-import"
echo "5. Start: docker compose up -d motis"
echo "6. Test: curl 'http://localhost:8080/api/v1/plan?fromPlace=51.5074,-0.1278&toPlace=51.5013,-0.0886&time=2026-04-22T08:00:00Z&numItineraries=1&mode=TRANSIT,WALK'"
echo ""
echo "Firewall: Only allow port 8080 from EC2 IP (16.60.67.248)"
echo "  ufw allow from 16.60.67.248 to any port 8080"
echo "  ufw allow ssh"
echo "  ufw enable"
