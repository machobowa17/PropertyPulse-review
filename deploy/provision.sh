#!/usr/bin/env bash
# PropertyPulse — EC2 Instance Provisioning Script
#
# Run this ON the EC2 instance after first SSH connection:
#   curl -fsSL https://raw.githubusercontent.com/machobowa17/PropertyPulse/main/deploy/provision.sh | bash
#   OR: scp this file to the instance and run it
#
# Tested on: Amazon Linux 2023 (AL2023) ARM64 (t4g.small)
#
# What this does:
#   1. Installs Docker + docker-compose
#   2. Installs git, htop, tmux
#   3. Creates app directory structure
#   4. Configures Docker for non-root use
#
# After running, you still need to:
#   - Clone the repo or scp the code
#   - Upload and restore the pg_dump
#   - Set up .env with production values
#   - Run certbot for initial SSL cert
#   - Start services with docker compose

set -euo pipefail

echo "=== PropertyPulse EC2 Provisioning (AL2023 ARM64) ==="
echo ""

# ── 1. System updates ───────────────────────────────────────────────────────
echo "[1/6] Updating system packages..."
sudo dnf update -y -q

# ── 2. Install Docker ───────────────────────────────────────────────────────
echo "[2/6] Installing Docker..."
sudo dnf install -y docker
sudo systemctl enable docker
sudo systemctl start docker

# Add current user to docker group (avoids needing sudo for docker commands)
sudo usermod -aG docker "$(whoami)"

# ── 3. Install Docker Compose (v2 plugin) ───────────────────────────────────
echo "[3/6] Installing Docker Compose..."
DOCKER_COMPOSE_VERSION="v2.29.2"
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -fsSL "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-linux-aarch64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
docker compose version

# ── 4. Install utilities ────────────────────────────────────────────────────
echo "[4/6] Installing git, htop, tmux..."
sudo dnf install -y git htop tmux

# ── 5. Create app directory ─────────────────────────────────────────────────
echo "[5/6] Creating /opt/propertypulse..."
sudo mkdir -p /opt/propertypulse
sudo chown "$(whoami):$(whoami)" /opt/propertypulse

# ── 6. Configure swap (important for 2 GB RAM instances) ────────────────────
echo "[6/6] Configuring 2 GB swap..."
if [ ! -f /swapfile ]; then
  sudo dd if=/dev/zero of=/swapfile bs=1M count=2048 status=progress
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile swap swap defaults 0 0' | sudo tee -a /etc/fstab
  echo "Swap enabled: 2 GB"
else
  echo "Swap already exists, skipping"
fi

echo ""
echo "=== Provisioning complete ==="
echo ""
echo "Next steps:"
echo "  1. Log out and back in (for docker group to take effect)"
echo "  2. Clone the repo:  cd /opt/propertypulse && git clone <repo-url> ."
echo "  3. Copy .env.production to .env and fill in real values"
echo "  4. Upload DB dump:  scp ukproperty.dump ec2-user@<ip>:/opt/propertypulse/"
echo "  5. Run:  ./deploy/setup.sh"
echo ""
