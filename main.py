from playwright.sync_api import sync_playwright
from configs import *
from datetime import datetime
from os import path
import json
import random
import time
import urllib.request
import ssl
import sys
from urllib.parse import urlparse, urlunparse

SSL_CONTEXT = ssl._create_unverified_context()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding='utf-8')

def detect_browser_path():
    candidates = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in candidates:
        if path.exists(p):
            print(f"[*] Browser ditemukan: {p}")
            return p
    print("[*] Browser lokal tidak ditemukan, menggunakan default Playwright")
    return None

def get_contents_list():
    contents_path = f"{PROJECT_ROOT}/contents.json"
    if not path.exists(contents_path):
        print("[!] contents.json tidak ditemukan, menggunakan konten default.")
        return [{"text": "Hello Everyone!\nAutomated post #{timestamp}", "image": ""}]
    with open(contents_path, "r", encoding="utf-8") as f:
        return json.load(f)

class FacebookGroupSpam:
    def __init__(self) -> None:
        self.playwright = sync_playwright().start()
        try:
            browser_path = detect_browser_path()
            user_data_dir = f"{PROJECT_ROOT}/sessions/brave-profile-post"
            
            if browser_path:
                self.context = self.playwright.chromium.launch_persistent_context(
                    user_data_dir,
                    executable_path=browser_path,
                    headless=False,
                    no_viewport=True
                )
            else:
                self.context = self.playwright.chromium.launch_persistent_context(
                    user_data_dir,
                    headless=True,
                    no_viewport=True
                )
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()

            self.results = {"success": [], "failed": [], "skipped": []}
            
            self.webhook_id_file = f"{PROJECT_ROOT}/sessions/webhook-message-id.json"
            self.last_webhook_msg_id = None
            if path.exists(self.webhook_id_file):
                try:
                    with open(self.webhook_id_file, "r") as f:
                        data = json.load(f)
                        self.last_webhook_msg_id = data.get("message_id")
                except Exception:
                    pass

            self.realtime_statuses = []
            self.current_cycle = 1
            self.pending_approval = set()
            self.user_name = None
            self.load_cookie()

            if not self.check_cookie_valid():
                print("=" * 50)
                print("[!] Cookie sudah expired atau tidak valid!")
                print("[!] Silakan perbarui file cookie JSON Anda di folder sessions/")
                print("=" * 50)
                self.send_cookie_expired_webhook(self.current_cycle)
                return

            cycle = 1
            while True:
                print(f"\n{'=' * 50}")
                print(f"[*] Memulai Autopost ke semua grup (Siklus ke-{cycle})...")
                self.post_to_groups(cycle)
                print(f"\n[*] Siklus ke-{cycle} Selesai!")
                
                loop_delay = random.randint(LOOP_DELAY_MIN, LOOP_DELAY_MAX)
                print(f"[*] Menunggu {loop_delay // 60} menit ({loop_delay} detik) sebelum memulai siklus berikutnya...")
                self.send_discord_webhook(cycle, extra_info=f"Waiting for Cycle {cycle+1} <t:{int(time.time() + loop_delay)}:R>")
                
                time.sleep(loop_delay)
                cycle += 1
                self.current_cycle = cycle
        except KeyboardInterrupt:
            print("\n[!] Program dihentikan oleh pengguna (KeyboardInterrupt).")
        except SystemExit:
            pass
        except Exception as e:
            print(f"\n[!] Terjadi kesalahan fatal: {e}")
        finally:
            print(f"\n[*] Menutup browser dan mematikan Playwright...")
            if hasattr(self, "page") and self.page:
                try: self.page.close()
                except Exception: pass
            if hasattr(self, "context") and self.context:
                try: self.context.close()
                except Exception: pass
            if hasattr(self, "playwright") and self.playwright:
                try: self.playwright.stop()
                except Exception: pass
            print(f"{'=' * 50}")

    def get_random_content(self) -> dict:
        contents = get_contents_list()
        item = random.choice(contents)
        now = datetime.now()
        text = item.get("text", "")
        if text:
            text = text.replace("{timestamp}", now.strftime("%H:%M"))
        image = item.get("image", "")
        background_index = item.get("background_index", None)
        return {"text": text, "image": image, "background_index": background_index}

    def select_facebook_background(self, index: int) -> bool:
        print(f"\t[+] Mencoba memilih background warna ke-{index + 1}...")
        try:
            aa_selectors = [
                "xpath=//div[@role='dialog']//img[contains(@src, 'Aa_square')]/ancestor::div[@role='button']",
                "xpath=//div[@role='dialog']//img[contains(@src, 'Aa_square')]",
                "xpath=//div[@role='dialog']//div[@aria-label='Tampilkan Opsi Latar Belakang' or @aria-label='Show background options' or contains(@aria-label, 'Background') or contains(@aria-label, 'Latar Belakang')][@role='button']",
                "xpath=//div[@role='dialog']//img[contains(@src, 'composer')]/ancestor::div[@role='button']"
            ]
            
            aa_clicked = False
            for sel in aa_selectors:
                try:
                    locator = self.page.locator(sel)
                    if locator.count() > 0 and locator.first.is_visible():
                        locator.first.click()
                        print("\t[+] Tombol Aa diklik.")
                        aa_clicked = True
                        break
                except Exception:
                    continue
                    
            if not aa_clicked:
                res = self.page.evaluate("""() => {
                    const dialog = document.querySelector('[role="dialog"]');
                    if (!dialog) return {success: false, error: 'no-dialog'};
                    const buttons = dialog.querySelectorAll('[role="button"]');
                    for (const btn of buttons) {
                        const label = btn.getAttribute('aria-label') || '';
                        if (label.includes('Latar Belakang') || label.includes('Background') || label.includes('Opsi')) {
                            btn.click();
                            return {success: true, method: 'aria-label', label: label};
                        }
                    }
                    const images = dialog.querySelectorAll('img');
                    for (const img of images) {
                        const src = img.getAttribute('src') || '';
                        if (src.includes('Aa_square') || src.includes('composer/SATP_Aa')) {
                            let parent = img.parentElement;
                            while (parent && parent !== dialog) {
                                if (parent.getAttribute('role') === 'button') {
                                    parent.click();
                                    return {success: true, method: 'img-parent', src: src};
                                }
                                parent = parent.parentElement;
                            }
                            img.click();
                            return {success: true, method: 'img-direct', src: src};
                        }
                    }
                    return {success: false, error: 'not-found'};
                }""")
                if res.get("success"):
                    print("\t[+] Tombol Aa diklik.")
                    aa_clicked = True
                else:
                    print(f"\t[!] Tombol Aa tidak ditemukan ({res.get('error')}). Skip background.")
                    return False
            
            time.sleep(random.uniform(1.5, 2.5))

            clicked = {"success": False}
            for attempt in range(10):
                clicked = self.page.evaluate("""(targetIndex) => {
                    const dialog = document.querySelector('[role="dialog"]');
                    if (!dialog) return {success: false, error: 'no-dialog'};
                    const allDivs = dialog.querySelectorAll('div[style*="background-color"], div[style*="background-image"]');
                    const colorCircles = [];
                    for (const el of allDivs) {
                        const rect = el.getBoundingClientRect();
                        const w = Math.round(rect.width);
                        const h = Math.round(rect.height);
                        if (w >= 28 && w <= 40 && h >= 28 && h <= 40 && el.children.length === 0) {
                            const style = el.getAttribute('style') || '';
                            if (style.includes('rgb(28, 28, 29)') || style.includes('rgb(28,28,29)')) {
                                continue;
                            }
                            colorCircles.push({el: el, style: style.substring(0, 80)});
                        }
                    }
                    if (colorCircles.length === 0) {
                        return {success: false, error: 'Tidak ada bulatan warna ditemukan', count: 0};
                    }
                    const idx = Math.max(0, Math.min(targetIndex, colorCircles.length - 1));
                    colorCircles[idx].el.click();
                    return {
                        success: true, 
                        count: colorCircles.length, 
                        clicked: idx,
                        style: colorCircles[idx].style
                    };
                }""", index)
                
                if clicked.get("success"):
                    break
                time.sleep(0.5)
            
            if clicked.get("success"):
                print(f"\t[+] Memilih warna ke-{clicked['clicked'] + 1}...")
                time.sleep(random.uniform(2.0, 3.5))
                return True
            else:
                print(f"\t[!] {clicked.get('error', 'Gagal')}.")
                return False
        except Exception as e:
            print(f"\t[!] Gagal memilih background warna: {e}")
            return False

    def post_to_single_group(self, group: dict) -> str:
        content = self.get_random_content()
        text = content["text"]
        image = content["image"]
        background_idx = content.get("background_index", None)

        group_url = group['username']
        if not group_url.startswith("http"):
            group_url = f"https://facebook.com/groups/{group_url}"
        
        self.page.goto(group_url, wait_until="domcontentloaded", timeout=30000)
        
        try:
            import re
            current_url = self.page.url
            match = re.search(r"facebook\.com/groups/([^/?]+)", current_url)
            if match:
                group['username'] = match.group(1)
        except Exception:
            pass
        
        if not group.get("name") or group["name"] == group["username"]:
            try:
                title = self.page.title() or ""
                group["name"] = title.split(" | ")[0].strip() if " | " in title else title.strip()
                if not group["name"]:
                    group["name"] = group["username"]
            except Exception:
                group["name"] = group["username"]
            
            for rg in self.realtime_statuses:
                if rg["username"] == group["username"]:
                    rg["name"] = group["name"]
                    break
            self.send_discord_webhook(self.current_cycle, extra_info="Fase: Autoposting ke Grup")

        write_selectors = [
            '//span[contains(text(), "Write something")]',
            '//span[contains(text(), "Tulis sesuatu")]',
            '//span[contains(text(), "Apa yang Anda pikirkan")]',
            '//span[contains(text(), "What\'s on your mind")]',
        ]
        write_btn = None
        for sel in write_selectors:
            try:
                el = self.page.wait_for_selector(sel, timeout=5000)
                if el:
                    write_btn = el
                    break
            except Exception:
                continue
        
        if not write_btn:
            raise Exception("Tombol 'Write something...' tidak ditemukan di halaman grup ini.")
        
        write_btn.click()
        
        delay = random.randint(3, 8)
        print(f"\t[*] Jeda aman: Menunggu {delay} detik...")
        time.sleep(delay)

        if background_idx is not None and not image:
            idx = int(background_idx) - 1
            self.select_facebook_background(idx)

        if text:
            print(f"\t[+] Mengetik status...")
            editor = self.page.wait_for_selector("//div[@role='dialog']//div[@contenteditable='true']")
            editor.click()
            time.sleep(0.5)
            editor.type(text, delay=TYPING_DELAY)

            try:
                autocomplete = self.page.locator("//div[@role='dialog']//div[@role='listbox'] | //div[@role='dialog']//ul[@role='listbox'] | //div[@role='listbox']")
                if autocomplete.count() > 0 and autocomplete.first.is_visible():
                    print("\t[!] Popup autocomplete/mention terdeteksi, menekan Escape untuk menutup...")
                    editor.press("Escape")
            except Exception:
                pass

        if image:
            if isinstance(image, list):
                resolved = [path.join(PROJECT_ROOT, f) if not path.isabs(f) else f for f in image]
                valid = all(path.exists(f) for f in resolved)
            else:
                resolved = path.join(PROJECT_ROOT, image) if not path.isabs(image) else image
                valid = path.exists(resolved)

            if valid:
                print(f"\t[+] Mengunggah gambar...")
                self.page.set_input_files("//div[@role='dialog']//input[@type='file']", resolved)
                print(f"\t[*] Jeda aman (upload): Menunggu 5 detik...")
                time.sleep(5)
            else:
                print(f"\t[!] File gambar tidak ditemukan: {resolved}, memposting tanpa gambar")

        try:
            post_btn = self.page.locator("[role='dialog']").get_by_role("button", name="Post", exact=True)
            if post_btn.count() > 0:
                post_btn.first.click()
                print("\t[+] Tombol Post diklik.")
            else:
                self.page.wait_for_selector("//div[@role='dialog']//div[@aria-label='Post']", timeout=10000).click()
                print("\t[+] Tombol Post diklik (via XPath fallback).")
        except Exception as e:
            print(f"\t[!] Gagal mengklik tombol Post: {e}")
            try:
                self.page.locator("//div[@role='dialog']//*[@role='button']//*[contains(text(), 'Post')]").first.click()
                print("\t[+] Tombol Post diklik (via text contains fallback).")
            except Exception as e2:
                raise Exception(f"Tombol Post tidak dapat diklik: {e2}")
        
        try:
            dialog = self.page.locator("//div[@role='dialog']").first
            dialog.wait_for(state="hidden", timeout=15000)
            print("\t[+] Postingan selesai diproses (dialog tertutup).")
        except Exception as e:
            print(f"\t[!] Peringatan: Dialog postingan tidak tertutup otomatis: {e}")
            time.sleep(5)
        
        self.page.wait_for_load_state("domcontentloaded")

        needs_approval = self.detect_pending_approval()
        if needs_approval:
            print(f"\t[!] Grup ini membutuhkan persetujuan admin. Ditandai untuk di-skip di siklus berikutnya.")
            self.pending_approval.add(group['username'])
            return "pending"
        else:
            self.pending_approval.discard(group['username'])
            return "success"

    def detect_pending_approval(self) -> bool:
        try:
            page_text = self.page.evaluate("""() => {
                let text = "";
                const main = document.querySelector('[role="main"]');
                if (main) text += main.innerText + "\\n";
                const alerts = document.querySelectorAll('[role="alert"], [role="status"], div[class*="toast"]');
                alerts.forEach(el => { text += el.innerText + "\\n"; });
                return text;
            }""")
            pending_keywords = [
                "submitted for admin",
                "pending approval",
                "pending review",
                "awaiting approval",
                "submitted to admin",
                "menunggu persetujuan",
                "sedang ditinjau",
                "menunggu moderasi",
                "ditinjau oleh admin",
            ]
            text_lower = page_text.lower()
            for keyword in pending_keywords:
                if keyword in text_lower:
                    return True
            return False
        except Exception:
            return False

    def check_pending_approved(self, group: dict) -> bool:
        try:
            print(f"\t[*] Mengecek status persetujuan admin...")
            group_url = group['username']
            if not group_url.startswith("http"):
                group_url = f"https://facebook.com/groups/{group_url}"
            self.page.goto(group_url, wait_until="domcontentloaded", timeout=30000)

            if not group.get("name") or group["name"] == group["username"]:
                try:
                    title = self.page.title() or ""
                    group["name"] = title.split(" | ")[0].strip() if " | " in title else title.strip()
                    if not group["name"]:
                        group["name"] = group["username"]
                except Exception:
                    group["name"] = group["username"]
                
                for rg in self.realtime_statuses:
                    if rg["username"] == group["username"]:
                        rg["name"] = group["name"]
                        break
                self.send_discord_webhook(self.current_cycle, extra_info="Fase: Autoposting ke Grup")

            time.sleep(random.uniform(3.0, 6.0))

            page_text = self.page.evaluate("""() => {
                let text = "";
                const main = document.querySelector('[role="main"]');
                if (main) text += main.innerText + "\\n";
                const alerts = document.querySelectorAll('[role="alert"], [role="status"], div[class*="toast"]');
                alerts.forEach(el => { text += el.innerText + "\\n"; });
                return text;
            }""")
            text_lower = page_text.lower()
            
            pending_indicators = [
                "pending post", "pending review", "awaiting approval",
                "post is pending", "submitted for review",
                "menunggu persetujuan", "sedang ditinjau",
            ]
            
            for indicator in pending_indicators:
                if indicator in text_lower:
                    print(f"\t[!] Post sebelumnya MASIH menunggu persetujuan admin.")
                    return False
            
            print(f"\t[V] Post sebelumnya sudah di-approve! Lanjut posting baru.")
            return True

        except Exception as e:
            print(f"\t[!] Gagal cek status approval: {e}")
            return False

    def post_to_groups(self, cycle=1):
        self.current_cycle = cycle
        groups = get_sources_list()
        
        if SHUFFLE_GROUPS:
            groups = groups.copy()
            random.shuffle(groups)
            print("[*] Urutan grup diacak (SHUFFLE_GROUPS = True)")
            
        total = len(groups)

        self.realtime_statuses = []
        for g in groups:
            self.realtime_statuses.append({
                "name": g.get("name") or g["username"],
                "username": g["username"],
                "status": "waiting"
            })

        pending_count = len([g for g in groups if g['username'] in self.pending_approval])

        print("=" * 50)
        print(f"[*] Memulai posting ke {total} grup")
        print(f"[*] Delay antar grup: {DELAY_MIN}-{DELAY_MAX} detik")
        print(f"[*] Max retry per grup: {MAX_RETRIES}x")
        print(f"[*] Variasi konten tersedia: {len(get_contents_list())} template")
        if pending_count > 0:
            print(f"[*] Grup menunggu approval admin: {pending_count}")
        print("=" * 50)

        self.send_discord_webhook(cycle, extra_info="Fase: Autoposting ke Grup")

        for i, group in enumerate(groups, 1):
            print(f"\n[{i}/{total}] Posting ke: {group['name'] or group['username']}")

            self.realtime_statuses[i - 1]["status"] = "processing"
            self.realtime_statuses[i - 1]["name"] = group["name"] or group["username"]
            self.send_discord_webhook(cycle, extra_info="Fase: Autoposting ke Grup")

            if group['username'] in self.pending_approval:
                approved = self.check_pending_approved(group)
                if not approved:
                    print(f"\t[SKIP] Post sebelumnya belum di-approve admin. Skip grup ini.")
                    self.results["skipped"].append(group["name"] or group["username"])
                    
                    self.realtime_statuses[i - 1]["status"] = "skipped"
                    self.realtime_statuses[i - 1]["name"] = group["name"] or group["username"]
                    self.send_discord_webhook(cycle, extra_info="Fase: Autoposting ke Grup")
                    continue
                else:
                    self.pending_approval.discard(group['username'])

            success_status = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    if attempt > 1:
                        print(f"\t[Retry] Retry ke-{attempt}/{MAX_RETRIES}...")
                        time.sleep(random.randint(10, 30))

                    status_res = self.post_to_single_group(group)
                    if status_res in ["success", "pending"]:
                        print(f"\t[OK] Berhasil diposting (status: {status_res})!")
                        if status_res == "success":
                            self.results["success"].append(group["name"] or group["username"])
                        else:
                            self.results["skipped"].append(group["name"] or group["username"])
                        success_status = status_res
                        break
                except Exception as e:
                    print(f"\t[FAIL] Gagal (attempt {attempt}/{MAX_RETRIES}): {e}")

            if success_status == "success":
                self.realtime_statuses[i - 1]["status"] = "success"
                self.realtime_statuses[i - 1]["name"] = group["name"]
            elif success_status == "pending":
                self.realtime_statuses[i - 1]["status"] = "skipped"
                self.realtime_statuses[i - 1]["name"] = group["name"]
            else:
                print(f"\t[FAIL] GAGAL setelah {MAX_RETRIES}x percobaan. Skip grup ini.")
                self.results["failed"].append(group["name"] or group["username"])
                self.realtime_statuses[i - 1]["status"] = "failed"
                self.realtime_statuses[i - 1]["name"] = group["name"] or group["username"]

            self.send_discord_webhook(cycle, extra_info="Fase: Autoposting ke Grup")

            if i < total:
                post_delay = random.randint(DELAY_MIN, DELAY_MAX)
                print(f"\n[*] Menunggu {post_delay} detik sebelum posting ke grup berikutnya...")
                self.send_discord_webhook(cycle, extra_info=f"Waiting <t:{int(time.time() + post_delay)}:R>")
                time.sleep(post_delay)

    def send_discord_webhook(self, cycle=1, extra_info=""):
        if not DISCORD_WEBHOOK_URL:
            return

        success_count = sum(1 for g in self.realtime_statuses if g["status"] == "success")
        failed_count = sum(1 for g in self.realtime_statuses if g["status"] == "failed")
        skipped_count = sum(1 for g in self.realtime_statuses if g["status"] == "skipped")

        now_str = datetime.now().strftime("%a %b %d %Y, %H:%M:%S")

        any_processing = any(g["status"] == "processing" for g in self.realtime_statuses)
        any_waiting = any(g["status"] == "waiting" for g in self.realtime_statuses)
        
        if any_processing or any_waiting:
            state_color, state_text = "36", "Running"
            embed_color = 3718648
        elif failed_count > 0:
            state_color, state_text = "31", "Finished (With Failures)"
            embed_color = 16281969
        else:
            state_color, state_text = "32", "Finished (Success)"
            embed_color = 3462041

        state_rows = [
            f"- STATUS      \u001b[1;{state_color}m◉\u001b[0m \u001b[2;{state_color}m{state_text}\u001b[0m",
            f"- CYCLE       \u001b[1;37m◉\u001b[0m \u001b[2;37m{cycle}\u001b[0m",
            f"- PROGRESS    \u001b[1;32m◉\u001b[0m \u001b[2;32m{success_count}\u001b[0m  \u001b[1;31m◉\u001b[0m \u001b[2;31m{failed_count}\u001b[0m  \u001b[1;33m◉\u001b[0m \u001b[2;33m{skipped_count}\u001b[0m"
        ]

        terminal_state = "\u001b[1;36m── STATE ──────────────────────────────────\u001b[0m\n" + "\n".join(state_rows)

        INDEX_W = 2
        LABEL_W = 12

        def _ansi_row(idx_val: int, name: str, color: str, status_text: str) -> str:
            if len(name) > LABEL_W:
                name = name[:LABEL_W - 1] + "…"
            idx = str(idx_val).zfill(INDEX_W).rjust(INDEX_W)
            label = name.ljust(LABEL_W)
            return (
                f"\u001b[2;37m{idx}\u001b[0m "
                f"\u001b[0;37m{label}\u001b[0m "
                f"\u001b[1;{color}m◉\u001b[0m "
                f"\u001b[2;{color}m{status_text}\u001b[0m"
            )

        group_rows = []
        for i, g in enumerate(self.realtime_statuses, 1):
            status = g["status"]
            name = g["name"]
            if status == "success":
                row_color, row_desc = "32", "Success"
            elif status == "failed":
                row_color, row_desc = "31", "Failed"
            elif status == "skipped":
                row_color, row_desc = "33", "Skip (Admin)"
            elif status == "processing":
                row_color, row_desc = "36", "Processing..."
            else:
                row_color, row_desc = "37", "Queued"
            group_rows.append(_ansi_row(i, name, row_color, row_desc))

        terminal_groups = "\n\u001b[1;36m── GROUP STATUS ───────────────────────────\u001b[0m\n" + "\n".join(group_rows)
        terminal_block = f"```ansi\n{terminal_state}\n{terminal_groups}\n```"

        description_text = terminal_block
        if extra_info:
            description_text += f"\n⏳ **Status:** {extra_info}"

        payload = {
            "username": "FB Auto Poster",
            "embeds": [
                {
                    "description": description_text,
                    "color": embed_color,
                    "footer": {
                        "text": f"Last Updated: {now_str}"
                    }
                }
            ]
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            
            if self.last_webhook_msg_id:
                parsed_url = urlparse(DISCORD_WEBHOOK_URL)
                path_parts = parsed_url.path.rstrip("/").split("/")
                new_path = "/".join(path_parts) + f"/messages/{self.last_webhook_msg_id}"
                
                query_params = parsed_url.query
                webhook_url = urlunparse((
                    parsed_url.scheme,
                    parsed_url.netloc,
                    new_path,
                    parsed_url.params,
                    query_params,
                    parsed_url.fragment
                ))
                
                req = urllib.request.Request(
                    webhook_url,
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                    method="PATCH"
                )
                with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
                    pass
            else:
                webhook_url = DISCORD_WEBHOOK_URL + ("&" if "?" in DISCORD_WEBHOOK_URL else "?") + "wait=true"
                req = urllib.request.Request(
                    webhook_url,
                    data=data,
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
                )
                with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    self.last_webhook_msg_id = resp_data.get("id")
                    self.save_webhook_message_id()
                print("[+] Laporan terkirim ke Discord (Pesan Baru)!")
        except urllib.error.HTTPError as e:
            print(f"[-] Gagal kirim ke Discord (HTTP Error {e.code}): {e.read().decode('utf-8', errors='ignore')}")
            if e.code == 404:
                self.last_webhook_msg_id = None
                self.delete_webhook_message_id_file()
        except Exception as e:
            print(f"[-] Gagal kirim ke Discord: {e}")
            if self.last_webhook_msg_id:
                self.last_webhook_msg_id = None

    def save_webhook_message_id(self):
        try:
            with open(self.webhook_id_file, "w") as f:
                json.dump({"message_id": self.last_webhook_msg_id}, f)
        except Exception as e:
            print(f"[-] Gagal menyimpan ID pesan webhook: {e}")

    def delete_webhook_message_id_file(self):
        try:
            if path.exists(self.webhook_id_file):
                import os
                os.remove(self.webhook_id_file)
        except Exception:
            pass

    def send_cookie_expired_webhook(self, cycle):
        if not DISCORD_WEBHOOK_URL:
            return

        now_str = datetime.now().strftime("%a %b %d %Y, %H:%M:%S")

        payload = {
            "username": "FB Auto Poster",
            "embeds": [
                {
                    "title": "⚠️ Cookie Facebook Expired!",
                    "description": f"Sesi Facebook Anda telah berakhir pada **Siklus ke-{cycle}**.\n\n**Tindakan yang Diperlukan:**\nSilakan ekspor cookie baru dari browser Anda dan simpan ke folder `sessions/` untuk melanjutkan.",
                    "color": 15181212,
                    "footer": {
                        "text": f"FB Auto Poster | {now_str}"
                    }
                }
            ]
        }

        try:
            data = json.dumps(payload).encode("utf-8")
            webhook_url = DISCORD_WEBHOOK_URL
            req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            urllib.request.urlopen(req, context=SSL_CONTEXT)
            print("[+] Notifikasi cookie expired terkirim ke Discord!")
        except Exception as e:
            print(f"[-] Gagal kirim notifikasi: {e}")

    def check_cookie_valid(self) -> bool:
        print("[*] Mengecek validitas cookie...")
        try:
            self.page.goto("https://www.facebook.com/me", wait_until="domcontentloaded", timeout=8000)
            current_url = self.page.url

            try:
                title = self.page.title() or ""
                if title:
                    if "|" in title:
                        self.user_name = title.split("|")[0].strip()
                    elif "Facebook" not in title:
                        self.user_name = title.strip()
                    if self.user_name:
                        print(f"[V] Nama pengguna terdeteksi: {self.user_name}")
            except Exception:
                pass

            if "login" in current_url or "checkpoint" in current_url or "recover" in current_url:
                print("[X] Cookie expired! Diarahkan ke halaman login.")
                return False

            try:
                self.page.wait_for_selector("//div[@role='banner'] | //a[@aria-label='Facebook'] | //div[@aria-label='Facebook']", timeout=3000)
                print("[V] Cookie masih valid!")
                return True
            except Exception:
                if "facebook.com/me" in current_url or len(self.page.context.cookies()) > 2:
                    print("[V] Cookie masih valid (verified via context)!")
                    return True
                print("[X] Cookie tidak valid.")
                return False

        except Exception as e:
            print(f"[X] Gagal mengecek cookie: {e}")
            return False

    def load_cookie(self) -> None:
        possible_paths = [
            f"{PROJECT_ROOT}/sessions/{SOCIAL_MAPS['facebook']['filename']}",
            f"{PROJECT_ROOT}/sessions/cookies.json",
            f"{PROJECT_ROOT}/sessions/facebook.json",
        ]
        
        file_path = None
        for p in possible_paths:
            if path.exists(p):
                file_path = p
                break

        if not file_path:
            print(f"[-] File cookie tidak ditemukan di: {possible_paths[0]}")
            print("[-] Silakan export cookie dari browser Anda dan simpan di folder sessions/.")
            exit()

        self.page.goto(SOCIAL_MAPS["facebook"]["login"])
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                raw_cookies = json.loads(f.read())
            except Exception as e:
                print(f"[!] Error membaca file JSON cookie: {e}")
                print("[!] Pastikan format yang di-paste adalah JSON (dimulai dengan [ dan diakhiri dengan ]).")
                exit()
            
            if isinstance(raw_cookies, dict) and "data" in raw_cookies:
                print("[!] Anda mengunduh format 'Backup' (terenkripsi) dari Cookie-Editor!")
                print("[!] Silakan ulangi export, pilih menu 'Export' lalu klik 'JSON'.")
                exit()

            if not isinstance(raw_cookies, list):
                print("[!] Format cookie salah. Harus berupa list JSON (diawali dengan '[' dan diakhiri dengan ']').")
                exit()
            
            cookies = []
            for c in raw_cookies:
                playwright_cookie = {
                    "name": str(c.get("name")),
                    "value": str(c.get("value")),
                    "domain": str(c.get("domain")),
                    "path": str(c.get("path", "/")),
                    "httpOnly": bool(c.get("httpOnly", False)),
                    "secure": bool(c.get("secure", False)),
                }
                
                if "expires" in c:
                    playwright_cookie["expires"] = c["expires"]
                elif "expirationDate" in c:
                    playwright_cookie["expires"] = c["expirationDate"]
                
                same_site = c.get("sameSite")
                if same_site:
                    same_site_str = str(same_site).lower()
                    if "no_restriction" in same_site_str or "none" in same_site_str:
                        playwright_cookie["sameSite"] = "None"
                    elif "lax" in same_site_str:
                        playwright_cookie["sameSite"] = "Lax"
                    elif "strict" in same_site_str:
                        playwright_cookie["sameSite"] = "Strict"
                
                cookies.append(playwright_cookie)
                
            self.context.add_cookies(cookies)

if __name__ == "__main__":
    FacebookGroupSpam()
