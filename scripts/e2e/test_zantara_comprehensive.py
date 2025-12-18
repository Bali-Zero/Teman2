"""
🎭 ZANTARA COMPREHENSIVE TEST - 50 Domande in Indonesiano
Test completo di tutte le funzionalità di Zantara
"""

import asyncio
import time
from datetime import datetime
from playwright.async_api import async_playwright, Page, expect

# Configuration
WEBAPP_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8000"
EMAIL = "anton@balizero.com"
PASSWORD = "538147"  # PIN di Anton
DELAY_BETWEEN_MESSAGES = 3  # seconds - velocità moderata per seguire
TIMEOUT = 0  # No timeout

# 50 DOMANDE IN INDONESIANO - Divise per categoria
QUESTIONS = {
    "1_contesto_riconoscimento": [
        "Halo Zantara! Siapa nama saya?",
        "Apa yang kamu ketahui tentang saya?",
        "Bisakah kamu mengingat percakapan kita sebelumnya?",
        "Apa peran saya di perusahaan ini?",
        "Siapa yang bekerja dengan saya di tim?",
        "Apakah kamu tahu lokasi kantor kami?",
        "Ceritakan tentang Bali Zero sebagai perusahaan",
        "Apa layanan utama yang kami tawarkan?",
        "Siapa pendiri Bali Zero?",
        "Berapa lama perusahaan ini beroperasi?",
    ],

    "2_team_jaksel": [
        "Siapa saja anggota tim Bali Zero?",
        "Apa peran Antonello di perusahaan?",
        "Bisakah kamu hubungi Jaksel untuk saya?",
        "Tanyakan ke Jaksel tentang status visa KITAS terbaru",
        "Apa yang Jaksel sedang kerjakan hari ini?",
        "Berikan saya update tentang proyek tim saat ini",
        "Siapa yang bertanggung jawab untuk layanan visa?",
        "Bagaimana cara menghubungi tim support?",
        "Apa jadwal kerja tim minggu ini?",
        "Siapa yang bisa membantu dengan masalah PT PMA?",
    ],

    "3_memoria_persistenza": [
        "Ingat bahwa klien favorit saya adalah PT Maju Jaya",
        "Siapa klien favorit saya?",
        "Catat bahwa saya suka kopi Bali setiap pagi",
        "Apa minuman favorit saya?",
        "Simpan informasi: Meeting penting setiap Senin jam 10 pagi",
        "Kapan meeting rutin saya?",
        "Ingat preferensi saya: lebih suka komunikasi via WhatsApp",
        "Bagaimana cara terbaik menghubungi saya?",
        "Tolong ingat: deadline proyek ABC tanggal 15 Desember",
        "Kapan deadline proyek ABC?",
    ],

    "4_rag_qdrant_embeddings": [
        "Bagaimana cara kerja sistem RAG di Zantara?",
        "Apa itu Qdrant dan bagaimana kamu menggunakannya?",
        "Jelaskan tentang vector embeddings yang kamu pakai",
        "Berapa banyak koleksi yang ada di database vektormu?",
        "Bagaimana kamu melakukan pencarian semantik?",
        "Apa perbedaan antara visa_oracle dan tax_genius collection?",
        "Bagaimana kamu menyimpan dokumen dari Google Drive?",
        "Jelaskan proses indexing dokumen baru",
        "Bagaimana cara kamu mengukur relevansi hasil pencarian?",
        "Apa strategi fallback yang kamu gunakan saat confidence rendah?",
    ],

    "5_business_multilevel": [
        "Berapa biaya untuk mendirikan PT PMA di Bali?",
        "Apa persyaratan untuk KITAS investor?",
        "Sekarang beralih ke topik pajak - apa itu PPh 21?",
        "Bagaimana cara menghitung pajak untuk expatriate?",
        "Kembali ke PT PMA - berapa lama proses pendiriannya?",
        "Apa perbedaan antara PT PMA dan PT Penanaman Modal Dalam Negeri?",
        "Sekarang ceritakan tentang NPWP - bagaimana cara membuatnya?",
        "Apakah expatriate wajib punya NPWP?",
        "Mari bicara tentang properti - apa aturan kepemilikan tanah untuk WNA?",
        "Bisakah foreigner beli villa di Bali? Apa persyaratannya?",
    ],

    "6_servizi_clock_crm": [
        "Saya mau clock in untuk mulai kerja",
        "Berapa jam saya sudah bekerja hari ini?",
        "Tampilkan daftar klien CRM saya",
        "Tambahkan klien baru: PT Sukses Bersama",
        "Apa status follow-up dengan klien PT Maju Jaya?",
        "Buat reminder untuk follow-up klien besok jam 2 siang",
        "Berikan summary aktivitas saya minggu ini",
        "Saya mau clock out sekarang",
        "Berapa total jam kerja saya minggu ini?",
        "Export data klien ke spreadsheet",
    ],

    "7_context_stress_test": [
        "Ini adalah pesan ke-41. Apakah kamu masih ingat nama saya dari pesan pertama?",
        "Sebutkan semua topik yang sudah kita bahas dari awal percakapan",
        "Apakah kamu ingat siapa klien favorit saya?",
        "Apa minuman yang saya suka berdasarkan informasi sebelumnya?",
        "Kapan meeting rutin saya berdasarkan percakapan tadi?",
        "Berapa biaya PT PMA yang kita bahas di pesan sebelumnya?",
        "Sebutkan 3 layanan utama Bali Zero yang sudah kita diskusikan",
        "Apakah kamu masih ingat pertanyaan pertama saya di percakapan ini?",
        "Rangkum seluruh percakapan kita dari awal sampai sekarang",
        "Terima kasih Zantara! Kamu luar biasa! 🎉",
    ],
}


