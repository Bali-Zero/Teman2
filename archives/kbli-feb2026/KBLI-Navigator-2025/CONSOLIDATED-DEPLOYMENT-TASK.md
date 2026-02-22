# 🚀 CONSOLIDATED DEPLOYMENT TASK - For Claude Code

**Task**: Deploy complete KBLI Navigator 2025 integration to balizero.com
**Date**: 2026-02-16
**Status**: Ready for atomic deployment

---

## 📦 WHAT YOU HAVE

You (Claude Code) have already completed:

- ✅ Homepage modifications (`app/page.tsx` or equivalent)
- ✅ Featured Collection → KBLI Navigator section
- ✅ Latest Insights → 3 KBLI articles
- ✅ Watch & Listen → KBLI podcast

---

## 📁 WHAT NEEDS TO BE DEPLOYED

### From `/deployment-package/`:

1. **KBLI Navigator App**:
   - `index.html` (780KB) → Deploy to `/kbli-navigator/`

2. **Homepage Images** (5 files):
   - `kbli-2025-hero-cover.png` (95KB)
   - `article-1-kbli-changes.png` (24KB)
   - `article-2-risk-levels.png` (25KB)
   - `article-3-finding-code.png` (24KB)
   - `podcast-kbli-2025.png` (124KB)
   - → Deploy all to `/public/images/`

3. **Homepage Changes**:
   - Your modifications to homepage component
   - → Git commit and push

---

## 🎯 DEPLOYMENT STEPS

### Step 1: Verify Files Exist

```bash
# Check deployment package
ls -lh /sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/deployment-package/

# Should show:
# - index.html (780KB)
# - 5 PNG files (~292KB total)
```

### Step 2: Deploy to balizero.com

**Option A: If you have server access via SCP**

```bash
# Navigate to deployment package
cd /sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/deployment-package

# Upload KBLI Navigator app
scp index.html user@balizero.com:/var/www/balizero.com/kbli-navigator/

# Upload all images
scp *.png user@balizero.com:/var/www/balizero.com/public/images/

# Set correct permissions
ssh user@balizero.com "chmod 644 /var/www/balizero.com/kbli-navigator/index.html"
ssh user@balizero.com "chmod 644 /var/www/balizero.com/public/images/*.png"
```

**Option B: If using Vercel/Netlify**

```bash
# Assuming balizero.com repo is available
cd /path/to/balizero-repo

# Copy KBLI Navigator to public directory
mkdir -p public/kbli-navigator
cp /sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/deployment-package/index.html public/kbli-navigator/

# Copy images
cp /sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/deployment-package/*.png public/images/

# Deploy via Vercel
vercel --prod

# Or via Netlify
netlify deploy --prod
```

**Option C: If using cPanel/FTP**

```bash
# Instructions for manual upload:
1. Login to cPanel/hosting panel
2. Navigate to File Manager
3. Go to public_html directory
4. Create folder: kbli-navigator
5. Upload index.html to kbli-navigator/
6. Go to public_html/images directory
7. Upload all 5 PNG files
8. Set permissions: 644 for all files
```

### Step 3: Git Commit Homepage Changes

```bash
# Add modified files
git add app/page.tsx
git add public/images/kbli-2025-hero-cover.png
git add public/images/article-1-kbli-changes.png
git add public/images/article-2-risk-levels.png
git add public/images/article-3-finding-code.png
git add public/images/podcast-kbli-2025.png

# Commit with detailed message
git commit -m "feat: integrate KBLI 2025 Navigator into homepage

## Changes

### Homepage Integration
- Replace Featured Collection with KBLI 2025 Navigator hero
- Update Latest Insights with 3 KBLI-focused articles:
  1. KBLI 2025: What Changed for Foreign Investors
  2. High-Risk vs Low-Risk Business Codes Explained
  3. Finding Your Perfect KBLI Code in 30 Seconds
- Replace podcast with KBLI 2025 Deep Dive

### Assets
- Add kbli-2025-hero-cover.png (1200x600px)
- Add article-1-kbli-changes.png (800x450px)
- Add article-2-risk-levels.png (800x450px)
- Add article-3-finding-code.png (800x450px)
- Add podcast-kbli-2025.png (800x800px)

### KBLI Navigator App
- Deploy standalone app at /kbli-navigator
- 1,562 KBLI 2025 codes with search
- 4-level risk assessment
- PMA status tracking
- Bilingual interface (EN/ID)
- Mobile responsive

## Impact
All homepage sections now link to /kbli-navigator, creating
multiple entry points for users to access the KBLI tool.

## Testing
- ✅ 47 tests run (95.7% pass rate)
- ✅ 1,562 codes verified (100% accurate)
- ✅ Mobile responsive confirmed
- ✅ Performance optimized (0.58ms search)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to production
git push origin main
```

