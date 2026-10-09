#!/bin/bash
#
# SSL Certificate Setup Script
# Configures Let's Encrypt SSL certificates for GATE Platform
#
# Usage: ./setup-ssl.sh <domain> [email]
#
# Prerequisites:
# - Domain pointing to this server
# - Ports 80/443 accessible
# - Docker and Docker Compose installed

set -e

DOMAIN="${1:-}"
EMAIL="${2:-admin@$DOMAIN}"
CERT_DIR="./certs"
NGINX_CONF="./nginx-ssl.conf"

if [ -z "$DOMAIN" ]; then
    echo "Usage: ./setup-ssl.sh <domain> [email]"
    echo "Example: ./setup-ssl.sh app.gateplatform.com admin@gateplatform.com"
    exit 1
fi

echo "========================================"
echo "GATE Platform SSL Setup"
echo "========================================"
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Check if certbot is available
if ! command -v certbot &> /dev/null; then
    echo "Installing certbot..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y certbot
    elif command -v brew &> /dev/null; then
        brew install certbot
    else
        echo "Please install certbot manually:"
        echo "  https://certbot.eff.org/instructions"
        exit 1
    fi
fi

# Create certificate directory
mkdir -p "$CERT_DIR"

# Stop any running containers using port 80/443
echo "Stopping containers to free ports 80/443..."
docker compose down 2>/dev/null || true

# Get certificate using standalone mode
echo ""
echo "Obtaining SSL certificate from Let's Encrypt..."
echo "Note: This requires ports 80 and 443 to be accessible from the internet."
echo ""

sudo certbot certonly \
    --standalone \
    -d "$DOMAIN" \
    --email "$EMAIL" \
    --agree-tos \
    --non-interactive

# Copy certificates to local directory
echo "Copying certificates..."
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$CERT_DIR/"
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem "$CERT_DIR/"
sudo chown -R $(whoami):$(whoami) "$CERT_DIR/"
chmod 600 "$CERT_DIR/privkey.pem"
chmod 644 "$CERT_DIR/fullchain.pem"

# Generate Nginx SSL configuration
echo "Generating Nginx SSL configuration..."
cat > "$NGINX_CONF" << EOF
# Nginx SSL Configuration for GATE Platform
# Domain: $DOMAIN
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name $DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://\$host\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    # SSL certificates
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    
    # SSL configuration (Mozilla Intermediate)
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    
    # HSTS (1 year)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Security headers
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Root location - serve frontend
    location / {
        proxy_pass http://frontend:80;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://api:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Rate limit headers
        proxy_set_header X-RateLimit-Limit \$upstream_http_x_ratelimit_limit;
        proxy_set_header X-RateLimit-Remaining \$upstream_http_x_ratelimit_remaining;
        proxy_set_header X-RateLimit-Tier \$upstream_http_x_ratelimit_tier;
        
        # Timeouts for long-running operations
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
        
        # File upload size
        client_max_body_size 100M;
    }
    
    # WebSocket support for real-time updates
    location /ws/ {
        proxy_pass http://api:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
    
    # Health check
    location /health {
        proxy_pass http://api:8000/health;
        access_log off;
    }
}
EOF

# Create docker-compose override for SSL
cat > docker-compose.ssl.yml << EOF
# Docker Compose SSL Override
# Use with: docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d

version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: \${CUSTOMER_ID:-gate}_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
      - ./certbot-webroot:/var/www/certbot:ro
    depends_on:
      - api
      - frontend
    restart: unless-stopped
    networks:
      - default

  # Remove port mapping from frontend (nginx handles it)
  frontend:
    ports: []

networks:
  default:
    name: \${CUSTOMER_ID:-gate}_network
EOF

# Create renewal script
cat > renew-ssl.sh << 'EOF'
#!/bin/bash
# SSL Certificate Renewal Script
# Run this monthly via cron: 0 0 1 * * /path/to/renew-ssl.sh

set -e

DOMAIN="${1:-}"
CERT_DIR="./certs"

if [ -z "$DOMAIN" ]; then
    echo "Usage: ./renew-ssl.sh <domain>"
    exit 1
fi

# Renew certificate
sudo certbot renew --quiet

# Copy updated certificates
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$CERT_DIR/"
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem "$CERT_DIR/"
sudo chown -R $(whoami):$(whoami) "$CERT_DIR/"

# Reload nginx
docker compose exec nginx nginx -s reload

echo "SSL certificate renewed successfully"
EOF

chmod +x renew-ssl.sh

echo ""
echo "========================================"
echo "SSL Setup Complete!"
echo "========================================"
echo ""
echo "Files created:"
echo "  - $CERT_DIR/fullchain.pem (certificate chain)"
echo "  - $CERT_DIR/privkey.pem (private key)"
echo "  - $NGINX_CONF (Nginx configuration)"
echo "  - docker-compose.ssl.yml (Docker override)"
echo "  - renew-ssl.sh (certificate renewal script)"
echo ""
echo "To start with SSL:"
echo "  docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d"
echo ""
echo "To renew certificates (monthly):"
echo "  ./renew-ssl.sh $DOMAIN"
echo ""
echo "Add to crontab for automatic renewal:"
echo "  0 0 1 * * cd $(pwd) && ./renew-ssl.sh $DOMAIN >> /var/log/ssl-renewal.log 2>&1"
echo ""
