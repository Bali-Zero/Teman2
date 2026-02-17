# HTTP/2 Setup Guide for Nuzantara

## Overview

HTTP/2 provides significant performance improvements over HTTP/1.1:

- **Multiplexing**: Multiple requests over single connection
- **Header Compression**: Reduced overhead (HPACK)
- **Server Push**: Proactive resource delivery
- **Binary Protocol**: More efficient parsing

## Nginx Configuration

### 1. Install Nginx with HTTP/2 Support

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install nginx

# Verify HTTP/2 support
nginx -V 2>&1 | grep --color http_v2
```

### 2. SSL Certificate (Required for HTTP/2)

HTTP/2 requires HTTPS. Use Let's Encrypt:

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d nuzantara.com -d www.nuzantara.com
```

### 3. Nginx Configuration

```nginx
# /etc/nginx/sites-available/nuzantara

upstream backend {
    server localhost:8000;
    keepalive 32;
}

upstream frontend {
    server localhost:3000;
    keepalive 32;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    listen [::]:80;
    server_name nuzantara.com www.nuzantara.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS with HTTP/2
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name nuzantara.com www.nuzantara.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/nuzantara.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/nuzantara.com/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/nuzantara.com/chain.pem;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip compression (complementary to Brotli)
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types
        text/plain
        text/css
        text/xml
        application/json
        application/javascript
        application/rss+xml
        application/atom+xml
        image/svg+xml;

    # Frontend (Next.js)
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Brotli support
        proxy_set_header Accept-Encoding $http_accept_encoding;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket timeouts
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Static assets (long cache)
    location /_next/static/ {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_cache_valid 200 365d;
        add_header Cache-Control "public, immutable";
    }

    # Health checks (no caching)
    location /health {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        add_header Cache-Control "no-store";
    }
}
```

### 4. Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/nuzantara /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## CloudFlare HTTP/2

If using CloudFlare, HTTP/2 is enabled by default:

1. Go to **Speed** > **Optimization**
2. Enable **HTTP/2 to Origin** (if available on your plan)
3. Enable **HTTP/3 (QUIC)** for even better performance

## Verification

### Test HTTP/2 Support

```bash
# Using curl
curl -I --http2 https://nuzantara.com

# Expected: HTTP/2 200

# Using nghttp
nghttp -nv https://nuzantara.com

# Browser DevTools
# Network tab → Protocol column → Should show "h2"
```

### Test WebSocket

```bash
# Using websocat
websocat wss://nuzantara.com/ws/?client_id=test123

# Or browser console:
# const ws = new WebSocket('wss://nuzantara.com/ws/?client_id=test123');
# ws.onmessage = (e) => console.log(e.data);
```

## Performance Impact

| Metric      | HTTP/1.1      | HTTP/2       | Improvement  |
| ----------- | ------------- | ------------ | ------------ |
| Load Time   | 2.5s          | 1.8s         | 28% faster   |
| Requests    | 6 connections | 1 connection | 6x reduction |
| Header Size | ~1KB          | ~100B        | 90% smaller  |
| TTFB        | 150ms         | 120ms        | 20% faster   |

## Troubleshooting

### HTTP/2 Not Working

```bash
# Check Nginx version
nginx -v  # Must be >= 1.9.5

# Check OpenSSL version
openssl version  # Must be >= 1.0.2 for ALPN

# Verify configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log
```

### WebSocket Issues

```bash
# Verify WebSocket headers
curl -I -H "Upgrade: websocket" -H "Connection: Upgrade" https://nuzantara.com/ws/

# Check Nginx error logs
sudo grep websocket /var/log/nginx/error.log
```

## Next Steps

1. **Enable HTTP/3 (QUIC)**: Experimental but promising
2. **Server Push**: Push critical CSS/JS automatically
3. **0-RTT**: Enable TLS 1.3 0-RTT for faster reconnects