### Step 4: Verify Deployment

```bash
# Test homepage
curl -I https://balizero.com/
# Should return 200 OK

# Test KBLI Navigator
curl -I https://balizero.com/kbli-navigator/
# Should return 200 OK

# Test image
curl -I https://balizero.com/images/kbli-2025-hero-cover.png
# Should return 200 OK
```

---

## ✅ POST-DEPLOYMENT CHECKLIST

### 1. Homepage Verification

Visit: `https://balizero.com/`

**Check**:

- [ ] Featured Collection shows "KBLI 2025 Navigator" with puzzle hero image
- [ ] "Explore Navigator →" button present and clickable
- [ ] 3 articles visible with correct covers:
  - [ ] Article 1: "KBLI 2025: What Changed" (Business badge)
  - [ ] Article 2: "High-Risk vs Low-Risk" (Immigration badge)
  - [ ] Article 3: "Finding Your Code" (Business badge)
- [ ] Podcast section shows "KBLI 2025 Deep Dive" with microphone cover
- [ ] All images load correctly (no broken images)
- [ ] All sections link to `/kbli-navigator`
- [ ] Mobile responsive (test on phone)
- [ ] No console errors (press F12)

### 2. KBLI Navigator Verification

Visit: `https://balizero.com/kbli-navigator/`

**Check**:

- [ ] Page loads successfully (< 3 seconds)
- [ ] Header shows "KBLI 2025 Navigator Pro" with Bali Zero logo
- [ ] Search bar visible and functional
- [ ] Try search: "restaurant" → should find code 56101
- [ ] Try search: "software" → should find code 62191
- [ ] Try search: "56101" → should find exact match
- [ ] Filters work (Risk: L/ML/MH/H, PMA: Open/Restricted/Closed)
- [ ] Language toggle works (EN/ID)
- [ ] Mobile responsive
- [ ] No console errors

### 3. User Flow Test

**Complete Journey**:

1. [ ] Start at `https://balizero.com/`
2. [ ] Click "Explore Navigator →" from Featured Collection
3. [ ] Verify arrives at `/kbli-navigator/`
4. [ ] Perform a search
5. [ ] Go back to homepage
6. [ ] Click article 1
7. [ ] Verify arrives at `/kbli-navigator/`
8. [ ] Go back, click podcast
9. [ ] Verify arrives at `/kbli-navigator/`

**Result**: All paths should lead to working KBLI Navigator ✅

### 4. Performance Test

**Metrics**:

- [ ] Homepage load: < 2 seconds
- [ ] KBLI Navigator load: < 3 seconds
- [ ] Search response: < 1 second
- [ ] Images load progressively (no delays)
- [ ] No layout shift (CLS < 0.1)

### 5. Mobile Test

**Devices to test**:

- [ ] iPhone (Safari)
- [ ] Android (Chrome)
- [ ] Tablet (iPad)

**Verify**:

- [ ] Layout adapts correctly
- [ ] Touch targets large enough
- [ ] Text readable without zoom
- [ ] Images scale properly

---

## 🐛 TROUBLESHOOTING

### Issue: Images don't load

**Check**:

```bash
# Verify images uploaded
ssh user@balizero.com "ls -lh /var/www/balizero.com/public/images/*.png"

# Check permissions
ssh user@balizero.com "ls -l /var/www/balizero.com/public/images/*.png"
# Should show: -rw-r--r-- (644)
```

**Fix**:

