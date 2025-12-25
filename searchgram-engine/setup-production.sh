#!/bin/bash
# SearchGram Engine - Production Setup Script

set -e  # Exit on error

echo "================================================"
echo "SearchGram Engine - Production Setup"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -eq 0 ]; then
   echo -e "${RED}ERROR: Do not run this script as root${NC}"
   exit 1
fi

# Step 1: Generate API Key
echo -e "${GREEN}[1/8] Generating API Key...${NC}"
if [ ! -f .env ]; then
    cp .env.example .env
    API_KEY=$(openssl rand -hex 32)
    ELASTIC_PASSWORD=$(openssl rand -base64 24)

    sed -i "s/your-strong-32-char-random-api-key-here/$API_KEY/" .env
    sed -i "s/your-strong-elasticsearch-password-here/$ELASTIC_PASSWORD/" .env

    echo -e "${GREEN}✓ Generated .env file with random keys${NC}"
else
    echo -e "${YELLOW}⚠ .env already exists, skipping...${NC}"
fi

# Step 2: Prompt for domain
echo -e "${GREEN}[2/8] Domain Configuration...${NC}"
read -p "Enter your domain name (e.g., searchgram-api.yourdomain.com): " DOMAIN_NAME
read -p "Enter your email for SSL certificates: " LETSENCRYPT_EMAIL

sed -i "s/searchgram-api.yourdomain.com/$DOMAIN_NAME/g" nginx.conf
sed -i "s/DOMAIN_NAME=.*/DOMAIN_NAME=$DOMAIN_NAME/" .env
sed -i "s/LETSENCRYPT_EMAIL=.*/LETSENCRYPT_EMAIL=$LETSENCRYPT_EMAIL/" .env

echo -e "${GREEN}✓ Domain configured: $DOMAIN_NAME${NC}"

# Step 3: Create directories
echo -e "${GREEN}[3/8] Creating directories...${NC}"
mkdir -p ssl logs/nginx certbot/www fail2ban

echo -e "${GREEN}✓ Directories created${NC}"

# Step 4: Firewall setup
echo -e "${GREEN}[4/8] Configuring firewall...${NC}"
read -p "Configure UFW firewall? (y/n): " SETUP_FIREWALL

if [ "$SETUP_FIREWALL" = "y" ]; then
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow 22/tcp comment 'SSH'
    sudo ufw allow 80/tcp comment 'HTTP'
    sudo ufw allow 443/tcp comment 'HTTPS'

    # Block direct access to port 8080
    sudo ufw deny 8080/tcp comment 'Block direct Go service access'

    sudo ufw --force enable
    echo -e "${GREEN}✓ Firewall configured${NC}"
else
    echo -e "${YELLOW}⚠ Skipped firewall setup${NC}"
fi

# Step 5: Docker check
echo -e "${GREEN}[5/8] Checking Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker is not installed${NC}"
    echo "Install Docker: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}ERROR: Docker Compose is not installed${NC}"
    echo "Install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"

# Step 6: SSL Certificate (Let's Encrypt)
echo -e "${GREEN}[6/8] SSL Certificate Setup...${NC}"
read -p "Obtain SSL certificate with Let's Encrypt? (y/n): " SETUP_SSL

if [ "$SETUP_SSL" = "y" ]; then
    echo "Starting Nginx to obtain certificate..."

    # Start Nginx temporarily for certbot
    docker-compose -f docker-compose.production.yml up -d nginx

    # Wait for Nginx to start
    sleep 5

    # Obtain certificate
    docker run --rm \
        -v $(pwd)/ssl:/etc/letsencrypt \
        -v $(pwd)/certbot/www:/var/www/certbot \
        -p 80:80 \
        certbot/certbot certonly \
        --standalone \
        --preferred-challenges http \
        --email $LETSENCRYPT_EMAIL \
        --agree-tos \
        --no-eff-email \
        -d $DOMAIN_NAME

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ SSL certificate obtained${NC}"

        # Link certificates
        ln -sf /etc/letsencrypt/live/$DOMAIN_NAME/fullchain.pem ssl/fullchain.pem
        ln -sf /etc/letsencrypt/live/$DOMAIN_NAME/privkey.pem ssl/privkey.pem
        ln -sf /etc/letsencrypt/live/$DOMAIN_NAME/chain.pem ssl/chain.pem
    else
        echo -e "${RED}ERROR: Failed to obtain SSL certificate${NC}"
        echo "Make sure:"
        echo "1. DNS is pointing to this server"
        echo "2. Port 80 is accessible from internet"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ Skipped SSL setup - you'll need to add certificates manually${NC}"
fi

# Step 7: Build and start services
echo -e "${GREEN}[7/8] Building and starting services...${NC}"
docker-compose -f docker-compose.production.yml build
docker-compose -f docker-compose.production.yml up -d

echo -e "${GREEN}✓ Services started${NC}"

# Step 8: Health check
echo -e "${GREEN}[8/8] Performing health check...${NC}"
sleep 10

# Check if services are running
if docker-compose -f docker-compose.production.yml ps | grep -q "Up"; then
    echo -e "${GREEN}✓ Services are running${NC}"
else
    echo -e "${RED}ERROR: Some services failed to start${NC}"
    docker-compose -f docker-compose.production.yml ps
    exit 1
fi

# Test health endpoint
if curl -f -k https://localhost/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${YELLOW}⚠ Health check failed (might need DNS propagation)${NC}"
fi

# Display summary
echo ""
echo "================================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "================================================"
echo ""
echo "Your SearchGram Engine is now running!"
echo ""
echo "Service URL: https://$DOMAIN_NAME"
echo "API Key: $(grep API_KEY .env | cut -d '=' -f2)"
echo ""
echo "Next steps:"
echo "1. Update your Python bot config.json:"
echo "   {\"search_engine\": {\"engine\": \"http\", \"http\": {\"base_url\": \"https://$DOMAIN_NAME\", \"api_key\": \"YOUR_API_KEY\"}}}"
echo ""
echo "2. Test the API:"
echo "   curl -H \"X-API-Key: YOUR_API_KEY\" https://$DOMAIN_NAME/api/v1/ping"
echo ""
echo "3. Monitor logs:"
echo "   docker-compose -f docker-compose.production.yml logs -f"
echo ""
echo "4. SSL certificate will auto-renew via certbot"
echo ""
echo -e "${YELLOW}IMPORTANT: Keep your .env file secure and never commit it to git!${NC}"
echo ""
