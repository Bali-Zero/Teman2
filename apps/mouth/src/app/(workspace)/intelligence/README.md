# Intelligence Center

**Enterprise-grade content management and analytics system for Indonesian immigration intelligence.**

---

## 🎯 Overview

The Intelligence Center provides a comprehensive platform for managing automated content discovery, curation, and publishing. It consists of 4 main sections:

1. **Visa Oracle** - Review and approve/reject visa regulation updates
2. **News Room** - Curate and publish immigration news articles
3. **Analytics** - Historical trends and performance metrics
4. **System Pulse** - Real-time system health monitoring

---

## ✨ Features

### 🔍 Filters & Sorting
- **Real-time Search**: Filter by title, ID, or source
- **Type Filters**: All, NEW, UPDATED, Critical (News)
- **Sort Options**: Date (newest/oldest), Title (A-Z/Z-A)

### 📊 Analytics Dashboard
- **Summary Cards**: Total Processed, Approval Rate, Rejection Rate, Published
- **Daily Trends**: Visual chart showing daily activity
- **Type Breakdown**: Separate statistics for Visa and News
- **Period Selector**: 7, 30, 90, 180 days

### ⚡ Bulk Operations
- **Multi-select**: Checkbox selection for multiple items
- **Bulk Approve/Reject**: Process multiple items at once
- **Bulk Publish**: Publish multiple news articles
- **Select All/Deselect All**: Quick selection management

### 📈 Prometheus Metrics
- **Bulk Operations**: Tracking and distribution
- **Filter/Sort Usage**: User behavior analytics
- **Search Queries**: Query pattern tracking
- **User Actions**: Complete action tracking
- **Analytics Queries**: Dashboard usage metrics

---

## 🚀 Quick Start

### Access
- **URL**: `https://zantara.balizero.com/intelligence`
- **Default**: Redirects to `/intelligence/visa-oracle`

### Navigation
- Use tabs at the top to switch between sections
- Each section has its own filters and actions
- Analytics provides historical insights

---

## 📖 Documentation

- [Refactoring Summary](./INTELLIGENCE_REFACTOR_SUMMARY.md) - Initial refactoring
- [Advanced Features](./ADVANCED_FEATURES_SUMMARY.md) - Feature implementation details
- [Testing Summary](./TESTING_SUMMARY.md) - Test coverage and patterns
- [Final Implementation](./FINAL_IMPLEMENTATION_SUMMARY.md) - Complete implementation summary

---

## 🧪 Testing

```bash
# Run all intelligence tests
cd apps/mouth && npm test -- intelligence --run

# Run specific test file
npm test -- analytics/page.test.tsx --run
```

**Test Coverage:** 117+ tests covering all features

---

## 📊 Monitoring

### Grafana Dashboard
- **Location**: `config/grafana/dashboards/intelligence-center-dashboard.json`
- **Access**: `http://localhost:3001` (Grafana UI)
- **Auto-loaded**: Via Grafana provisioning

### Prometheus Metrics
- **Endpoint**: `http://localhost:9090/metrics`
- **Prefix**: `zantara_intel_*`

### Key Metrics
- `zantara_intel_staging_queue_size` - Pending items
- `zantara_intel_bulk_operations_total` - Bulk operations count
- `zantara_intel_user_actions_total` - User action tracking
- `zantara_intel_analytics_queries_total` - Analytics usage

---

## 🛠️ Development

### File Structure
```
intelligence/
├── layout.tsx              # Main layout with tabs
├── page.tsx                # Redirect to visa-oracle
├── visa-oracle/
│   └── page.tsx           # Visa staging review
├── news-room/
│   └── page.tsx           # News curation
├── analytics/
│   └── page.tsx           # Analytics dashboard
└── system-pulse/
    └── page.tsx           # System metrics
```

### API Client
```typescript
import { intelligenceApi } from '@/lib/api/intelligence.api';

// Get pending items
const items = await intelligenceApi.getPendingItems('visa');

// Get analytics
const analytics = await intelligenceApi.getAnalytics(30);

// Bulk approve
await intelligenceApi.approveItem('visa', 'item-id');
```

---

## 📝 Best Practices

1. **Always use `intelligenceApi`** - Don't use direct fetch
2. **Log all actions** - Use `logger` for tracking
3. **Handle errors gracefully** - Show user-friendly messages
4. **Test new features** - Add tests for all functionality
5. **Update metrics** - Track new user actions

---

## 🔧 Troubleshooting

### Items not showing
- Check filters are not too restrictive
- Verify backend staging directory exists
- Check browser console for errors

### Bulk operations failing
- Verify items are selected
- Check backend logs for errors
- Ensure sufficient permissions

### Analytics not loading
- Verify backend archived directories exist
- Check period selector value
- Review backend logs

---

## 📚 Related Documentation

- [AI Onboarding](../../../../docs/AI_ONBOARDING.md)
- [System Map 4D](../../../../docs/SYSTEM_MAP_4D.md)
- [Living Architecture](../../../../docs/LIVING_ARCHITECTURE.md)

---

**Last Updated:** 2026-01-09  
**Version:** v2.0 (Advanced Features)
