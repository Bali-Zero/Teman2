import pyotp
import qrcode
import time

# 1. Genera il Segreto (La chiave della cassaforte)
key = pyotp.random_base32()

print("--- 🔐 CONFIGURAZIONE SICUREZZA NUZANTARA ---")
print(f"LA TUA CHIAVE SEGRETA: {key}")
print("⚠️  COPIA QUESTA STRINGA! Ti servirà nello script della dashboard.")
print("-" * 40)

# 2. Crea il Link per l'App
uri = pyotp.totp.TOTP(key).provisioning_uri(
    name="Nuzantara War Room",
    issuer_name="Bali Zero Prime"
)

# 3. Stampa il QR Code nel terminale
print("\nSCANSIONA QUESTO QR CON GOOGLE AUTHENTICATOR (o Authy):")
qr = qrcode.QRCode()
qr.add_data(uri)
qr.print_ascii(invert=True)
print("-" * 40)
