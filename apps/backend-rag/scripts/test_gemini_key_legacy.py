import os
import google.generativeai as genai

def test_key():
    key = "AIzaSyC1cM933ORSdB4CCAx8EYe4mNsYShIoGDI"
    print(f"Testing key with legacy SDK: {key[:10]}...")
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content("Hello, respond with 'OK' if you can hear me.")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_key()
