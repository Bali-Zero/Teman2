"""
Servizio traduzione batch (ID → EN) con cache.
Supporta Google Translate API e OpenAI come fallback.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional
import requests
from dotenv import load_dotenv

# Load environment
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
backend_path = PROJECT_ROOT / "apps" / "backend-rag"
load_dotenv(backend_path / ".env")

# Cache file
CACHE_DIR = PROJECT_ROOT / "reports" / "kbli_extraction"
CACHE_FILE = CACHE_DIR / "kbli_translations_cache.json"


class TranslationService:
    """Servizio traduzione con cache."""
    
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.cache_file = CACHE_FILE
        self.load_cache()
    
    def load_cache(self):
        """Carica cache da file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                print(f"📁 Cache caricata: {len(self.cache)} traduzioni")
            except Exception as e:
                print(f"⚠️  Errore caricamento cache: {e}")
                self.cache = {}
        else:
            self.cache = {}
    
    def save_cache(self):
        """Salva cache su file."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            print(f"💾 Cache salvata: {len(self.cache)} traduzioni")
        except Exception as e:
            print(f"⚠️  Errore salvataggio cache: {e}")
    
    def translate_with_google(self, text: str) -> Optional[str]:
        """Traduce usando Google Translate API (gratuito via web)."""
        try:
            # Usa API pubblica Google Translate (limitata ma funziona)
            url = "https://translate.googleapis.com/translate_a/single"
            params = {
                "client": "gtx",
                "sl": "id",
                "tl": "en",
                "dt": "t",
                "q": text
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result and len(result) > 0 and len(result[0]) > 0:
                    translated = result[0][0][0]
                    return translated
            
            return None
        except Exception as e:
            print(f"⚠️  Errore traduzione Google: {e}")
            return None
    
    def translate_with_openai(self, text: str) -> Optional[str]:
        """Traduce usando OpenAI API."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        
        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional translator. Translate Indonesian to English accurately."},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            translated = response.choices[0].message.content.strip()
            return translated
        except Exception as e:
            print(f"⚠️  Errore traduzione OpenAI: {e}")
            return None
    
    def translate(self, text: str, use_cache: bool = True) -> str:
        """
        Traduce testo ID → EN.
        
        Args:
            text: Testo in indonesiano
            use_cache: Usa cache se disponibile
        
        Returns:
            Testo tradotto in inglese
        """
        if not text or not text.strip():
            return ""
        
        # Normalizza chiave cache
        cache_key = text.strip()
        
        # Controlla cache
        if use_cache and cache_key in self.cache:
            return self.cache[cache_key]
        
        # Prova Google Translate prima (gratuito)
        translated = self.translate_with_google(text)
        
        # Fallback a OpenAI se disponibile
        if not translated:
            translated = self.translate_with_openai(text)
        
        # Se ancora non funziona, usa testo originale
        if not translated:
            print(f"⚠️  Traduzione fallita per: {text[:50]}...")
            translated = text  # Fallback a originale
        
        # Salva in cache
        self.cache[cache_key] = translated
        
        # Rate limiting
        time.sleep(0.1)  # 100ms delay tra richieste
        
        return translated
    
    def translate_batch(self, texts: list[str], save_interval: int = 100) -> Dict[str, str]:
        """
        Traduce batch di testi.
        
        Args:
            texts: Lista di testi da tradurre
            save_interval: Salva cache ogni N traduzioni
        
        Returns:
            Dict {originale: tradotto}
        """
        results = {}
        total = len(texts)
        
        print(f"🔄 Traduzione batch: {total} testi")
        
        for i, text in enumerate(texts, 1):
            if not text or not text.strip():
                results[text] = ""
                continue
            
            translated = self.translate(text)
            results[text] = translated
            
            if i % save_interval == 0:
                self.save_cache()
                print(f"   Progress: {i}/{total} ({i/total*100:.1f}%)")
        
        # Salva cache finale
        self.save_cache()
        
        print(f"✅ Traduzione completata: {total} testi")
        return results


# Singleton instance
_translation_service: Optional[TranslationService] = None


def get_translation_service() -> TranslationService:
    """Ottiene istanza singleton del servizio traduzione."""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service
