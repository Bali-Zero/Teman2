import os
import json

# The new key provided by the user
NEW_KEY_JSON = {
    "type": "service_account",
    "project_id": "nuzantara",
    "private_key_id": "39a373fe510d4f61eec73b54b3ba833760f291a1",
    "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDDmjmVXfeSUFTY\ni+zu5pXOtDRvmHWBqGBgommwhQjZlxOlp6J9ikIJYYk7ybvH8D20V7oAa60h3j//\n9UmIQ8SY7R7mfYgWDf/Ms3di39t92DV4CApV1QkVas8nb45keGUt5qor6p+uJFIg\nHXf7Cuz1RnJ2A1eshDWE+f0gHcRaZHreu7v6/ak2NsQYKKIKdGQIJgvRt7WmyMq1\ngTfPxnRYbJYU64h8ql+TOW3MvH651SfCpo09tDXaRh7UJwoVQmCt3AWA7ZRyc7/0\n2P8cY3OMkVj9gFuzmwC1jdD+gpt9AwQjSGjikasUYDf3x1H6lr1audPltNsgA7+g\njwbReCMTAgMBAAECggEAAoytZwXlMYk/2PnWX23nUmtMOQEJ8bldcuUAYP9MsOXP\nN038gRn0PRBlumnF1+1P7s5HstDQ7HLBKCJCV4xYzXAmO2dQXBzJthlWFCS8KI37\njxloLKKs46KTbuELlaVxbCwvSd3rP8q3oDVQWF8c+VkEYyOfIApOcvG2VLIrEz73\n+nILobAXCPFMK8y6N2QkUQ7Rl9y7uDo0N/O+stcwLJ/W56n0J8xiyhWRDRixRdhw\nONckBLAezm7q384qufnfSxccuL8NzUNOYH79dVIOwkX/zkpOZqUEykVifLEo29Ea\npyBWdgZHnlVBsT+E44h62zcYz/tKrThHXqNdZc44gQKBgQDl4B7Mcmo3LNxvqkgR\n98JA5VeLuJZ2ZhpdJ/ox254/HCL3UcrA02w2sSRVCZ7m+DeS+Ge/W3x/yikLuzz9\nn+QXGwdZ1HVUx1patK8aTcAsR5pQtevuPdU474FxAuJDb1ZJFtZdPPpsbSaIqEig\nlut8YIB5G5RkW/TU85Rre2ik6QKBgQDZ1PuMHfh07HuxvHWJPpv7N7X/S3I4tGI9\nfUnkR6Ms5oGR26UYpq7dr+UBll9Yyzm7TLNbyYj6bPdjZZa1kp/4s87dzBqmAAL+\nWboXMeEwqQiGD83kyKkL6my2vHb9Dibt3CHJRiJ5NVkccgdgSp4mkCYIfC1AzUuc\nJipptBO6mwKBgF/7KGDtFPRcwt3NF7KI5I78M4WfWROupitnWcwfiv+G3AKwIBxL\nKs/bPvRSxApkca/oEEmSBXXGD0VatKihbjdHjdYwI512b3+YGdS9yhOzAffZPd2H\n69OODVoGfjrx7fEum+rqXxWOrZw5x7llyoVwNbRbk6YjzyJrYflO2e6hAoGAcFI7\nNv/JOnkqOvajYJZxFbOfW7mKdyTEN1KgRF6QDDn7e7tXQQPJzTPCkPP5zC5WYXbm\nUSD1SbPgSFd8w7mMVVBaDdINt6Tv5jlcFFO6+z1d0MrbbuntCODjF8LMVCX0+td0\ncHWClx9kCJ/fn846CEZx5hQpvW1eXHDtk72wIpsCgYEA1k6Xd1sze/o1127Fibyo\nC6w1KEmw06/Ky1QvPc2F7IFDyxK1YPtMqpP/e2OiGbddM5M/ZVsMD2OO+hwX8jZY\n1XcoSK1XumhW+zbbUDNhb1IeIqi4/gBv8IkaBBJ4I9MGh5IX4OXEp8por9VGoHMJ\nmiURyPlCHiUpmR7TtxOpU0Q=\n-----END PRIVATE KEY-----\n",
    "client_email": "nuzantara-google-drive-sa@nuzantara.iam.gserviceaccount.com",
    "client_id": "107304438107245099867",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/nuzantara-google-drive-sa%40nuzantara.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}

ENV_PATH = "apps/backend-rag/.env"


def main():
    print(f"🔄 Updating {ENV_PATH}...")

    # Read existing content
    content = ""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            content = f.read()

    # Filter out existing key definition
    lines = [
        l
        for l in content.splitlines()
        if not l.strip().startswith("GOOGLE_SERVICE_ACCOUNT_JSON=")
    ]

    # Minify JSON
    minified_key = json.dumps(NEW_KEY_JSON)

    # Append new key
    # Use single quotes for the value to be safe, though dumping usually escapes quotes
    lines.append(f"GOOGLE_SERVICE_ACCOUNT_JSON='{minified_key}'")

    # Write back
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")

    print("✅ updated .env successfully")


if __name__ == "__main__":
    main()
