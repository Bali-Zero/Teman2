#!/usr/bin/env python3
"""
Compliance Report Generator - PT Urban Jungle Bali
Bali Zero Advisory - KBLI 2025 Alignment & Regulatory Compliance
"""

import os
import sys
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib.colors import Color, white, black, HexColor
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
except ImportError:
    print("ERROR: reportlab not installed. Install with: pip install reportlab")
    sys.exit(1)

# =============================================================================
# Configuration
# =============================================================================
OUTPUT_PATH = "/Users/nuzantara/Desktop/nuzantara/compliance_report_urban_jungle_bali.pdf"
LOGO_PATH = "/Users/nuzantara/Desktop/images/image.png"
PAGE_WIDTH, PAGE_HEIGHT = A4  # 595.27 x 841.89 points

# Colors
BG_COLOR = Color(0.05, 0.05, 0.08)  # Near-black with slight blue tint
TEXT_COLOR = Color(0.92, 0.92, 0.92)  # Slightly warm white
ACCENT_RED = Color(0.85, 0.15, 0.15)  # Deep red accent
ACCENT_RED_LIGHT = Color(0.90, 0.25, 0.25)
DIM_TEXT = Color(0.55, 0.55, 0.58)  # Muted text for secondary info
TABLE_BORDER = Color(0.35, 0.35, 0.38)
TABLE_HEADER_BG = Color(0.12, 0.12, 0.15)
TABLE_ROW_ALT = Color(0.08, 0.08, 0.11)
HIGHLIGHT_BG = Color(0.15, 0.08, 0.08)  # Subtle red tint for critical items
WHITE = white

# Margins
LEFT_MARGIN = 55
RIGHT_MARGIN = 55
TOP_MARGIN = 60
BOTTOM_MARGIN = 70
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

# Font sizes
TITLE_SIZE = 32
SUBTITLE_SIZE = 16
SECTION_TITLE_SIZE = 14
SUBSECTION_SIZE = 12
BODY_SIZE = 9.5
SMALL_SIZE = 8
FOOTER_SIZE = 7


