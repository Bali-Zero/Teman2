# 🎯 New CRM Features - Team Training Guide

## What's New?

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   👨‍👩‍👧‍👦  FAMILY MEMBERS    📄  DOCUMENTS    ⚠️  EXPIRY ALERTS   │
│                                                                 │
│   Track spouse &        Organize by         Never miss a       │
│   children visas        category            renewal again!     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1️⃣ Family Members

### Why?
Most clients have **spouse + children** who also need visas processed.
Now we track them ALL in one place!

### What to Enter

```
┌──────────────────────────────────────────────────────────────┐
│  👤 Family Member Card                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Full Name:        Sarah Johnson (Wife)                      │
│  Relationship:     [ Spouse ▼ ]                              │
│                                                              │
│  📘 Passport                                                 │
│  ├─ Number:        US123456789                               │
│  ├─ Nationality:   USA                                       │
│  └─ Expiry:        2026-08-15  🟡 < 12 months                │
│                                                              │
│  📋 Current Visa                                             │
│  ├─ Type:          E28A (Investor KITAS)                     │
│  └─ Expiry:        2025-03-20  🔴 < 8 months                 │
│                                                              │
│  📞 Contact                                                  │
│  ├─ Email:         sarah@email.com                           │
│  └─ Phone:         +1 555-1234                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Relationship Options
| Code | Use For |
|------|---------|
| `spouse` | Husband / Wife |
| `child` | Son / Daughter |
| `parent` | Mother / Father |
| `sibling` | Brother / Sister |
| `other` | Business partner, assistant, etc. |

---

## 2️⃣ Document Categories

### Why?
Clients send us MANY documents. Now they're organized!

### Categories

```
📁 IMMIGRATION                    📁 PT PMA (Company)
├── 📘 Passport                   ├── 📄 NIB
├── 📋 KITAS                      ├── 📄 Akta Pendirian
├── 📋 KITAP                      ├── 📄 SK Kemenkumham
├── 📋 Visa Kunjungan             ├── 📄 NPWP Perusahaan
├── 📋 VOA                        ├── 📄 Surat Domisili
├── 📋 RPTKA                      └── 📄 OSS Certificate
├── 📋 IMTA
├── 📋 MERP                       📁 TAX
└── 📄 Sponsor Letter             ├── 📄 NPWP (Personal)
                                  ├── 📄 EFIN
📁 PERSONAL                       ├── 📄 SPT Tahunan
├── 📷 Photo                      ├── 📄 LKPM
├── 📄 CV/Resume                  ├── 📄 BPJS TK
├── 📜 Diploma                    └── 📄 BPJS Kesehatan
├── 📜 Marriage Certificate
├── 📜 Birth Certificate          📁 OTHER
└── 📄 Police Clearance           ├── 📄 Contract
                                  ├── 📄 Invoice
                                  └── 📄 Receipt
```

---

## 3️⃣ Expiry Alerts - Color System

### The Traffic Light System

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   🔴 RED        Expires in < 8 months     → ACTION NOW!        │
│                                                                 │
│   🟡 YELLOW     Expires in < 12 months    → Start planning     │
│                                                                 │
│   🟢 GREEN      Expires in > 12 months    → All good           │
│                                                                 │
│   ⚫ EXPIRED    Already expired!          → URGENT!            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### What Gets Tracked?

| Document | Alert Threshold |
|----------|-----------------|
| Passport | 8 months (red), 12 months (yellow) |
| KITAS | 8 months (red), 12 months (yellow) |
| KITAP | 8 months (red), 12 months (yellow) |
| Family Passports | Same as above |
| Family Visas | Same as above |

---

## 4️⃣ Google Drive Integration

### Each Client = 1 Folder

```
📁 Google Drive (30 TB)
└── 📁 Clients
    ├── 📁 John Smith (ID: 123)
    │   ├── 📁 Immigration
    │   │   ├── passport_scan.pdf
    │   │   └── kitas_2024.pdf
    │   ├── 📁 PT PMA
    │   │   ├── nib.pdf
    │   │   └── akta_pendirian.pdf
    │   └── 📁 Family
    │       ├── wife_passport.pdf
    │       └── child_birth_cert.pdf
    │
    └── 📁 Jane Doe (ID: 456)
        └── ...
