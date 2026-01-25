import json

# The raw components provided by the user
PRIVATE_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQChObDZg3ZvALQu
KN8xqNUNw5dCobxGWhOuGvepqeL6e7FeqmoG+Yw01sdIBdSRee6tOPX5ARD0s/R+
jf0aeqKXPblHbbmgPjADt8gNaj2f3hNGhUqQ9AcOHVZlRfMkV++g9RfZ8IQ4VLQ6
WkvpqCjhFfNaramvII4VYo0I7yotfJIewU9Rm5Iy4EjTE/LdmY6zwzrd/LNhAAGs
kVyDE1s6vUg6mJKIf5qZDf2YF89cV1+IPmPxYKUbFuAU+RcLqhfylTu/E3dKIIwl
MiGj7l8tFFnzWaIp34GQWvOss8MbGwfMJyvVfJAHGyijBgfbq5CmoeWntS3667Px
8qeTJsqTAgMBAAECggEAPg0trzHFOejL8D4j1QGVanQ+edM02uDdVTOk4WR06xID
TJuLLj8KguWtEl/IFeuXfI0BQoJyC7RdI/4zDWdov4vujPrCqFV29l9b/CnJKQf4
ZDp13f9F3d1VvKmk8HZ10H20XdmPkfyr1w+cywPBJAxmOp6/QZtmg/2HqYofMhz0
xUHUWruLmO8WcBb2Rm9INNq6u6xBNAtrjwUO5yjXXGghockB1SbPj5mNdIyn2ndF
4zjR2Q+jX+SBFDkI5CaW6Cwf5sr5ZYe++oeBBsmxqHN3o/X+73LPOddKiuJcYjEH
9rJyasZC4zEFLdIHg2bm8b8YWRCDUleHVgmo+nhbrQKBgQDStEtVZ1fMuMOlD1+U
P1o3lW2SVgHKTZYMVTj1C8IAN6gEt0dFt+V9LnE3u/JeyomvzLk090jtIOROh5vd
A0RFEqBMtDGGaceb3p5r7HcXnLBK8a9N3jYrxc+gIZxykhaydk041V9CWV06Y9gH
y5Rz59ewUs2fzXj/IhqfG/PobQKBgQDD4mtIaKzDH2FxYGue/GBPCxo2k4KCzw1h
e3M9Vt+JT3tTCDNT/SAZKOUOLr1mjQ1lFvu7NeW4DZqqL+8XPT7DgZVgr0bNai7i
j61gcyDyA69ryrSoPuqk1Qc8HfZKjoiu6mBqahn3vs3Dy0XgyeDmy5ulyfpKxcza
96Y6/1ue/wKBgQC9BnYW9hE0XgVWjQYoDvW2q92SzInqndQg2Euyuoueek/He0z7
ZNECjqmPYJM9KuJ+zmDQ/Y90/G8VbF8N1aJnfSBF79oGRduHIB5rn8XvbuhRM6Ub
bGCYwGtVsxGRTzIBhFQeyn0dHuKeQXhK9f4GRVWgn4hM9p639DaByyfzuQKBgQCp
EWLRg28hlpMvHS6mcWPatVVxp42sw3LkIX4Mgk+7nvttZhWPN1md/Zr9y7+zpKjc
CKNLKTDV1AAbRfYR0825Rr4cTgxJPY2sBKB7L8NOv3mICtQ0puE1VZzB+YZbQXyd
pDOFhYBWQbwtcuQkKXpRGYmE5bh/EwxGLhuurjpxFwKBgCO1Qwls3bp53abHsWan
cRl900agV++Ow2u31YlNjsNoEJQOleXaSrKKOEgveNWAOr0Quy7ymdgWXWxuPZkg
KbAwVDBR1OMq4OcSw8oP3HXx6ea4DrLBbF2rIvfXFEyGoTUBCp+gbXsbIokK85Lq
LXMjHflppd7lEQ3GEDtgOt1V
-----END PRIVATE KEY-----"""

# Credentials Dict
creds = {
    "type": "service_account",
    "project_id": "nuzantara",
    "private_key_id": "97f7d659dcf934502184da7ab5521d0dbfc5218f",
    "private_key": PRIVATE_KEY_PEM,
    "client_email": "nuzantara-drive-bot@nuzantara.iam.gserviceaccount.com",
    "client_id": "107320780789686248577",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/nuzantara-drive-bot%40nuzantara.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}

# Serialize to JSON string (ensure only one line)
json_str = json.dumps(creds)

# Escape single quotes for shell safety if wrapping in single quotes
# Actually, best is to not rely on shell specific escaping if possible
# But .env file is often read as KEY='VALUE'
# We will use single quotes around the value, so we must escape any single quotes inside (JSON usually doesn't have them)
env_line = f"GOOGLE_CREDENTIALS_JSON='{json_str}'"

# Read existing .env
env_path = "apps/backend-rag/.env"
try:
    with open(env_path, "r") as f:
        lines = f.readlines()
except FileNotFoundError:
    lines = []

# Replace or Append
new_lines = []
found = False
for line in lines:
    if line.startswith("GOOGLE_CREDENTIALS_JSON=") or line.startswith(
        "GOOGLE_SERVICE_ACCOUNT_JSON="
    ):
        if not found:
            new_lines.append(env_line + "\n")
            found = True
        # Skip duplicates
    else:
        new_lines.append(line)

if not found:
    new_lines.append(env_line + "\n")

# Write back
with open(env_path, "w") as f:
    f.writelines(new_lines)

print(f"✅ Updated {env_path} with correctly formatted credentials.")