class ComplianceReportGenerator:
    def __init__(self):
        self.c = canvas.Canvas(OUTPUT_PATH, pagesize=A4)
        self.c.setTitle("Compliance Report - PT Urban Jungle Bali - KBLI 2025")
        self.c.setAuthor("Bali Zero Advisory")
        self.c.setSubject("KBLI 2025 Alignment & Regulatory Compliance")
        self.page_num = 0
        self.y = PAGE_HEIGHT - TOP_MARGIN

        # Load logo
        if os.path.exists(LOGO_PATH):
            self.logo = ImageReader(LOGO_PATH)
        else:
            self.logo = None
            print(f"WARNING: Logo not found at {LOGO_PATH}")

    def draw_background(self):
        """Draw black background on the entire page."""
        self.c.setFillColor(BG_COLOR)
        self.c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)

    def draw_logo(self):
        """Draw logo in the top-right corner."""
        if self.logo:
            logo_height = 45
            logo_width = 45  # Will be adjusted by aspect ratio
            try:
                img_w, img_h = self.logo.getSize()
                aspect = img_w / img_h
                logo_width = logo_height * aspect
            except:
                logo_width = 45

            x = PAGE_WIDTH - RIGHT_MARGIN - logo_width
            y = PAGE_HEIGHT - TOP_MARGIN + 5
            self.c.drawImage(
                self.logo, x, y, width=logo_width, height=logo_height,
                preserveAspectRatio=True, mask='auto'
            )

    def draw_footer(self):
        """Draw page footer with confidentiality notice and page number."""
        self.page_num += 1

        # Thin red line above footer
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(0.5)
        self.c.line(LEFT_MARGIN, BOTTOM_MARGIN - 15, PAGE_WIDTH - RIGHT_MARGIN, BOTTOM_MARGIN - 15)

        # Footer text
        self.c.setFont("Helvetica", FOOTER_SIZE)
        self.c.setFillColor(DIM_TEXT)
        self.c.drawString(LEFT_MARGIN, BOTTOM_MARGIN - 28, "CONFIDENZIALE - Bali Zero Advisory")

        # Page number right-aligned
        self.c.drawRightString(
            PAGE_WIDTH - RIGHT_MARGIN, BOTTOM_MARGIN - 28,
            f"Pagina {self.page_num}"
        )

    def new_page(self):
        """Start a new page with background, logo, and footer."""
        if self.page_num > 0:
            self.c.showPage()
        self.draw_background()
        self.draw_logo()
        self.y = PAGE_HEIGHT - TOP_MARGIN - 50  # Below logo area

    def finish_page(self):
        """Finish current page (draw footer)."""
        self.draw_footer()

    def check_space(self, needed):
        """Check if there's enough space on the page, start new page if not."""
        if self.y - needed < BOTTOM_MARGIN + 10:
            self.finish_page()
            self.new_page()
            return True
        return False

    def draw_section_divider(self):
        """Draw a thin red accent line as section divider."""
        self.y -= 8
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(1.2)
        self.c.line(LEFT_MARGIN, self.y, LEFT_MARGIN + 80, self.y)
        self.c.setStrokeColor(Color(0.35, 0.10, 0.10))
        self.c.setLineWidth(0.3)
        self.c.line(LEFT_MARGIN + 80, self.y, PAGE_WIDTH - RIGHT_MARGIN, self.y)
        self.y -= 14

    def draw_section_title(self, number, title):
        """Draw a section title with number."""
        self.check_space(50)
        self.y -= 10

        self.draw_section_divider()

        # Section number in red
        self.c.setFont("Helvetica-Bold", SECTION_TITLE_SIZE)
        self.c.setFillColor(ACCENT_RED_LIGHT)
        num_text = f"SEZIONE {number}"
        self.c.drawString(LEFT_MARGIN, self.y, num_text)
        self.y -= 18

        # Section title in white
        self.c.setFont("Helvetica-Bold", SECTION_TITLE_SIZE)
        self.c.setFillColor(WHITE)
        self.c.drawString(LEFT_MARGIN, self.y, title)
        self.y -= 20

    def draw_subsection_title(self, title):
        """Draw a subsection title."""
        self.check_space(35)
        self.y -= 6

        self.c.setFont("Helvetica-Bold", SUBSECTION_SIZE)
        self.c.setFillColor(TEXT_COLOR)
        self.c.drawString(LEFT_MARGIN + 5, self.y, title)
        self.y -= 16

    def draw_body_text(self, text, indent=0, bold=False):
        """Draw body text with word wrapping."""
        self.check_space(20)

        font = "Helvetica-Bold" if bold else "Helvetica"
        self.c.setFont(font, BODY_SIZE)
        self.c.setFillColor(TEXT_COLOR)

        x = LEFT_MARGIN + indent
        max_width = CONTENT_WIDTH - indent

        # Simple word wrap
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test = current_line + (" " if current_line else "") + word
            if self.c.stringWidth(test, font, BODY_SIZE) < max_width:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for line in lines:
            self.check_space(14)
            self.c.setFont(font, BODY_SIZE)
            self.c.setFillColor(TEXT_COLOR)
            self.c.drawString(x, self.y, line)
            self.y -= 13.5

    def draw_bullet(self, text, indent=10, bullet_char="\u2022"):
        """Draw a bullet point."""
        self.check_space(20)

        x = LEFT_MARGIN + indent
        self.c.setFont("Helvetica", BODY_SIZE)
        self.c.setFillColor(ACCENT_RED_LIGHT)
        self.c.drawString(x, self.y, bullet_char)

        self.c.setFillColor(TEXT_COLOR)
        text_x = x + 12

        font = "Helvetica"
        max_width = CONTENT_WIDTH - indent - 12

        # Handle bold markers **text**
        # Simple approach: render entire text
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test = current_line + (" " if current_line else "") + word
            if self.c.stringWidth(test, font, BODY_SIZE) < max_width:
                current_line = test
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        for i, line in enumerate(lines):
            self.check_space(14)
            self.c.setFont(font, BODY_SIZE)
            self.c.setFillColor(TEXT_COLOR)
            if i == 0:
                self.c.drawString(text_x, self.y, line)
            else:
                self.c.drawString(text_x, self.y, line)
            self.y -= 13.5

    def draw_note_box(self, lines):
        """Draw a highlighted note box."""
        total_height = len(lines) * 14 + 16
        self.check_space(total_height + 10)

        box_x = LEFT_MARGIN + 5
        box_width = CONTENT_WIDTH - 10
        box_y = self.y - total_height + 4

        # Background
        self.c.setFillColor(HIGHLIGHT_BG)
        self.c.roundRect(box_x, box_y, box_width, total_height, 3, fill=1, stroke=0)

        # Left accent bar
        self.c.setFillColor(ACCENT_RED)
        self.c.rect(box_x, box_y, 3, total_height, fill=1, stroke=0)

        # Note label
        self.c.setFont("Helvetica-Bold", SMALL_SIZE)
        self.c.setFillColor(ACCENT_RED_LIGHT)
        self.y -= 4
        self.c.drawString(box_x + 12, self.y, "NOTA:")
        self.y -= 13

        # Note text
        self.c.setFont("Helvetica", SMALL_SIZE)
        self.c.setFillColor(TEXT_COLOR)
        for line in lines:
            words = line.split()
            wrapped = []
            current = ""
            for w in words:
                test = current + (" " if current else "") + w
                if self.c.stringWidth(test, "Helvetica", SMALL_SIZE) < box_width - 24:
                    current = test
                else:
                    if current:
                        wrapped.append(current)
                    current = w
            if current:
                wrapped.append(current)

            for wl in wrapped:
                self.check_space(14)
                self.c.setFont("Helvetica", SMALL_SIZE)
                self.c.setFillColor(TEXT_COLOR)
                self.c.drawString(box_x + 12, self.y, wl)
                self.y -= 12

        self.y -= 6

    def draw_table(self, headers, rows, col_widths=None):
        """Draw a table with styled appearance."""
        num_cols = len(headers)
        if col_widths is None:
            col_widths = [CONTENT_WIDTH / num_cols] * num_cols

        row_height = 22
        header_height = 24
        total_rows = len(rows)
        total_height = header_height + (total_rows * row_height)

        self.check_space(min(total_height + 10, 200))

        x_start = LEFT_MARGIN
        y_start = self.y

        # Draw header row
        self.c.setFillColor(TABLE_HEADER_BG)
        self.c.rect(x_start, y_start - header_height, CONTENT_WIDTH, header_height, fill=1, stroke=0)

        # Header border
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(1.5)
        self.c.line(x_start, y_start, x_start + CONTENT_WIDTH, y_start)
        self.c.line(x_start, y_start - header_height, x_start + CONTENT_WIDTH, y_start - header_height)

        # Header text
        self.c.setFont("Helvetica-Bold", SMALL_SIZE)
        self.c.setFillColor(WHITE)
        cx = x_start
        for i, h in enumerate(headers):
            self.c.drawString(cx + 6, y_start - header_height + 7, h)
            cx += col_widths[i]

        self.y = y_start - header_height

        # Draw data rows
        for row_idx, row in enumerate(rows):
            self.check_space(row_height + 5)

            # Alternate row background
            if row_idx % 2 == 0:
                self.c.setFillColor(TABLE_ROW_ALT)
            else:
                self.c.setFillColor(BG_COLOR)
            self.c.rect(x_start, self.y - row_height, CONTENT_WIDTH, row_height, fill=1, stroke=0)

            # Row bottom border
            self.c.setStrokeColor(TABLE_BORDER)
            self.c.setLineWidth(0.3)
            self.c.line(x_start, self.y - row_height, x_start + CONTENT_WIDTH, self.y - row_height)

            # Cell text
            cx = x_start
            for i, cell in enumerate(row):
                cell_str = str(cell)
                # Check if text fits, truncate if needed
                font = "Helvetica"
                font_size = SMALL_SIZE

                # Check for priority highlighting
                is_critical = cell_str in ["CRITICA", "URGENTE", "OBBLIGATORIA"]

                if is_critical:
                    self.c.setFont("Helvetica-Bold", font_size)
                    self.c.setFillColor(ACCENT_RED_LIGHT)
                else:
                    self.c.setFont(font, font_size)
                    self.c.setFillColor(TEXT_COLOR)

                # Truncate text if it exceeds column width
                max_text_w = col_widths[i] - 12
                display_text = cell_str
                while self.c.stringWidth(display_text, font, font_size) > max_text_w and len(display_text) > 3:
                    display_text = display_text[:-1]
                if display_text != cell_str:
                    display_text = display_text[:-2] + ".."

                self.c.drawString(cx + 6, self.y - row_height + 7, display_text)
                cx += col_widths[i]

            self.y -= row_height

        # Bottom border
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(1)
        self.c.line(x_start, self.y, x_start + CONTENT_WIDTH, self.y)

        self.y -= 10

    # =========================================================================
    # PAGE GENERATION
    # =========================================================================

    def generate_title_page(self):
        """Generate the title/cover page."""
        self.new_page()

        # Decorative top line
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(2)
        self.c.line(LEFT_MARGIN, PAGE_HEIGHT - 90, PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 90)

        # COMPLIANCE REPORT - main title
        self.y = PAGE_HEIGHT - 170
        self.c.setFont("Helvetica-Bold", 38)
        self.c.setFillColor(WHITE)
        self.c.drawString(LEFT_MARGIN, self.y, "COMPLIANCE")
        self.y -= 48
        self.c.drawString(LEFT_MARGIN, self.y, "REPORT")

        # Red accent line
        self.y -= 20
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(3)
        self.c.line(LEFT_MARGIN, self.y, LEFT_MARGIN + 120, self.y)

        # Subtitle
        self.y -= 40
        self.c.setFont("Helvetica", 15)
        self.c.setFillColor(TEXT_COLOR)
        self.c.drawString(LEFT_MARGIN, self.y, "Allineamento KBLI 2025 e Adeguamento Normativo")

        # Company name
        self.y -= 55
        self.c.setFont("Helvetica-Bold", 22)
        self.c.setFillColor(WHITE)
        self.c.drawString(LEFT_MARGIN, self.y, "PT Urban Jungle Bali")

        # Thin line
        self.y -= 18
        self.c.setStrokeColor(TABLE_BORDER)
        self.c.setLineWidth(0.5)
        self.c.line(LEFT_MARGIN, self.y, LEFT_MARGIN + 200, self.y)

        # Client info
        self.y -= 35
        self.c.setFont("Helvetica", 11)
        self.c.setFillColor(DIM_TEXT)
        self.c.drawString(LEFT_MARGIN, self.y, "Preparato per:")
        self.c.setFillColor(TEXT_COLOR)
        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawString(LEFT_MARGIN + 100, self.y, "Daniele")

        self.y -= 22
        self.c.setFont("Helvetica", 11)
        self.c.setFillColor(DIM_TEXT)
        self.c.drawString(LEFT_MARGIN, self.y, "Data:")
        self.c.setFillColor(TEXT_COLOR)
        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawString(LEFT_MARGIN + 100, self.y, "12 Febbraio 2026")

        self.y -= 22
        self.c.setFont("Helvetica", 11)
        self.c.setFillColor(DIM_TEXT)
        self.c.drawString(LEFT_MARGIN, self.y, "Riferimento:")
        self.c.setFillColor(TEXT_COLOR)
        self.c.setFont("Helvetica-Bold", 11)
        self.c.drawString(LEFT_MARGIN + 100, self.y, "BZA-CR-2026-002")

        # Bottom area - Bali Zero Advisory
        self.y = BOTTOM_MARGIN + 70
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(1)
        self.c.line(LEFT_MARGIN, self.y, PAGE_WIDTH - RIGHT_MARGIN, self.y)

        self.y -= 25
        self.c.setFont("Helvetica-Bold", 14)
        self.c.setFillColor(WHITE)
        self.c.drawString(LEFT_MARGIN, self.y, "Bali Zero Advisory")

        self.y -= 18
        self.c.setFont("Helvetica", 9)
        self.c.setFillColor(DIM_TEXT)
        self.c.drawString(LEFT_MARGIN, self.y, "Strategic Business & Regulatory Compliance")

        self.finish_page()

    def generate_section_1(self):
        """Sezione 1: Quadro Normativo di Riferimento"""
        self.new_page()
        self.draw_section_title("1", "Quadro Normativo di Riferimento")

        self.draw_body_text(
            "Il presente report si basa sul seguente quadro normativo, che definisce "
            "gli obblighi di adeguamento per tutte le imprese operanti in Indonesia:"
        )
        self.y -= 6

        regulations = [
            ("Peraturan Kepala BPS No. 7/2025",
             "KBLI 2025 in vigore dal 18 dicembre 2025. Nuova classificazione delle attivita "
             "economiche indonesiane con espansione da ~1.790 a oltre 2.300 codici."),
            ("PP 28/2025 - Perizinan Berusaha Berbasis Risiko",
             "Emanato il 5 giugno 2025 dal Presidente Prabowo. Revisione completa del sistema "
             "di licenze basato sul rischio. Tutte le attivita KBLI che generano reddito "
             "devono essere inserite nell'atto costitutivo."),
            ("BKPM Regulation No. 5/2025",
             "Riduzione del capitale minimo per PT PMA a IDR 2,5 miliardi. Nuova disciplina "
             "degli investimenti esteri e sistema graduato di compliance LKPM."),
        ]

        for reg_title, reg_desc in regulations:
            self.check_space(55)
            self.y -= 4

            # Regulation title with red bullet
            self.c.setFont("Helvetica", BODY_SIZE)
            self.c.setFillColor(ACCENT_RED_LIGHT)
            self.c.drawString(LEFT_MARGIN + 10, self.y, "\u25B8")
            self.c.setFont("Helvetica-Bold", BODY_SIZE)
            self.c.setFillColor(WHITE)
            self.c.drawString(LEFT_MARGIN + 22, self.y, reg_title)
            self.y -= 14

            # Description
            self.c.setFont("Helvetica", BODY_SIZE)
            self.c.setFillColor(TEXT_COLOR)
            words = reg_desc.split()
            current = ""
            max_w = CONTENT_WIDTH - 32
            for w in words:
                test = current + (" " if current else "") + w
                if self.c.stringWidth(test, "Helvetica", BODY_SIZE) < max_w:
                    current = test
                else:
                    self.c.drawString(LEFT_MARGIN + 22, self.y, current)
                    self.y -= 13
                    current = w
            if current:
                self.c.drawString(LEFT_MARGIN + 22, self.y, current)
                self.y -= 13

        self.y -= 8

        # Key deadlines box
        self.check_space(80)

        box_y = self.y - 60
        self.c.setFillColor(HIGHLIGHT_BG)
        self.c.roundRect(LEFT_MARGIN + 5, box_y, CONTENT_WIDTH - 10, 65, 3, fill=1, stroke=0)
        self.c.setFillColor(ACCENT_RED)
        self.c.rect(LEFT_MARGIN + 5, box_y, 3, 65, fill=1, stroke=0)

        self.c.setFont("Helvetica-Bold", SMALL_SIZE + 1)
        self.c.setFillColor(ACCENT_RED_LIGHT)
        self.y -= 4
        self.c.drawString(LEFT_MARGIN + 18, self.y, "SCADENZE CRITICHE:")
        self.y -= 16

        deadlines = [
            ("Scadenza obbligatoria adeguamento KBLI 2025:", "18 giugno 2026"),
            ("Coretax System:", "Operativo da gennaio 2026"),
            ("Finestra di compliance:", "6 mesi dalla data di pubblicazione"),
        ]
        for label, value in deadlines:
            self.c.setFont("Helvetica", SMALL_SIZE)
            self.c.setFillColor(TEXT_COLOR)
            self.c.drawString(LEFT_MARGIN + 18, self.y, label)
            self.c.setFont("Helvetica-Bold", SMALL_SIZE)
            self.c.setFillColor(WHITE)
            lw = self.c.stringWidth(label, "Helvetica", SMALL_SIZE)
            self.c.drawString(LEFT_MARGIN + 22 + lw, self.y, value)
            self.y -= 13

        self.y -= 10

        self.finish_page()

    def generate_section_2(self):
        """Sezione 2: Analisi KBLI Attivi"""
        self.new_page()
        self.draw_section_title("2", "Analisi KBLI Attivi")

        self.draw_body_text(
            "Analisi dettagliata dei codici KBLI attualmente attivi per PT Urban Jungle Bali "
            "e relativa mappatura ai nuovi codici KBLI 2025."
        )
        self.y -= 4

        # 2.1
        self.draw_subsection_title("2.1  KBLI 68111 - Suddivisione nel KBLI 2025")

        self.draw_body_text(
            "Il codice KBLI 68111 (Real Estat Yang Dimiliki Sendiri Atau Disewa - Hunian) "
            "e stato suddiviso in tre codici distinti nella classificazione 2025:"
        )
        self.y -= 4

        headers_2_1 = ["Nuovo Codice", "Denominazione", "Focus"]
        rows_2_1 = [
            ["68111", "Aktivitas Pengembangan Bangunan Dan Lahan Hunian", "Sviluppo immobiliare residenziale"],
            ["68112", "Aktivitas Penyewaan Bangunan Dan Lahan Hunian", "Affitto/gestione immobili residenziali"],
            ["68129", "Aktivitas Real Estat Nonhunian Lainnya", "Immobili non residenziali"],
        ]
        self.draw_table(headers_2_1, rows_2_1, [80, 250, CONTENT_WIDTH - 330])

        self.y -= 4
        self.draw_note_box([
            "Per attivita di locazione immobiliare, il codice corretto sara verosimilmente il 68112.",
            "Tutti i codici sono aperti al 100% proprieta straniera."
        ])

        self.y -= 6

        # 2.2
        self.draw_subsection_title("2.2  KBLI 55193 (Villa) - Rinumerato a 55203")

        bullets_2_2 = [
            "Stessa attivita, semplice rinumerazione: KBLI 55193 diventa 55203",
            "Livello di rischio: Medio-Basso (Menengah Rendah)",
            "100% proprieta straniera consentita",
            "PP 28/2025: deve essere inserito nell'atto costitutivo se genera reddito",
        ]
        for b in bullets_2_2:
            self.draw_bullet(b)

        self.finish_page()

    def generate_section_3(self):
        """Sezione 3: KBLI da Attivare - Codice 68200"""
        self.new_page()
        self.draw_section_title("3", "KBLI da Attivare - Codice 68200")

        self.draw_body_text(
            "Il codice 68200 (Aktivitas Real Estat Atas Dasar Balas Jasa/Kontrak) si e suddiviso "
            "in QUATTRO nuovi codici nella classificazione KBLI 2025:"
        )
        self.y -= 4

        headers_3 = ["Nuovo Codice", "Denominazione", "Ambito"]
        rows_3 = [
            ["68210", "Aktivitas Jasa Intermediasi Real Estat", "Intermediazione/brokeraggio"],
            ["68291", "Jasa Penaksir Real Estat", "Valutazione/perizia immobiliare"],
            ["68292", "Pengelolaan Real Estat Hunian", "Gestione immobili residenziali su fee"],
            ["68299", "Aktivitas Real Estat Lainnya", "Altre attivita immobiliari su fee"],
        ]
        self.draw_table(headers_3, rows_3, [80, 250, CONTENT_WIDTH - 330])

        self.y -= 4

        # Characteristics
        self.draw_subsection_title("Caratteristiche comuni:")
        chars = [
            "Tutti classificati rischio Medio-Alto (Menengah Tinggi) - richiedono NIB + Sertifikat Standar",
            "Tutti aperti al 100% proprieta straniera",
            "Tempistica verifica: 3 giorni lavorativi",
        ]
        for ch in chars:
            self.draw_bullet(ch)

        self.y -= 6

        self.draw_note_box([
            "Per PT Urban Jungle Bali: il codice piu pertinente e verosimilmente il 68292",
            "(Pengelolaan Real Estat Hunian) - gestione immobili residenziali su fee/contratto."
        ])

        self.y -= 8

        # Strategic advantage
        self.check_space(60)
        box_y = self.y - 45
        self.c.setFillColor(Color(0.08, 0.12, 0.08))  # Subtle green tint
        self.c.roundRect(LEFT_MARGIN + 5, box_y, CONTENT_WIDTH - 10, 50, 3, fill=1, stroke=0)
        self.c.setFillColor(Color(0.2, 0.65, 0.2))
        self.c.rect(LEFT_MARGIN + 5, box_y, 3, 50, fill=1, stroke=0)

        self.c.setFont("Helvetica-Bold", SMALL_SIZE + 1)
        self.c.setFillColor(Color(0.3, 0.75, 0.3))
        self.y -= 6
        self.c.drawString(LEFT_MARGIN + 18, self.y, "VANTAGGIO STRATEGICO:")
        self.y -= 15

        self.c.setFont("Helvetica", SMALL_SIZE)
        self.c.setFillColor(TEXT_COLOR)
        adv_text = (
            "Poiche il codice 68200 non e ancora attivo in OSS, si puo passare direttamente ai nuovi codici "
            "KBLI 2025 senza necessita di doppio passaggio (disattivazione vecchio + attivazione nuovo)."
        )
        words = adv_text.split()
        current = ""
        max_w = CONTENT_WIDTH - 40
        for w in words:
            test = current + (" " if current else "") + w
            if self.c.stringWidth(test, "Helvetica", SMALL_SIZE) < max_w:
                current = test
            else:
                self.c.drawString(LEFT_MARGIN + 18, self.y, current)
                self.y -= 12
                current = w
        if current:
            self.c.drawString(LEFT_MARGIN + 18, self.y, current)
            self.y -= 12

        self.y -= 10

        self.finish_page()

    def generate_section_4(self):
        """Sezione 4: Retroattivita e Migrazione Obbligatoria"""
        self.new_page()
        self.draw_section_title("4", "Retroattivita e Migrazione Obbligatoria")

        self.draw_body_text(
            "La conversione ai codici KBLI 2025 e OBBLIGATORIA per tutte le imprese registrate in Indonesia. "
            "Di seguito le implicazioni chiave per PT Urban Jungle Bali:"
        )
        self.y -= 6

        bullets_4 = [
            "La conversione e OBBLIGATORIA per tutte le imprese, senza eccezioni",
            "Dopo il 18 giugno 2026, i codici KBLI 2020 diventano \"ghost codes\" - non piu riconosciuti dal sistema",
            "Conseguenze del mancato adeguamento: disallineamento Coretax, gap nel reporting LKPM, blocco licenze operative",
            "OSS non ha ancora integrato i codici KBLI 2025 (stato a febbraio 2026) - aggiornamento imminente",
        ]
        for b in bullets_4:
            self.draw_bullet(b)

        self.y -= 8

        # Strategy box
        self.draw_subsection_title("Strategia raccomandata:")

        strat_bullets = [
            "Preparare tutta la documentazione necessaria ORA, in anticipazione",
            "Eseguire l'aggiornamento effettivo quando OSS integra i nuovi codici",
            "NON forzare aggiornamenti prematuri - rischio concreto di blocco NIB",
            "Monitorare costantemente le comunicazioni BKPM per apertura della migrazione",
        ]
        for b in strat_bullets:
            self.draw_bullet(b, indent=15)

        self.y -= 6

        # Warning box
        self.check_space(40)
        box_h = 35
        box_y = self.y - box_h
        self.c.setFillColor(HIGHLIGHT_BG)
        self.c.roundRect(LEFT_MARGIN + 5, box_y, CONTENT_WIDTH - 10, box_h, 3, fill=1, stroke=0)
        self.c.setFillColor(ACCENT_RED)
        self.c.rect(LEFT_MARGIN + 5, box_y, 3, box_h, fill=1, stroke=0)

        self.c.setFont("Helvetica-Bold", SMALL_SIZE + 1)
        self.c.setFillColor(ACCENT_RED_LIGHT)
        self.y -= 8
        self.c.drawString(LEFT_MARGIN + 18, self.y, "ATTENZIONE: Non forzare aggiornamenti prematuri su OSS.")
        self.y -= 14
        self.c.setFont("Helvetica", SMALL_SIZE)
        self.c.setFillColor(TEXT_COLOR)
        self.c.drawString(LEFT_MARGIN + 18, self.y,
                          "Un tentativo di aggiornamento prima dell'integrazione ufficiale puo causare il blocco del NIB.")
        self.y -= 18

        self.finish_page()

    def generate_section_5(self):
        """Sezione 5: Modifica Atto Costitutivo e AGMS"""
        self.new_page()
        self.draw_section_title("5", "Modifica Atto Costitutivo e AGMS")

        # 5.1
        self.draw_subsection_title("5.1  Requisiti PP 28/2025")

        bullets_5_1 = [
            "Tutte le attivita KBLI che generano reddito devono essere formalmente inserite nell'atto costitutivo (Anggaran Dasar)",
            "Il codice KBLI 55193/55203 (Villa/Pondok Wisata) va incorporato formalmente se genera reddito operativo",
            "Obbligo di allineamento tra codici KBLI dichiarati in OSS e quelli nell'atto costitutivo",
        ]
        for b in bullets_5_1:
            self.draw_bullet(b)

        self.y -= 6

        # 5.2
        self.draw_subsection_title("5.2  Passaggi operativi")

        steps = [
            ("1.", "Modifica atto costitutivo (Akta Perubahan)", "Atto notarile con inserimento di tutti i codici KBLI attivi che generano reddito"),
            ("2.", "Approvazione KEMENKUMHAM", "Sottomissione entro 30 giorni dalla data dell'atto notarile"),
            ("3.", "Aggiornamento OSS", "Allineamento del profilo OSS con il nuovo atto costitutivo"),
        ]

        for num, title, desc in steps:
            self.check_space(35)
            self.c.setFont("Helvetica-Bold", BODY_SIZE)
            self.c.setFillColor(ACCENT_RED_LIGHT)
            self.c.drawString(LEFT_MARGIN + 12, self.y, num)
            self.c.setFillColor(WHITE)
            self.c.drawString(LEFT_MARGIN + 28, self.y, title)
            self.y -= 14
            self.c.setFont("Helvetica", SMALL_SIZE)
            self.c.setFillColor(TEXT_COLOR)
            self.c.drawString(LEFT_MARGIN + 28, self.y, desc)
            self.y -= 16

        self.y -= 4

        # 5.3
        self.draw_subsection_title("5.3  AGMS (UU PT No. 40/2007)")

        agms_bullets = [
            "AGMS obbligatoria entro 6 mesi dalla chiusura dell'esercizio (giugno 2026)",
            "Approvazione bilancio e modifica AoA combinabili in un'unica assemblea",
            "Quorum modifica AoA: 2/3 del capitale presente, 2/3 dei voti favorevoli (art. 88)",
            "Alternativa: Circolare dei Soci (art. 91) senza necessita di riunione fisica",
        ]
        for b in agms_bullets:
            self.draw_bullet(b)

        self.finish_page()

    def generate_section_6(self):
        """Sezione 6: LKPM Q3 2025 - Verifica e Regolarizzazione"""
        self.new_page()
        self.draw_section_title("6", "LKPM Q3 2025 - Verifica e Regolarizzazione")

        self.draw_body_text(
            "Il LKPM Q3 2025 risulta incompleto o da revisionare. E opportuno analizzare "
            "la situazione e procedere alla regolarizzazione nei tempi corretti."
        )
        self.y -= 6

        # Deadline info
        self.check_space(30)
        self.c.setFont("Helvetica-Bold", BODY_SIZE)
        self.c.setFillColor(TEXT_COLOR)
        self.c.drawString(LEFT_MARGIN + 10, self.y, "Scadenza originaria LKPM Q3 2025: 15 ottobre 2025")
        self.y -= 18

        self.draw_subsection_title("Quadro sanzionatorio (sistema graduato):")

        graduated = [
            "Il sistema BKPM prevede un iter sanzionatorio progressivo, non automatico",
            "Pelanggaran Ringan (violazione lieve): scatta dopo 2 trimestri consecutivi mancati - avvisi scritti",
            "Pelanggaran Sedang (violazione media): sospensione temporanea con 30 giorni per correggere",
            "Pelanggaran Berat (violazione grave): revoca NIB - solo dopo l'intero iter di warning",
            "La mancata presentazione di un singolo trimestre viene registrata dal sistema OSS ma non comporta sanzioni immediate",
            "I dati del trimestre mancato possono essere accumulati nel report del trimestre successivo",
        ]
        for r in graduated:
            self.draw_bullet(r)

        self.y -= 8

        self.draw_subsection_title("Aspetti da considerare:")

        considerations = [
            "Il sistema OSS chiude la finestra di inserimento dopo la scadenza trimestrale",
            "Con l'integrazione Coretax, i dati LKPM vengono incrociati con la SPT Badan",
            "Per le PT PMA il monitoraggio BKPM e piu attento rispetto alle PT locali",
            "La compliance LKPM incide sul profilo di rischio per future richieste di permessi",
        ]
        for r in considerations:
            self.draw_bullet(r)

        self.y -= 8

        # Action box
        self.check_space(55)
        box_h = 50
        box_y = self.y - box_h
        self.c.setFillColor(HIGHLIGHT_BG)
        self.c.roundRect(LEFT_MARGIN + 5, box_y, CONTENT_WIDTH - 10, box_h, 3, fill=1, stroke=0)
        self.c.setFillColor(ACCENT_RED)
        self.c.rect(LEFT_MARGIN + 5, box_y, 3, box_h, fill=1, stroke=0)

        self.c.setFont("Helvetica-Bold", SMALL_SIZE + 1)
        self.c.setFillColor(ACCENT_RED_LIGHT)
        self.y -= 8
        self.c.drawString(LEFT_MARGIN + 18, self.y, "RACCOMANDAZIONE:")
        self.y -= 15

        self.c.setFont("Helvetica", SMALL_SIZE)
        self.c.setFillColor(TEXT_COLOR)
        self.c.drawString(LEFT_MARGIN + 18, self.y, "Verificare lo stato del Q3 nel sistema OSS e regolarizzare includendo i dati nel prossimo report.")
        self.y -= 12
        self.c.drawString(LEFT_MARGIN + 18, self.y, "Assicurarsi che Q4 2025 e Q1 2026 siano stati presentati correttamente e nei termini.")
        self.y -= 20

        self.finish_page()

    def generate_section_7(self):
        """Sezione 7: Compliance OTA e Deadline 31 Marzo 2026"""
        self.new_page()
        self.draw_section_title("7", "Compliance OTA e Deadline 31 Marzo 2026")

        self.draw_body_text(
            "Una nuova criticita rilevante per PT Urban Jungle Bali emerge dalla Circolare del "
            "Ministero del Turismo (Kemenparekraf) del 8 dicembre 2025."
        )
        self.y -= 6

        self.draw_subsection_title("Circolare B/SD/80/II.01/D.3.3/2025 - Registrazione OTA:")

        self.draw_body_text(
            "Il Ministero del Turismo richiede a tutte le Online Travel Agencies (Airbnb, Booking.com, "
            "Agoda, etc.) di verificare che ogni proprieta listed abbia:"
        )
        self.y -= 4

        ota_requirements = [
            "NIB (Nomor Induk Berusaha) valido",
            "KBLI appropriato registrato (es. 55203 per Villa, 68112 per gestione immobiliare)",
            "Licenze turistiche complete e aggiornate",
            "Label \"Terdaftar dan Berizin\" visibile sul listing",
        ]
        for req in ota_requirements:
            self.draw_bullet(req)

        self.y -= 6

        # Deadline box
        self.check_space(45)
        box_h = 40
        box_y = self.y - box_h
        self.c.setFillColor(HIGHLIGHT_BG)
        self.c.roundRect(LEFT_MARGIN + 5, box_y, CONTENT_WIDTH - 10, box_h, 3, fill=1, stroke=0)
        self.c.setFillColor(ACCENT_RED)
        self.c.rect(LEFT_MARGIN + 5, box_y, 3, box_h, fill=1, stroke=0)

        self.c.setFont("Helvetica-Bold", BODY_SIZE)
        self.c.setFillColor(ACCENT_RED_LIGHT)
        self.y -= 8
        self.c.drawString(LEFT_MARGIN + 18, self.y, "DEADLINE CRITICA: 31 MARZO 2026")
        self.y -= 14
        self.c.setFont("Helvetica", SMALL_SIZE)
        self.c.setFillColor(TEXT_COLOR)
        self.c.drawString(LEFT_MARGIN + 18, self.y, "Proprieta non conformi = delisting automatico dalle piattaforme OTA")
        self.y -= 20

        self.draw_subsection_title("Enforcement Governativo Bali (Governatore Koster):")

        enforcement_items = [
            "Oltre 2.000 proprieta a Bali a rischio delisting immediato",
            "Focus enforcement su: zoning compliance, PBG/SLF, registrazione fiscale (PAD)",
            "Fine della \"grey zone\" - mercato informale ville in via di smantellamento sistematico",
            "Crackdown coordinato tra Governo Provinciale, Kemenparekraf, e piattaforme OTA",
        ]
        for item in enforcement_items:
            self.draw_bullet(item)

        self.y -= 6

        self.draw_subsection_title("Impatto su PT Urban Jungle Bali:")

        self.draw_body_text(
            "Se PT Urban Jungle Bali gestisce ville tramite OTA, e essenziale verificare che tutte le "
            "proprieta nel portfolio abbiano NIB completo, KBLI aggiornato (preferibilmente gia KBLI 2025), "
            "e licenze turistiche in regola PRIMA del 31 marzo 2026. Il mancato rispetto comporta il delisting "
            "dalle piattaforme, con perdita immediata del canale di distribuzione principale."
        )

        self.finish_page()

    def generate_section_8(self):
        """Sezione 8: Piano Operativo e Calendario"""
        self.new_page()
        self.draw_section_title("8", "Piano Operativo e Calendario")

        self.draw_body_text(
            "Di seguito il piano operativo raccomandato con indicazione delle tempistiche "
            "e livelli di priorita per ciascuna attivita:"
        )
        self.y -= 6

        # Main operational plan table
        headers_7 = ["#", "Attivita", "Tempistica", "Priorita"]
        rows_7 = [
            ["1", "KBLI Audit & Mapping", "1-2 settimane", "CRITICA"],
            ["2", "Verifica compliance OTA (NIB + licenze)", "Immediata", "CRITICA"],
            ["3", "Verifica LKPM Q3 2025 + regolarizzazione", "1-2 settimane", "CONSIGLIATA"],
            ["4", "Preparazione AGMS", "2-3 settimane", "ALTA"],
            ["5", "Modifica Atto Costitutivo + KEMENKUMHAM", "2-4 settimane", "ALTA"],
            ["6", "AGMS (bilancio + modifica AoA)", "Entro giu. 2026", "OBBLIGATORIA"],
            ["7", "Aggiornamento OSS KBLI 2025", "Attesa BKPM", "CRITICA"],
            ["8", "Verifica post-aggiornamento", "1 sett. dopo OSS", "ALTA"],
        ]
        col_w = [30, 230, 110, CONTENT_WIDTH - 370]
        self.draw_table(headers_7, rows_7, col_w)

        self.y -= 10

        # Key deadlines
        self.draw_subsection_title("Scadenze chiave:")

        headers_dl = ["Scadenza", "Data"]
        rows_dl = [
            ["Compliance OTA (NIB + licenze)", "31 marzo 2026"],
            ["LKPM Q1 2026", "15 aprile 2026"],
            ["SPT Tahunan Badan 2025", "30 aprile 2026"],
            ["AGMS esercizio 2025", "Entro 30 giugno 2026"],
            ["Adeguamento KBLI 2025", "18 giugno 2026"],
        ]
        self.draw_table(headers_dl, rows_dl, [CONTENT_WIDTH * 0.55, CONTENT_WIDTH * 0.45])

        self.finish_page()

    def generate_disclaimer_page(self):
        """Generate the final disclaimer page."""
        self.new_page()

        self.y = PAGE_HEIGHT - 180

        # Decorative line
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(1.5)
        self.c.line(LEFT_MARGIN, self.y + 40, PAGE_WIDTH - RIGHT_MARGIN, self.y + 40)

        self.c.setFont("Helvetica-Bold", 18)
        self.c.setFillColor(WHITE)
        self.c.drawString(LEFT_MARGIN, self.y, "Disclaimer")

        self.y -= 12
        self.c.setStrokeColor(ACCENT_RED)
        self.c.setLineWidth(2)
        self.c.line(LEFT_MARGIN, self.y, LEFT_MARGIN + 80, self.y)

        self.y -= 30

        disclaimer_text = (
            "Il presente documento ha natura consultiva e non costituisce parere legale. "
            "Le informazioni sono basate sulla normativa vigente alla data di redazione. "
            "Si consiglia di verificare gli aggiornamenti normativi prima di intraprendere "
            "qualsiasi azione. Bali Zero Advisory declina ogni responsabilita per decisioni "
            "assunte sulla base esclusiva del presente documento senza preventiva verifica "
            "professionale."
        )

        self.c.setFont("Helvetica", 10)
        self.c.setFillColor(DIM_TEXT)

        words = disclaimer_text.split()
        lines = []
        current = ""
        max_w = CONTENT_WIDTH - 20
        for w in words:
            test = current + (" " if current else "") + w
            if self.c.stringWidth(test, "Helvetica", 10) < max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)

        for line in lines:
            self.c.drawString(LEFT_MARGIN + 10, self.y, line)
            self.y -= 16

        self.y -= 30
        self.c.setStrokeColor(TABLE_BORDER)
        self.c.setLineWidth(0.5)
        self.c.line(LEFT_MARGIN, self.y, PAGE_WIDTH - RIGHT_MARGIN, self.y)

        self.y -= 30
        self.c.setFont("Helvetica-Bold", 12)
        self.c.setFillColor(WHITE)
        self.c.drawString(LEFT_MARGIN, self.y, "Bali Zero Advisory")

        self.y -= 18
        self.c.setFont("Helvetica", 9)
        self.c.setFillColor(DIM_TEXT)
        self.c.drawString(LEFT_MARGIN, self.y, "Strategic Business & Regulatory Compliance")

        self.y -= 16
        self.c.drawString(LEFT_MARGIN, self.y, "12 Febbraio 2026")

        self.finish_page()

    def generate(self):
        """Generate the complete report."""
        print("Generating Compliance Report...")
        print(f"Output: {OUTPUT_PATH}")

        self.generate_title_page()
        self.generate_section_1()
        self.generate_section_2()
        self.generate_section_3()
        self.generate_section_4()
        self.generate_section_5()
        self.generate_section_6()
        self.generate_section_7()
        self.generate_section_8()
        self.generate_disclaimer_page()

        self.c.save()
        print(f"\nReport generated successfully: {OUTPUT_PATH}")
        print(f"Total pages: {self.page_num}")


if __name__ == "__main__":
    generator = ComplianceReportGenerator()
    generator.generate()
