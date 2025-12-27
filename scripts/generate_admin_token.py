
import jwt
from datetime import datetime, timedelta

# Configuration provided by user
SECRET_KEY = "07XoX6Eu24amEuUye7MhTFO62jzaYJ48myn04DvECN0="
ALGORITHM = "HS256"

def create_admin_token():
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode = {
        "sub": "zero@balizero.com",
        "email": "zero@balizero.com",
        "user_id": "zero_admin",
        "role": "admin",
        "permissions": ["all"],
        "exp": expire
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

if __name__ == "__main__":
    try:
        token = create_admin_token()
        print(f"\nGenerato Token Admin per Zero:\n\n{token}\n")
        print("\nComando pronto all'uso:\n")
        print(f'curl -s -H "Authorization: Bearer {token}" "https://nuzantara-rag.fly.dev/api/team/status"')
    except Exception as e:
        print(f"Errore generazione: {e}")
