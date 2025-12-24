import json
import base64

# Il corpo base64 puro della chiave (senza header/footer) preso dal tuo input
raw_b64 = "".join(ப்பூ
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDZziPmowj2kuXH
rpEzrdeIY10pObfB7PBr9u126X9B3ehoW2aDzRk8hl7YRsUD6pjtRBwwxSFZZk6t
c+Pkzdwhs10n8m9DhatmAQMli4iHH0EHpY0n6P1EzpC3Op9HFMVzjp0nZYaXRCNQ
yeeajU59sB/nCT6EDD8j9E+ar/Oyt/cgTaieSbgyJnbI1rkaoWB1WyOy4ZhngDEw
6kcvuTCNMv99R7e7ls3OVK8zamDpbMAfp/gRN28SefYx6204CIeHbGrWMPtJwiqP
rG/9hPmwvE7gQDj0A/3zatJrpRdu9XRNWnquKGmh1l09Nc9cWTMkTNwamMxC3EUf
MRkSfNcpAgMBAAECggEAA3WFrMqBagLi+8j+IbU0wp2H+ILD+pELL/HERQxRouYi
irHx6e1NnznhYxUVP0bNAZtzonaNA5AV0L7x9OH4/IvuUn2dwZnx79aobVxLqxBM
+0SIZLFlJuzsNjOL6khBiwbOE7BsdhxLfpalGZ3XJZtqZEqDEXwmznW/tzMs0mik
5GdUPAkidleIOKPBK5bQT6vd+tD2NAKSzSuCHVQGSpcesLlevMETHIVmIT81rA13
YbN2V0KfN8Tvwic3bBN6ZEiePRn8g5QCP0bpiaXrQo16AKi9sUrcH6sxlhLUkU97
/D25hzjsAP+uKIavqzPRN6x9mec76TnDx/pYvm3UAQKBgQDvaNQZVEcF8LPT+MGh
eZy4sVZGXOaheT+jF99m3bQHc3Msg6mT8Q/RkmSyoGStsJuMaeVSUkeik8+WhkLb
4PGhyI11+HthXd7FABYH0rvpgek52aOaFH+oHZ+VMfExcz3/v+t1Wf1v00tOxAAm
ixB1qG/Igsp4AkpVLXLNhrjUAQKBgQDo5gxNNv5DbrMONJGRz377mrpVKjbNMstY
xPpA1O8yoLj5CFLRezC62NgicM/eClPjz+tnoSwsvfNnEeo74QiuNYb2hG1gIvY
/il/uKWIUO4WTVt1pfr+foq6p2opgE5tAF4jG+R6QoRBCOy1l3srS1iiSAOy2gq+
kFGCIubjKQKBgCarzibRQC+rc8C3m79Tf4ctzfvLoc1PYoIbpxBcm2ngsifslIW7
GI0HkpBv7BNKRbXmnQ4xEDUonw13XnFZ4m35kTAPFQ7jNMqpeuWEmqnbPCsGBrEq
wnwLXO2ihY0xSkB3Zbcs9A0OGkn8yvFu4RfAP14qEj5UUGF11+du7YgBAoGBAJbR
otW97xor7bgdQsdx34F/yXqtQ5/ObPCnXoftXJkki6R5R2hwpjXZht2GwJXBimHU
nm1UYgkrW3B9CPQWhVahGmiCfLyiife2fabBUGp4UCppWrguZ2NhFigEluRH3DNJ5
knyZ63Ng79RNuzw9RH3c5SDyEbMYkCynuKDViT9BAoGACPX6apWRjcrCZ5Y5Scme
JUUPaucvEAlCYZkWesANZNOcD+SpXXqibE90d3TajC9cMOYVYFCtcjREZjjDFVqW
YOzIx+hCsVTuw2FYdaVDAZ2FcAsJH6expRwROx7d7Zaz5OlLG4pu+a1mB0v/5Mkw
UbQPc1iMJdHXlFTuFpjQvmE=
".split())

# Ricostruisco la chiave con wrapping corretto
pem_key = "-----BEGIN PRIVATE KEY-----\n"
for i in range(0, len(raw_b64), 64):
    pem_key += raw_b64[i:i+64] + "\n"
pem_key += "-----END PRIVATE KEY-----\n"

creds = {
  "type": "service_account",
  "project_id": "nuzantara",
  "private_key_id": "27bd2c546a52252c07c006df9da95bddf375e3ed",
  "private_key": pem_key,
  "client_email": "nuzantara-bot@nuzantara.iam.gserviceaccount.com",
  "client_id": "108084477435262178822",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/nuzantara-bot%40nuzantara.iam.gserviceaccount.com",
  "universe_domain": "googleapis.com"
}

with open("scripts/data/sa_nuzantara.json", "w") as f:
    json.dump(creds, f, indent=2)

print("✅ Chiave ricostruita chirurgicamente.")
