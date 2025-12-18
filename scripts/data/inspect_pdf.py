import pypdf


def main():
    pdf_path = "apps/scraper/data/correspondence-table-kbli-2020---kbli-2015.pdf"

    try:
        reader = pypdf.PdfReader(pdf_path)
        print(f"Total Pages: {len(reader.pages)}")

        print("\n--- PAGE 1 ---")
        print(reader.pages[0].extract_text())

        print("\n--- PAGE 2 ---")
        print(reader.pages[1].extract_text())

        print("\n--- PAGE 200 ---")
        print(reader.pages[199].extract_text())

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