```

### How to Link

1. Create folder in Google Drive
2. Copy folder ID from URL: `drive.google.com/drive/folders/[THIS_PART]`
3. Paste in client profile

---

## 5️⃣ Daily Workflow

### Morning Checklist

```
┌─────────────────────────────────────────────────────────────────┐
│  ☀️  MORNING ROUTINE (5 minutes)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Open Dashboard → Check Expiry Alerts                        │
│                                                                 │
│  2. 🔴 RED alerts = Contact client TODAY                        │
│     "Hi [Name], your [document] expires in [X] months.          │
│      We should start the renewal process now."                  │
│                                                                 │
│  3. 🟡 YELLOW alerts = Add to next week's follow-up             │
│                                                                 │
│  4. New client? → Add family members + upload documents         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### When Adding New Client

```
Step 1: Basic Info          Step 2: Family              Step 3: Documents
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│ Name             │        │ + Add Spouse     │        │ Upload Passport  │
│ Email            │   →    │ + Add Child 1    │   →    │ Upload KITAS     │
│ Phone            │        │ + Add Child 2    │        │ Set expiry dates │
│ Nationality      │        │ Enter passports  │        │ Link Drive folder│
└──────────────────┘        └──────────────────┘        └──────────────────┘
```

---

## 6️⃣ Quick Reference

### Keyboard Shortcuts (coming soon)
| Key | Action |
|-----|--------|
| `N` | New client |
| `F` | Add family member |
| `D` | Upload document |
| `E` | Edit current |

### Common Questions

**Q: Client has 2 wives (polygamy)?**
A: Add both as "spouse" - system supports multiple

**Q: Document has no expiry?**
A: Leave expiry blank (e.g., birth certificate, diploma)

**Q: Which category for work contract?**
A: Use "other" → "Contract"

**Q: Family member doesn't need visa?**
A: Still add them, leave visa fields empty

---

## 7️⃣ Portal Preview

### What Clients See (Read-Only)

```
┌─────────────────────────────────────────────────────────────────┐
│  🌴 Bali Zero Client Portal                    Welcome, John!   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📊 Your Status                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ KITAS       │  │ Passport    │  │ Company NIB │             │
│  │ Expires:    │  │ Expires:    │  │ Status:     │             │
│  │ 2025-06-15  │  │ 2027-01-20  │  │ ✅ Active   │             │
│  │ 🟡 5 months │  │ 🟢 OK       │  │             │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  👨‍👩‍👧 Family Members                                              │
│  ├── Sarah (Wife)     KITAS expires 2025-03-20 🔴              │
│  └── Emma (Daughter)  KITAS expires 2025-06-15 🟡              │
│                                                                 │
│  📄 Documents (12 files)                      [View All →]     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Remember:** What you enter in the Workspace → automatically appears in Client Portal!

---

## 8️⃣ Need Help?

### Contact

| Who | For What |
|-----|----------|
| Antonello | Technical issues, bugs |
| Adit | Process questions |
| Zantara (chat) | Quick answers about visas/PT PMA |

### Report a Bug

```
1. Screenshot the issue
2. Send to #tech-support channel
3. Include: What you were doing + What happened
```

---

## ✅ Summary

| Feature | What You Do |
|---------|-------------|
| **Family** | Add spouse + children with passport/visa info |
| **Documents** | Upload + categorize (immigration/PMA/tax/personal) |
| **Expiry** | System auto-alerts you (🔴🟡🟢) |
| **Google Drive** | Link folder ID to client profile |
| **Portal** | Data flows automatically to client view |

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   "Better data in = Better service out = Happy clients! 🎉"    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

*Last updated: January 2026*
*Version: 1.0*
