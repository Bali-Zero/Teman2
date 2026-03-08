# Notification System - Setup Guide

Complete setup guide for the Bali Zero automated email notification system.

## Prerequisites

1. **SendGrid Account**
   - Sign up at https://sendgrid.com
   - Verify your account
   - Create an API Key with "Mail Send" permissions
   - (Optional) Authenticate your domain for better deliverability

2. **Fly.io CLI**
   - Already configured for this project

3. **Database Access**
   - PostgreSQL running on Fly.io
   - Connection string available

## Quick Setup (Automated)

```bash
cd apps/backend-rag

# Run the complete setup script (requires SendGrid API key)
./scripts/configure_production.sh SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

This script will:

1. ✅ Configure SendGrid secrets on Fly.io
2. ✅ Run database migrations
3. ✅ Verify the configuration

## Manual Setup (Step by Step)

### Step 1: Configure SendGrid API Key

**Option A: Using the setup script**

```bash
./scripts/setup_sendgrid.sh SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Option B: Manual configuration**

```bash
flyctl secrets set SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx -a backend-rag
flyctl secrets set EMAIL_PROVIDER=sendgrid -a backend-rag
```

**Verify configuration:**

```bash
python scripts/verify_sendgrid.py your-email@example.com
```

### Step 2: Run Database Migration

**Connect to database:**

```bash
flyctl postgres connect -a nuzantara-db
```

**Execute migration SQL:**

```sql
\i backend/app/modules/notifications/migrations/001_create_notification_tables.sql
```

**Or run directly:**

```bash
flyctl postgres connect -a nuzantara-db < backend/app/modules/notifications/migrations/001_create_notification_tables.sql
```

**Verify tables created:**

```sql
\dt notification_*
SELECT COUNT(*) FROM notification_settings;
```

### Step 3: Test with Real Client Data

**A. List testable clients:**

```bash
curl https://backend-rag.fly.dev/api/notifications/test/clients \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**B. Test without sending email (dry run):**

```bash
curl -X POST https://backend-rag.fly.dev/api/notifications/test/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 123,
    "alert_type": "birthday"
  }'
```

**C. Test with actual email sending:**

```bash
curl -X POST https://backend-rag.fly.dev/api/notifications/test/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": 123,
    "alert_type": "birthday",
    "force_send": true,
    "test_email": "your-email@example.com"
  }'
```

**Available alert types for testing:**

- `passport_warning` - 13 months before expiry
- `passport_critical` - 9 months before expiry
- `passport_expired` - After expiry
- `visa_critical` - 2 months before expiry
- `birthday` - Birthday greeting

### Step 4: Access Admin Dashboard

**URL:** https://kita.balizero.com/notifications

**Features:**

- Real-time statistics (24h/7d/30d)
- Alert history with filtering
- Retry failed alerts
- Pause client notifications
- System status indicator

**Required permissions:** Admin role

## Verification Checklist

- [ ] SendGrid API key configured in Fly.io secrets
- [ ] Database tables created (`notification_alerts`, `notification_settings`, `notification_log`)
- [ ] Default settings created for existing clients
- [ ] Test email sent successfully
- [ ] Admin dashboard accessible
- [ ] Scheduler running (check logs)

## Troubleshooting

### SendGrid Issues

**Problem:** Emails not sending

```bash
# Check SendGrid configuration
flyctl secrets list -a backend-rag | grep SENDGRID

# Verify API key is valid
python scripts/verify_sendgrid.py
```

**Problem:** Emails going to spam

- Authenticate your domain in SendGrid
- Set up DKIM and SPF records
- Use a dedicated IP (paid SendGrid plan)

### Database Issues

**Problem:** Migration fails

```bash
# Check if tables already exist
flyctl postgres connect -a nuzantara-db -c "\dt notification_*"

# Check for errors
flyctl logs -a backend-rag | grep -i notification
```

### Scheduler Issues

**Problem:** Alerts not generating automatically

```bash
# Check scheduler is running
flyctl logs -a backend-rag | grep -i scheduler

# Trigger manual check
curl -X POST https://backend-rag.fly.dev/api/notifications/check \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Monitoring

### SendGrid Dashboard

https://app.sendgrid.com/email_activity

### Fly.io Logs

```bash
flyctl logs -a backend-rag
```

### Database Queries

**Check pending alerts:**

```sql
SELECT * FROM notification_alerts
WHERE status = 'pending'
ORDER BY created_at DESC;
```

**Check alert stats:**

```sql
SELECT
    alert_type,
    status,
    COUNT(*) as count
FROM notification_alerts
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY alert_type, status;
```

**Check failed alerts:**

```sql
SELECT * FROM notification_alerts
WHERE status = 'failed'
AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

## Security Considerations

1. **API Key Protection**
   - Never commit SendGrid API key to git
   - Use Fly.io secrets for production
   - Rotate keys regularly

2. **Rate Limiting**
   - Max 1 alert per day per client per type
   - BCC team leaders for critical alerts only
   - Audit log tracks all actions

3. **Access Control**
   - Test endpoints: Staging only
   - Admin dashboard: Admin role required
   - API endpoints: Authentication required

## Next Steps

1. **Monitor for 48 hours**
   - Check SendGrid activity
   - Review failed alerts
   - Verify delivery rates

2. **Customize templates** (if needed)
   - Edit `backend/app/modules/notifications/templates.py`
   - Add more languages
   - Update branding

3. **Set up monitoring alerts**
   - Failed alert threshold
   - Delivery rate drops
   - System errors

## Support

For issues or questions:

- Check logs: `flyctl logs -a backend-rag`
- Review SendGrid activity: https://app.sendgrid.com/email_activity
- Test endpoint: `POST /api/notifications/test/`