```bash
# Set correct permissions
ssh user@balizero.com "chmod 644 /var/www/balizero.com/public/images/*.png"
```

### Issue: KBLI Navigator shows 404

**Check**:

```bash
# Verify index.html exists
ssh user@balizero.com "ls -lh /var/www/balizero.com/kbli-navigator/index.html"
```

**Fix**:

```bash
# Re-upload if missing
scp deployment-package/index.html user@balizero.com:/var/www/balizero.com/kbli-navigator/
```

### Issue: Search doesn't work

**Check**:

- Open browser console (F12)
- Look for JavaScript errors
- Verify no CSP (Content Security Policy) blocking inline scripts

**Fix**:

- If CSP error, adjust server headers to allow inline scripts
- KBLI Navigator uses inline JS by design (self-contained)

### Issue: Homepage changes not visible

**Check**:

```bash
# Verify git push succeeded
git log -1
# Should show your commit

# Check if Next.js redeployed
# (varies by hosting platform)
```

**Fix**:

```bash
# If using Vercel/Netlify, trigger rebuild
vercel --prod --force
# or
netlify deploy --prod --force

# Clear browser cache
# Ctrl+Shift+R (or Cmd+Shift+R on Mac)
```

---

## 📊 SUCCESS METRICS

### Day 1 Goals:

- [ ] 0 deployment errors
- [ ] All links functional
- [ ] 50+ unique visitors to /kbli-navigator
- [ ] 200+ searches performed
- [ ] < 10% bounce rate

### Week 1 Goals:

- [ ] 500+ unique visitors
- [ ] 2,000+ searches
- [ ] 5+ min average session
- [ ] User feedback collected

---

## 📞 SUPPORT RESOURCES

**Documentation**:

- `FINAL-STATUS-REPORT.md` - Complete project status
- `DEPLOY-NOW.md` - Detailed deployment options
- `TESTING-SUMMARY.md` - Test results (95.7% pass rate)
- `OPTIMIZATION-RECOMMENDATIONS.md` - Future improvements

**Quick Reference**:

- Deployment package location: `/deployment-package/`
- Total files to deploy: 6 (1 HTML + 5 PNG)
- Total size: ~1.1 MB
- Target URLs:
  - Homepage: `https://balizero.com/`
  - App: `https://balizero.com/kbli-navigator/`

---

## 🎯 FINAL COMMAND SUMMARY

**All-in-one deployment** (if you have server access):

```bash
#!/bin/bash
# Quick deploy script

# Set variables
PKG="/sessions/practical-inspiring-galileo/mnt/Desktop/KBLI-Navigator-2025/deployment-package"
SERVER="user@balizero.com"
WEBROOT="/var/www/balizero.com"

# Deploy KBLI Navigator
echo "Deploying KBLI Navigator..."
scp $PKG/index.html $SERVER:$WEBROOT/kbli-navigator/

# Deploy images
echo "Deploying images..."
scp $PKG/*.png $SERVER:$WEBROOT/public/images/

# Set permissions
echo "Setting permissions..."
ssh $SERVER "chmod 644 $WEBROOT/kbli-navigator/index.html"
ssh $SERVER "chmod 644 $WEBROOT/public/images/kbli*.png"
ssh $SERVER "chmod 644 $WEBROOT/public/images/article*.png"
ssh $SERVER "chmod 644 $WEBROOT/public/images/podcast*.png"

# Git commit
echo "Committing homepage changes..."
git add app/page.tsx public/images/*.png
git commit -m "feat: integrate KBLI 2025 Navigator

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
git push origin main

# Verify
echo "Verifying deployment..."
curl -I https://balizero.com/
curl -I https://balizero.com/kbli-navigator/

echo "✅ Deployment complete!"
echo "Please verify at: https://balizero.com/"
```

---

## 🎉 YOU'RE READY!

**Status**: Everything is prepared
**Action**: Execute deployment steps above
**Result**: Complete KBLI Navigator integration live on balizero.com

**Good luck!** 🚀

---

**Task prepared by**: Claude Sonnet 4.5  
**Date**: 2026-02-16  
**For**: Claude Code deployment
