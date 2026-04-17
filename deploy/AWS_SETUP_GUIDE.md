# PropertyPulse — AWS Setup Guide

Step-by-step instructions for launching on AWS EC2.

---

## Step 1: AWS Console Setup

### 1a. Set region
Top-right corner → switch to **EU (London) eu-west-2**

### 1b. Create Key Pair
1. EC2 → Key Pairs → **Create key pair**
2. Name: `propertypulse`
3. Type: **ED25519**
4. Format: **.pem** (for macOS/Linux)
5. Download the `.pem` file → save to `~/.ssh/propertypulse.pem`
6. Run: `chmod 400 ~/.ssh/propertypulse.pem`

### 1c. Launch EC2 Instance
1. EC2 → **Launch Instance**
2. Name: `PropertyPulse`
3. AMI: **Amazon Linux 2023** (ARM — should be default for t4g)
4. Instance type: **t4g.small** (2 vCPU, 2 GB RAM — free tier)
5. Key pair: `propertypulse` (created above)
6. Network:
   - Create security group or select existing
   - Allow: **SSH (22)** from your IP
   - Allow: **HTTP (80)** from anywhere (0.0.0.0/0)
   - Allow: **HTTPS (443)** from anywhere (0.0.0.0/0)
7. Storage: **80 GB gp3** (change from default 8 GB!)
8. Click **Launch Instance**

### 1d. Allocate Elastic IP
1. EC2 → Elastic IPs → **Allocate Elastic IP address**
2. Click **Allocate**
3. Select the new IP → **Actions → Associate Elastic IP address**
4. Choose your `PropertyPulse` instance → **Associate**
5. Note down the IP: `___.___.___.__`

---

## Step 2: DNS Setup

Point your domain to the Elastic IP:

| Record | Name | Value |
|--------|------|-------|
| A | `@` (or `yourdomain.co.uk`) | `YOUR_ELASTIC_IP` |
| A | `www` | `YOUR_ELASTIC_IP` |

If using Route 53, create a hosted zone for your domain.
If using an external registrar (Namecheap, etc.), add these A records there.

**Wait for DNS propagation** (usually 5-30 minutes):
```bash
dig +short yourdomain.co.uk
# Should return your Elastic IP
```

---

## Step 3: SSH In and Provision

```bash
# SSH to your instance
ssh -i ~/.ssh/propertypulse.pem ec2-user@YOUR_ELASTIC_IP

# Run the provisioning script
# Option A: If repo is accessible
cd /opt/propertypulse
git clone https://github.com/machobowa17/PropertyPulse.git .
./deploy/provision.sh

# Option B: scp files from your Mac first
# (from your Mac terminal):
scp -i ~/.ssh/propertypulse.pem -r "/Users/batty/Desktop/Manus Take 2/deploy" ec2-user@YOUR_ELASTIC_IP:/tmp/
ssh -i ~/.ssh/propertypulse.pem ec2-user@YOUR_ELASTIC_IP "sudo mv /tmp/deploy /opt/propertypulse/ && cd /opt/propertypulse && ./deploy/provision.sh"
```

**Log out and back in** (for docker group):
```bash
exit
ssh -i ~/.ssh/propertypulse.pem ec2-user@YOUR_ELASTIC_IP
```

---

## Step 4: Upload Code + DB Dump

From your Mac:
```bash
# Upload the entire codebase
rsync -avz --exclude='node_modules' --exclude='.git' --exclude='etl/data' \
  -e "ssh -i ~/.ssh/propertypulse.pem" \
  "/Users/batty/Desktop/Manus Take 2/" \
  ec2-user@YOUR_ELASTIC_IP:/opt/propertypulse/

# Upload the database dump (this will take a while — ~10 GB over the internet)
scp -i ~/.ssh/propertypulse.pem \
  /Volumes/PropertyPulse/ukproperty_20260417_v3.dump \
  ec2-user@YOUR_ELASTIC_IP:/opt/propertypulse/ukproperty.dump
```

**Tip:** For the large DB dump, consider uploading to S3 first (faster), then downloading on EC2:
```bash
# From Mac:
aws s3 cp /Volumes/PropertyPulse/ukproperty_20260417_v3.dump s3://YOUR-BUCKET/ukproperty.dump

# From EC2:
aws s3 cp s3://YOUR-BUCKET/ukproperty.dump /opt/propertypulse/ukproperty.dump
```

---

## Step 5: Configure and Launch

On the EC2 instance:
```bash
cd /opt/propertypulse

# Create production .env
cp .env.production .env
nano .env
# Fill in:
#   POSTGRES_PASSWORD=<strong random password>
#   ALLOWED_ORIGINS=https://yourdomain.co.uk,https://www.yourdomain.co.uk
#   ADMIN_API_KEY=<random key>

# Run setup (in tmux so DB restore survives SSH disconnect)
tmux new -s setup
./deploy/setup.sh yourdomain.co.uk
```

---

## Step 6: Verify

```bash
# Check all services are running
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# Check from your browser
# https://yourdomain.co.uk — should show the PropertyPulse frontend
# https://yourdomain.co.uk/api/docs — should show FastAPI Swagger docs
```

---

## Ongoing Operations

### Deploy a code update
```bash
cd /opt/propertypulse
git pull
./deploy/update.sh
```

### View logs
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api
```

### psql shell
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db psql -U ukproperty
```

### Restart a service
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml restart api
```

### Resize instance (e.g., to t4g.medium)
1. EC2 Console → select instance → **Instance State → Stop**
2. **Actions → Instance Settings → Change instance type** → t4g.medium
3. **Instance State → Start**
4. Services auto-restart (docker restart policies)

### Renew SSL cert (auto via certbot sidecar, but manual if needed)
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm certbot certbot renew
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec frontend nginx -s reload
```

### Refresh materialized views (run weekly)
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec db psql -U ukproperty -c "
  REFRESH MATERIALIZED VIEW mv_parent_yearly_ppsf;
  REFRESH MATERIALIZED VIEW mv_parent_rolling_price_stats;
  REFRESH MATERIALIZED VIEW mv_parent_yearly_price_stats;
  REFRESH MATERIALIZED VIEW mv_parent_noise_avg;
  REFRESH MATERIALIZED VIEW mv_parent_crime_rate;
"
```
