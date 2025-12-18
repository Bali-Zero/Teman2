# 🔐 Secrets Directory

**NEVER COMMIT THIS DIRECTORY**

This directory contains sensitive credentials and keys for the NUZANTARA platform.

## Contents

- `oracle_ssh_key.pem` - Oracle Cloud SSH private key
- `oracle_config` - Oracle Cloud CLI configuration
- `google_service_account.json` - Google Cloud service account credentials

## Security

- All files in this directory are in `.gitignore`
- File permissions set to 600 (owner read/write only)
- These credentials are also backed up in `.env.master`

## Usage

### Oracle Cloud
```bash
oci --config-file .secrets/oracle_config compute instance list
```

### Google Service Account
```bash
export GOOGLE_APPLICATION_CREDENTIALS=.secrets/google_service_account.json
```

---
**Last Updated:** 2025-11-25
