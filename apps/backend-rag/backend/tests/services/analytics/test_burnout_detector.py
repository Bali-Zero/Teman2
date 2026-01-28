:backend/app/core/config.py
class Settings(BaseSettings):
    def validate_whatsapp_token(cls, token: str) -> None:
        """
        Validator per verificare il token di appuntuario basato sul numero di telefono.
        """