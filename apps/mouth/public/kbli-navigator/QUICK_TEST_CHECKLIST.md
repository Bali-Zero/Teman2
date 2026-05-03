# KBLI Navigator - Quick Test Checklist

**URL:** https://kita.balizero.com/kbli-navigator
**Date:** 2026-02-16
**Tester:** **\*\***\_\_\_\_**\*\***
**Browser:** **\*\***\_\_\_\_**\*\***

---

## ✅ Phase 2 Tests (Already Deployed)

### Test 1: Relevance Scoring

- [ ] Search: `software`
- [ ] ✅ Result #1 is Code 62013 (Software Development)
- [ ] ✅ Result #2 is Code 47403 (Retail Software)
- [ ] ✅ Console shows: `[KBLI Search Phase 2] ✓ ... Top score: 50`

**Notes:** **\*\***\*\***\*\***\_\_\_**\*\***\*\***\*\***

---

### Test 2: Fuzzy Search (Typo)

- [ ] Search: `resturant` (missing 'a')
- [ ] ✅ Yellow suggestion box appears
- [ ] ✅ Shows: "restoran", "restaurant" as clickable links
- [ ] ✅ Clicking "restoran" triggers new search
- [ ] ✅ Results appear for restaurants (Code 56101)

**Notes:** **\*\***\*\***\*\***\_\_\_**\*\***\*\***\*\***

---

### Test 3: No Results

- [ ] Search: `xyzabc123`
- [ ] ✅ Red error box appears
- [ ] ✅ Message: "No results found... Try using Indonesian terms..."
- [ ] ✅ No JavaScript errors in console

**Notes:** **\*\***\*\***\*\***\_\_\_**\*\***\*\***\*\***

---

## 🔄 Regression Tests

### Test 4: PMA Filter

- [ ] Click "Open" chip
- [ ] Search: `restaurant`
- [ ] ✅ Only Open codes shown
- [ ] ✅ Results are still relevant (scored)

**Notes:** **\*\***\*\***\*\***\_\_\_**\*\***\*\***\*\***

---

### Test 5: Risk Filter

- [ ] Click "Low Risk" chip
- [ ] Search: `software`
- [ ] ✅ Only Low Risk codes shown
- [ ] ✅ Relevance scoring still works

**Notes:** **\*\***\*\***\*\***\_\_\_**\*\***\*\***\*\***

---

### Test 6: Load More

- [ ] Search: `perdagangan` (common word)
- [ ] Scroll down
- [ ] Click "Load More" button
- [ ] ✅ Next 50 results load
- [ ] ✅ No duplicates
- [ ] ✅ Order maintained

**Notes:** **\*\***\*\***\*\***\_\_\_**\*\***\*\***\*\***

---

## 🚀 Performance Tests

### Test 7: Console Logs

- [ ] Open DevTools → Console tab
- [ ] Search: `restaurant`
- [ ] ✅ See: `[KBLI Search Phase 2] ✓ Query: "restaurant" | Results: X | Top score: Y | Time: Zms`
- [ ] ✅ Time is < 50ms

**Console output:**

```
_______________________________
```

---

### Test 8: Multiple Searches

- [ ] Search: `hotel`
- [ ] Wait 2 seconds
- [ ] Search: `restaurant`
- [ ] Wait 2 seconds
- [ ] Search: `software`
- [ ] ✅ Each search completes instantly
- [ ] ✅ No errors in console
- [ ] ✅ Results always correct

**Notes:** **\*\***\*\***\*\***\_\_\_**\*\***\*\***\*\***

---

## 📱 Mobile Tests (Optional)

### Test 9: Mobile Responsive

- [ ] Resize browser to 375px width (or use mobile device)
- [ ] Search: `restaurant`
- [ ] ✅ Suggestion box fits screen
- [ ] ✅ Cards stack vertically
- [ ] ✅ Touch interactions work

**Device:** **\*\***\*\***\*\***\_\_\_**\*\***\*\***\*\***

---

## 🎯 Summary

**Total Tests:** 9
**Passed:** **\_** / 9
**Failed:** **\_** / 9
**Pass Rate:** **\_** %

**Phase 2 Status:** ✅ / ❌ / ⚠️ (circle one)

---

## 🐛 Issues Found

| Test # | Issue Description | Severity | Screenshots |
| ------ | ----------------- | -------- | ----------- |
|        |                   |          |             |
|        |                   |          |             |
|        |                   |          |             |

**Severity Legend:**

- 🔴 Critical (breaks functionality)
- 🟡 Medium (affects UX)
- 🟢 Low (cosmetic)

---

## 📸 Screenshots

**Test 1 - Relevance Scoring:**

- Screenshot of "software" search results
- Show Code 62013 appears first

**Test 2 - Fuzzy Search:**

- Screenshot of "resturant" search
- Show yellow suggestion box

**Test 3 - Console Logs:**

- Screenshot of browser console
- Show Phase 2 logs with timing

---

## ✅ Sign-off

**Tested by:** **\*\***\_\_\_\_**\*\***
**Date:** **\*\***\_\_\_\_**\*\***
**Approved:** ☐ Yes ☐ No ☐ With Issues

**Reviewer Notes:**

---

---

---

---

**Next Step:** Complete Phase 1 integration for bilingual search!