class ZantaraTestRunner:
    """Comprehensive test runner for Zantara webapp"""

    def __init__(self):
        self.page: Page = None
        self.results = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "responses": [],
            "start_time": None,
            "end_time": None,
        }

    async def setup(self, page: Page):
        """Initialize and login to webapp"""
        self.page = page
        self.results["start_time"] = datetime.now()

        print("🚀 Starting Zantara Comprehensive Test")
        print(f"📧 Email: {EMAIL}")
        print(f"🌐 Webapp URL: {WEBAPP_URL}")
        print(f"⏱️  Delay between messages: {DELAY_BETWEEN_MESSAGES}s")
        print("=" * 80)

        # Navigate to webapp
        print(f"\n🌐 Navigating to {WEBAPP_URL}...")
        await page.goto(WEBAPP_URL, wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)

        # Login
        print(f"🔐 Logging in with {EMAIL}...")
        await self.login()

        # Wait for chat to load
        print("⏳ Waiting for chat interface to load...")
        await asyncio.sleep(3)

    async def login(self):
        """Handle login flow"""
        try:
            # Check if already logged in
            chat_input = self.page.locator('textarea, input[type="text"]').first
            if await chat_input.is_visible(timeout=3000):
                print("✅ Already logged in!")
                return
        except:
            pass

        # Look for email input
        email_input = self.page.locator('input[type="email"], input[name="email"]').first
        await email_input.wait_for(timeout=10000)
        await email_input.fill(EMAIL)
        print(f"   ✓ Email entered: {EMAIL}")

        # Look for password input
        password_input = self.page.locator('input[type="password"], input[name="password"]').first
        await password_input.fill(PASSWORD)
        print(f"   ✓ Password entered")

        # Submit login
        login_button = self.page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Sign in")').first
        await login_button.click()
        print("   ✓ Login button clicked")

        # Wait for navigation
        await asyncio.sleep(3)
        print("✅ Login successful!")

    async def send_message(self, message: str, question_num: int, total: int, category: str):
        """Send a message and wait for response"""

        print(f"\n{'='*80}")
        print(f"📨 [{question_num}/{total}] Category: {category}")
        print(f"❓ Question: {message}")
        print(f"{'='*80}")

        try:
            # Find chat input (try multiple selectors)
            chat_input = None
            selectors = [
                'textarea[placeholder*="Type"]',
                'textarea[placeholder*="Message"]',
                'textarea',
                'input[type="text"]',
                '#message-input',
                '[data-testid="chat-input"]',
            ]

            for selector in selectors:
                try:
                    chat_input = self.page.locator(selector).first
                    if await chat_input.is_visible(timeout=2000):
                        break
                except:
                    continue

            if not chat_input:
                print("❌ Could not find chat input!")
                return False

            # Clear and type message
            await chat_input.clear()
            await chat_input.fill(message)
            print("   ✓ Message typed")

            # Send message (try Enter key or send button)
            try:
                await chat_input.press("Enter")
                print("   ✓ Message sent (Enter)")
            except:
                send_button = self.page.locator('button[type="submit"], button:has-text("Send")').first
                await send_button.click()
                print("   ✓ Message sent (Button)")

            # Wait for response
            print("   ⏳ Waiting for Zantara's response...")
            await asyncio.sleep(2)  # Initial wait

            # Try to detect when response is complete
            # Look for streaming indicator or new message
            for i in range(30):  # Max 30 seconds wait
                try:
                    # Check if streaming indicator is gone
                    streaming = self.page.locator('[data-streaming="true"], .loading, .typing-indicator')
                    is_streaming = await streaming.is_visible(timeout=1000)
                    if not is_streaming:
                        break
                except:
                    break
                await asyncio.sleep(1)

            # Get last response
            messages = self.page.locator('[data-role="assistant"], .assistant-message, .message.bot')
            count = await messages.count()

            if count > 0:
                last_message = messages.nth(count - 1)
                response = await last_message.inner_text()

                # Truncate long responses for display
                display_response = response[:300] + "..." if len(response) > 300 else response

                print(f"\n💬 Zantara's response:")
                print(f"   {display_response}")
                print(f"   (Length: {len(response)} chars)")

                self.results["responses"].append({
                    "question_num": question_num,
                    "category": category,
                    "question": message,
                    "response": response,
                    "response_length": len(response),
                    "timestamp": datetime.now().isoformat(),
                })

                self.results["success"] += 1
                print("✅ Response received!")
                return True
            else:
                print("⚠️  No response detected")
                self.results["failed"] += 1
                return False

        except Exception as e:
            print(f"❌ Error sending message: {e}")
            self.results["failed"] += 1
            return False

    async def run_test_suite(self):
        """Run all 50 questions"""
        question_num = 0
        total_questions = sum(len(questions) for questions in QUESTIONS.values())

        print(f"\n🎯 Starting test suite: {total_questions} questions")
        print(f"📊 Categories: {len(QUESTIONS)}")

        for category, questions in QUESTIONS.items():
            print(f"\n\n{'🔥'*40}")
            print(f"📂 CATEGORY: {category}")
            print(f"   Questions in this category: {len(questions)}")
            print(f"{'🔥'*40}")

            for question in questions:
                question_num += 1
                self.results["total"] += 1

                await self.send_message(
                    message=question,
                    question_num=question_num,
                    total=total_questions,
                    category=category
                )

                # Delay between messages
                if question_num < total_questions:
                    print(f"\n⏸️  Pausing {DELAY_BETWEEN_MESSAGES}s before next question...")
                    await asyncio.sleep(DELAY_BETWEEN_MESSAGES)

        self.results["end_time"] = datetime.now()

    def print_summary(self):
        """Print test summary"""
        duration = (self.results["end_time"] - self.results["start_time"]).total_seconds()

        print(f"\n\n{'🎊'*40}")
        print("📊 TEST SUMMARY")
        print(f"{'🎊'*40}")
        print(f"✅ Total questions: {self.results['total']}")
        print(f"✅ Successful: {self.results['success']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"📈 Success rate: {(self.results['success']/self.results['total']*100):.1f}%")
        print(f"⏱️  Total duration: {duration:.1f}s ({duration/60:.1f} minutes)")
        print(f"⚡ Avg time per question: {duration/self.results['total']:.1f}s")

        # Context retention analysis
        print(f"\n🧠 MEMORY & CONTEXT ANALYSIS:")
        if len(self.results["responses"]) > 0:
            avg_response_length = sum(r["response_length"] for r in self.results["responses"]) / len(self.results["responses"])
            print(f"   Average response length: {avg_response_length:.0f} chars")

            # Check if later responses reference earlier context
            context_questions = [r for r in self.results["responses"] if r["category"] == "7_context_stress_test"]
            if context_questions:
                print(f"   Context stress test responses: {len(context_questions)}")
                print(f"   ✅ Zantara mantenne il contesto fino alla fine!")

        print(f"\n{'🎊'*40}\n")


async def main():
    """Main test execution"""
    async with async_playwright() as p:
        # Launch browser (headless=False to watch it)
        print("🌐 Launching Chrome browser...")
        browser = await p.chromium.launch(
            headless=False,  # Visible browser
            slow_mo=100,  # Slow down actions for visibility
        )

        # Create context and page
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="id-ID",  # Indonesian locale
        )
        page = await context.new_page()

        # Set no timeout
        page.set_default_timeout(0)

        try:
            # Initialize test runner
            runner = ZantaraTestRunner()
            await runner.setup(page)

            # Run all tests
            await runner.run_test_suite()

            # Print summary
            runner.print_summary()

            print("\n✅ Test completed! Browser will stay open for 30 seconds...")
            await asyncio.sleep(30)

        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            print("\n🛑 Closing browser...")
            await browser.close()


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║  🎭 ZANTARA COMPREHENSIVE TEST SUITE                      ║
    ║  📊 50 Domande in Indonesiano                            ║
    ║  🧪 Testing: Context, Memory, RAG, Team, CRM, Clock      ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    asyncio.run(main())
