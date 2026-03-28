# Notification Module

Automated email notification system for Bali Zero clients.

## Features

- **Passport Alerts**: 13-month warning, 9-month critical, expired
- **Visa Alerts**: 4-month warning, 2-month critical, expired
- **Birthday Greetings**: Automated birthday emails with Indonesian blessings
- **Multi-language**: Support for EN, IT, ID, RU, FR, DE, ES, ZH, JA
- **Rate Limiting**: Prevents duplicate alerts within configurable time windows
- **Team Notifications**: Critical alerts BCC team leader

## Architecture

```
notifications/
├── __init__.py          # Module exports
├── models.py            # Pydantic models
├── templates.py         # Multi-language email templates
├── checker.py           # Expiry checking logic
├── service.py           # Email sending service
├── router.py            # FastAPI endpoints
├── scheduler.py         # Cron job scheduler
├── migrations/          # Database migrations
└── README.md           # This file
```

## Configuration

Environment variables:

```bash
# Email Provider
EMAIL_PROVIDER=sendgrid  # or ses, smtp
SENDGRID_API_KEY=your_api_key

# Scheduling (optional)
NOTIFICATION_CHECK_HOUR=9      # Bali time
NOTIFICATION_CHECK_MINUTE=0
NOTIFICATION_TIMEZONE=Asia/Singapore

# Rate Limiting
MIN_DAYS_BETWEEN_ALERTS=1      # Max 1 alert per day per type
```

## API Endpoints

### POST /api/notifications/check

Run manual expiry check (requires auth)

```json
{
  "client_id": 123 // optional, check all if omitted
}
```

### GET /api/notifications/status

Get system status and pending alert count

### POST /api/notifications/send-pending

Send all pending alerts (admin only)

## Scheduled Jobs

| Job                      | Schedule          | Description                                          |
| ------------------------ | ----------------- | ---------------------------------------------------- |
| daily_notification_check | 9:00 AM Bali time | Generate alerts for expiring documents and birthdays |
| hourly_pending_send      | Every hour        | Send any pending alerts                              |

## Alert Thresholds

| Document | Warning              | Critical            | Expired  |
| -------- | -------------------- | ------------------- | -------- |
| Passport | 13 months            | 9 months            | < 0 days |
| Visa     | 4 months (~120 days) | 2 months (~60 days) | < 0 days |

## Database Schema

### notification_alerts

Stores generated alerts and their status

### notification_settings

Per-client notification preferences

### notification_log

Audit log of all notification activities

## Testing

```bash
# Run manual check
curl -X POST http://localhost:8000/api/notifications/check \
  -H "Authorization: Bearer $TOKEN"

# Check status
curl http://localhost:8000/api/notifications/status \
  -H "Authorization: Bearer $TOKEN"
```

## Deployment

### Fly.io (Current)

Scheduler runs in-process with main application.

### Kubernetes

Use CronJob for external scheduling:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: notification-check
spec:
  schedule: '0 9 * * *' # 9 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: notifier
              image: balizero-backend
              command: ['python', '-m', 'notifications.cli', 'check']
```

## Adding New Languages

1. Add templates to `templates.py` in `EMAIL_TEMPLATES` dict
2. Use ISO 639-1 language code as key
3. Include Indonesian blessing for birthday templates
4. Test with sample data

## Security

- All endpoints require authentication
- Admin endpoints check `is_admin` flag
- Email content is HTML-escaped
- BCC used for team notifications (protects privacy)
- Audit log tracks all actions

## Golden Rules Compliance

- ✅ No hardcoded secrets (use env vars)
- ✅ Structured logging throughout
- ✅ Type hints on all functions
- ✅ Database connection pooling
- ✅ Proper error handling
- ✅ Rate limiting to prevent spam
- ✅ Audit trail for compliance
