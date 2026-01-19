# Vertex AI Billing & Credits Verification

**CRITICAL:** Before relying on Vertex AI fallback, verify that your 16M IDR credit covers Vertex AI usage.

---

## 🔍 What is the 16M IDR Credit?

**16 Million IDR ≈ $1,000 USD**

This could be:

1. **Google Developer Program Credit**
   - Up to $1,000 for Vertex AI
   - Specific to AI Studio + Vertex AI only
   - Covers: Gemini 2.0+ models, Imagen, Veo
   - [Source: Google Developer Program](https://developers.google.com/profile/help/benefits)

2. **Google Cloud Free Trial**
   - $300 USD (~4.7M IDR) for 90 days
   - Covers ALL Google Cloud services
   - **Note:** Standard free trial is only $300, not $1,000

3. **Startup/Enterprise Credits**
   - Custom amount negotiated with Google
   - May have specific service restrictions

---

## ✅ How to Verify Your Credits Cover Vertex AI

### Step 1: Check Billing Account

```bash
# Login to Google Cloud Console
https://console.cloud.google.com/billing

# Select project "nuzantara"
# Go to: Billing → Overview → Credits & Promotions
```

### Step 2: What to Look For

**✅ GOOD - Credits cover Vertex AI:**

```
Credit Name: "Google Cloud Platform Credit"
             OR "Google Developer Program - AI Credit"
Applicable to: All Google Cloud services
               OR Vertex AI, AI Studio, Gemini models
Remaining: $XXX / $1,000
```

**❌ BAD - Credits DON'T cover Vertex AI:**

```
Credit Name: "AI Studio API Free Tier"
Applicable to: Google AI Studio only (API Key usage)
Note: Does NOT cover Vertex AI (separate billing)
```

### Step 3: Check Service Restrictions

In the Credits tab, look for **"Restrictions"** section:

- **"No restrictions"** = Credit applies to all GCP services ✅
- **"AI Studio only"** = Vertex AI will charge separately ❌
- **"Vertex AI and AI Studio"** = Both covered ✅

---

## 📊 Vertex AI vs AI Studio Billing

| Aspect                   | AI Studio API Key       | Vertex AI (Service Account)     |
| ------------------------ | ----------------------- | ------------------------------- |
| **Authentication**       | API Key (simple)        | Service Account (project-based) |
| **Billing Method**       | AI Studio quota/credits | GCP Billing Account             |
| **Credits Applicable**   | AI Studio credits only  | GCP credits (if eligible)       |
| **Pricing (Gemini 2.0)** | $0.075/1M input tokens  | $0.075/1M input tokens          |
| **Quota**                | 1,500 RPM               | 2,000 RPM (higher)              |

**Key Difference:**

- **AI Studio API Key** = Uses separate quota, may have separate credits
- **Vertex AI** = Uses GCP billing account, shares GCP-wide credits

---

## 🔍 Verify in Google Cloud Console

### Method 1: Check via Web Console

1. **Go to Billing:**

   ```
   https://console.cloud.google.com/billing?project=nuzantara
   ```

2. **Navigate to Credits:**
   - Click "Credits & Promotions" tab
   - Look for total credit amount (should show ~16M IDR or $1,000)

3. **Check Service Coverage:**
   - Click on the credit name
   - Read "Applicable Services" section
   - Verify "Vertex AI" is listed ✅

### Method 2: Check via gcloud CLI

```bash
# Authenticate with Service Account
gcloud auth activate-service-account \
  nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com \
  --key-file=/tmp/google_credentials.json

# Set project
gcloud config set project nuzantara

# Check billing account
gcloud billing projects describe nuzantara

# Check Vertex AI API status
gcloud services list --enabled | grep aiplatform

# Expected output:
# aiplatform.googleapis.com    Vertex AI API
```

### Method 3: Check Credit Balance via API

```bash
# Get billing account linked to project
BILLING_ACCOUNT=$(gcloud billing projects describe nuzantara \
  --format="value(billingAccountName)")

# View billing account details
gcloud billing accounts describe $BILLING_ACCOUNT
```

---

## 🚨 CRITICAL FINDINGS

Based on research, **Vertex AI CAN use Google Cloud credits** ✅

**Source:** [Vertex AI Billing Questions - Google Cloud](https://docs.cloud.google.com/vertex-ai/docs/support/billing-questions)

> "With express mode, you can still use any existing credits on your account."

**Google Developer Program Credits:**

> "This credit may only be used in Google AI Studio and Google Cloud Vertex AI.
> Specifically, for Google Cloud Vertex AI, the credit can only be applied to
> Google GenAI models including Gemini 2.0+ models."

**Source:** [Free Google Vertex AI credits (up to US$1,000)](https://university.tenten.co/t/free-google-vertex-ai-credits-up-to-us-1-000/2107)

---

## ⚠️ IMPORTANT: What Vertex AI Credits Cover

**✅ COVERED by Vertex AI Credits:**

- Gemini 2.0+ models (Flash, Pro)
- Imagen (image generation)
- Veo (video generation)
- Text embeddings (if using Vertex AI Embeddings API)

**❌ NOT COVERED:**

- Google Maps Platform
- Cloud Storage (separate charges)
- Compute Engine (if used)
- Support packages

---

## 🔧 How to Enable Vertex AI on Project "nuzantara"

### 1. Enable Vertex AI API

```bash
gcloud services enable aiplatform.googleapis.com --project=nuzantara
```

### 2. Verify Service Account Permissions

```bash
# Check current IAM roles
gcloud projects get-iam-policy nuzantara \
  --flatten="bindings[].members" \
  --filter="bindings.members:nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com"

# Required roles:
# - roles/aiplatform.user (Vertex AI User)
```

### 3. Grant Required Permissions (if missing)

```bash
# Grant Vertex AI User role
gcloud projects add-iam-policy-binding nuzantara \
  --member="serviceAccount:nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

---

## 📊 Cost Comparison: AI Studio vs Vertex AI

**Scenario:** 10M tokens input, 2M tokens output per month

| Method        | Cost Calculation                            | Total         |
| ------------- | ------------------------------------------- | ------------- |
| **AI Studio** | (10M × $0.075) + (2M × $0.30) = $750 + $600 | **$1,350/mo** |
| **Vertex AI** | (10M × $0.075) + (2M × $0.30) = $750 + $600 | **$1,350/mo** |

**Pricing is identical**, but:

- ✅ Vertex AI: Uses your 16M IDR credit (if applicable)
- ❌ AI Studio: May use separate quota/credit

---

## 🎯 RECOMMENDATION

**Based on your 16M IDR credit, here's what to do:**

### ✅ IF credit covers Vertex AI:

1. **Primary:** Use Vertex AI (save AI Studio quota)
2. **Fallback:** Use AI Studio API Key
3. **Last Resort:** OpenRouter

**Why?**

- Maximize use of 16M IDR credit
- Higher quota (2,000 RPM vs 1,500 RPM)
- Enterprise features (audit logs, VPC-SC)

### ❌ IF credit is AI Studio only:

1. **Primary:** Use AI Studio API Key (utilize credit)
2. **Fallback:** Vertex AI (paid, but higher quota)
3. **Last Resort:** OpenRouter

**Why?**

- Maximize free tier usage first
- Vertex AI as paid backup when quota exceeded

---

## 📝 Action Items - COMPLETATI ✅

- [x] 1. Login to Google Cloud Console
- [x] 2. Navigate to Billing → Credits & Promotions
- [x] 3. Check credit name and applicable services
- [x] 4. Verify "Vertex AI" is listed in covered services
- [x] 5. Enable Vertex AI API on project "nuzantara"
- [x] 6. Grant `roles/aiplatform.user` to Service Account
- [x] 7. Test Vertex AI with a simple request
- [x] 8. Backend deployed and operational (version 1668)

---

## ✅ Verifica Completata (2026-01-19)

**Risultati:**

| Item                    | Status | Details                                                 |
| ----------------------- | ------ | ------------------------------------------------------- |
| **Credito verificato**  | ✅     | 16.663.501 Rp (~$1,000 USD) al 100%                     |
| **Copertura Vertex AI** | ✅     | "Google GenAI models including Gemini 2.0+ models"      |
| **Service Account**     | ✅     | `nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com` |
| **Project ID**          | ✅     | `nuzantara`                                             |
| **API abilitata**       | ✅     | Vertex AI API attiva                                    |
| **Backend deployed**    | ✅     | Version 1668, 2/2 machines running                      |
| **Health check**        | ✅     | Passing                                                 |
| **Vertex AI PRIMARY**   | ✅     | Usa credito come primary (non fallback)                 |
| **Model attivo**        | ✅     | `gemini-3-flash-preview`                                |

**Durata stimata credito:**

- Con Gemini 3 Flash Preview: ~7 mesi
- Con Gemini 2.0 Flash: ~74 mesi (6 anni)

---

## 🔗 Sources

1. [Vertex AI Billing Questions - Google Cloud](https://docs.cloud.google.com/vertex-ai/docs/support/billing-questions)
2. [Google Developer Program Benefits FAQ](https://developers.google.com/profile/help/benefits)
3. [Free Google Vertex AI credits (up to US$1,000)](https://university.tenten.co/t/free-google-vertex-ai-credits-up-to-us-1-000/2107)
4. [Free Google Cloud features and trial offer](https://docs.cloud.google.com/free/docs/free-cloud-features)
5. [Vertex AI Pricing Review + Features](https://www.lindy.ai/blog/vertex-ai-pricing)

---

**Last Updated:** 2026-01-19
**Status:** ✅ Verifica completata e sistema operativo
**Deployment:** Version 1668 (commit a97bd0c8)
**Next Step:** Monitorare consumo credito nei prossimi giorni
