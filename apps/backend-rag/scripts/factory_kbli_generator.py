import asyncio
import json
import os
import sys

import pdfplumber
from google import genai
from google.genai import types
from playwright.async_api import async_playwright

# Configuration
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("Error: GOOGLE_API_KEY environment variable not set.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# Resolve paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "templates", "kbli_magazine.html")
SLIDES_TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "templates", "kbli_presentation.html")


def get_template(mode="report"):
    path = SLIDES_TEMPLATE_PATH if mode == "slides" else REPORT_TEMPLATE_PATH
    if not os.path.exists(path):
        print(f"Error: Template not found at {path}")
        sys.exit(1)
    with open(path) as f:
        return f.read()


def extract_text_from_pdf(pdf_path):
    print(f"Extracting text from {pdf_path}...")
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
        sys.exit(1)
    return text


async def generate_deep_dive_content(raw_text, mode="report"):
    print(f"Synthesizing content with Gemini 1.5 Pro (Mode: {mode})...")

    base_prompt = """
You are the Chief Editor of "Bali Zero Intelligence", a premium business intelligence unit.
Your task is to transform raw regulatory text into a "Deep Dive" executive report.

Target Audience: Foreign investors looking to open a business in Bali.
Tone: Professional, authoritative, yet accessible. High-end magazine style.

Raw Text from KBLI Document:
{raw_text}

Output structured JSON with these fields:
- kbli_code: e.g., "55110"
- kbli_title: e.g., "Star Hotels"
- risk_level: e.g., "High / Menengah Tinggi"
- min_capital: e.g., "10 Billion IDR"
- category: e.g., "Tourism / Accommodation"
- processing_time: e.g., "3-6 Months"
- permit_count: e.g., "5+"
- foreign_ownership: e.g., "100%" (verify against negative investment list)
"""

    if mode == "slides":
        specific_prompt = """
Add these fields specifically for a Visual Presentation Deck:
- img_title: A visually descriptive prompt for an AI image generator for the title slide (e.g., "cinematic shot of luxury bali hotel lobby at sunset, 8k").
- img_opportunity: Image prompt for the market opportunity slide (e.g., "busy tourist street in seminyak, vibrant, golden hour").
- img_requirements: Image prompt for requirements slide (e.g., "architectural blueprint on table, construction helmet, focused").
- img_roadmap: Image prompt for roadmap slide (e.g., "winding road in bali rice fields, drone shot, progress").
- slide_opportunity_text: A concise, punchy paragraph (max 40 words) about the investment opportunity.
- slide_requirements_bullets: HTML <li> elements (3-4 max) summarizing key requirements. Short and impactful.
- slide_roadmap_steps: HTML <div> elements representing 3-4 major steps. Use this format: 
  <div style="flex: 1; background: rgba(0,0,0,0.8); padding: 30px; border-top: 5px solid #D4AF37;">
     <h3 style="color: #D4AF37; margin-top: 0;">Step 1</h3>
     <p style="font-size: 24px;">Step Title</p>
  </div>
"""
    else:
        specific_prompt = """
Add these fields for the Magazine Report:
- executive_summary: A 300-word engaging summary of what this business classification entails, market opportunity in Bali, and key constraints. Use HTML <p> tags.
- requirements_content: HTML formatted content (<h3>, <ul>, <li>, <p>) detailed spatial requirements, zoning, technical standards.
- roadmap_content: HTML formatted content explaining the step-by-step licensing process (NIB -> Sertifikat Standar -> Verified).
"""

    final_prompt = base_prompt + specific_prompt

    # Inject text into prompt
    print(f"Raw text length: {len(raw_text)}")
    full_prompt = final_prompt.replace("{raw_text}", raw_text[:30000])

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=full_prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        if not response.parsed:
            try:
                print("Fallback: Parsing JSON text manually...")
                return json.loads(response.text)
            except Exception as e:
                print(f"Error parsing JSON: {e}")
                print(f"Raw Response: {response.text}")
                return None
        return response.parsed
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        sys.exit(1)


async def render_pdf(data, output_path, mode="report"):
    print(f"Rendering PDF with Playwright... Data type: {type(data)}")

    if not data:
        print("Error: No data generated from LLM.")
        sys.exit(1)

    if isinstance(data, list):
        print("Data is a list, taking first element.")
        data = data[0]

    try:
        template = get_template(mode)

        # Helper to safely format string
        def safe_format(tmpl, **kwargs):
            return tmpl.format(**{k: kwargs.get(k, "") for k in kwargs})

        # Pre-process image prompts to be URL safe
        import urllib.parse

        for key in ["img_title", "img_opportunity", "img_requirements", "img_roadmap"]:
            if key in data:
                data[key] = urllib.parse.quote(data[key])

        # Fill template
        html_content = template.format(
            kbli_code=data.get("kbli_code", "N/A"),
            kbli_title=data.get("kbli_title", "N/A"),
            risk_level=data.get("risk_level", "N/A"),
            min_capital=data.get("min_capital", "N/A"),
            category=data.get("category", "N/A"),
            processing_time=data.get("processing_time", "N/A"),
            permit_count=data.get("permit_count", "N/A"),
            foreign_ownership=data.get("foreign_ownership", "N/A"),
            # Report specific
            executive_summary=data.get("executive_summary", ""),
            requirements_content=data.get("requirements_content", ""),
            roadmap_content=data.get("roadmap_content", ""),
            # Slides specific
            img_title=data.get("img_title", "bali landscape"),
            img_opportunity=data.get("img_opportunity", "busy street bali"),
            img_requirements=data.get("img_requirements", "construction site"),
            img_roadmap=data.get("img_roadmap", "road map"),
            slide_opportunity_text=data.get("slide_opportunity_text", ""),
            slide_requirements_bullets=data.get("slide_requirements_bullets", ""),
            slide_roadmap_steps=data.get("slide_roadmap_steps", ""),
        )

        # Save debug HTML
        debug_html_path = output_path + ".debug.html"
        with open(debug_html_path, "w") as f:
            f.write(html_content)
        print(f"Debug HTML saved at: {debug_html_path}")

        async with async_playwright() as p:
            print("Launching system Google Chrome...")
            executable_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            browser = await p.chromium.launch(executable_path=executable_path, headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Set content with a longer timeout
            await page.set_content(html_content, wait_until="networkidle", timeout=60000)

            # Wait a bit for fonts and images to load
            print("Waiting for assets to load...")
            await asyncio.sleep(5)

            # Determine format based on mode
            if mode == "slides":
                await page.pdf(
                    path=output_path,
                    width="1920px",
                    height="1080px",
                    print_background=True,
                    page_ranges="1-4",
                )
            else:
                await page.pdf(
                    path=output_path,
                    format="A4",
                    print_background=True,
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )

            await browser.close()

        print(f"PDF generated successfully at: {output_path}")
    except Exception as e:
        print(f"Error rendering PDF: {e}")
        # Traceback
        import traceback

        traceback.print_exc()
        sys.exit(1)


async def main():
    if len(sys.argv) < 3:
        print("Usage: python factory_kbli_generator.py <input_pdf> <output_pdf> [--slides]")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]
    mode = "slides" if "--slides" in sys.argv else "report"

    # 1. Extract
    raw_text = extract_text_from_pdf(input_pdf)

    # 2. Synthesize
    content_data = await generate_deep_dive_content(raw_text, mode=mode)

    # 3. Render
    await render_pdf(content_data, output_pdf, mode=mode)


if __name__ == "__main__":
    asyncio.run(main())
