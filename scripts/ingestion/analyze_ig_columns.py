import fitz
import glob

# Find I.G
pdf = glob.glob("/Users/antonellosiano/Desktop/nuzantara/lampiran/*I.G*.pdf")[0]
doc = fitz.open(pdf)
page = doc[4]  # Page 5

print(f"ANALYZING {pdf} PAGE 5 Headers...")
words = page.get_text("words")
headers = [w for w in words if w[1] < 250]  # Headers are high up
headers.sort(key=lambda w: w[0])

for h in headers:
    text = h[4]
    if len(text) > 1:
        print(f"X={int(h[0])}-{int(h[2])} (Mid {int((h[0] + h[2]) / 2)}): {text}")
