import os
import time
import json
import threading
import requests
import flet as ft
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

class AppState:
    def __init__(self):
        self.loaded_posts = []
        self.current_creator = ""
        self.current_service = ""
        self.is_working = False
        self.current_page = 1
        self.posts_per_page = 100
        self.total_pages = 1

def main(page: ft.Page):
    # Ana mobil (veya APK) ekran yapılandırması
    page.title = "Coomer Downloader Mobile"
    page.theme_mode = ft.ThemeMode.DARK
    page.vertical_alignment = ft.MainAxisAlignment.START
    
    # Bilgisayarda test ederken telefon boyutunda açılsın diye (APK'da tam ekran olur)
    page.window_width = 420
    page.window_height = 800
    
    state = AppState()
    
    def get_headers():
        return {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Nexus/5.0', 'Accept': 'text/css'}

    # ================= LOGS SEKMESİ (TELEFON İÇİN) =================
    log_text = ft.Text(value="Sistem Başlatıldı. Mobil Sürüme Uygun.", color=ft.colors.GREY_400, size=12, selectable=True)
    log_column = ft.ListView(expand=True, spacing=5, auto_scroll=True, controls=[log_text])
    
    def log(msg, color=ft.colors.GREY_400):
        log_column.controls.append(ft.Text(value=msg, color=color, size=12))
        page.update()

    # ================= SEARCH SEKMESİ =================
    search_input = ft.TextField(label="Kullanıcı Adı Girin", expand=True)
    
    def search_creators(e):
        if state.is_working: return
        query = search_input.value.strip().lower()
        if not query:
            log("Lütfen bir kullanıcı adı girin.", ft.colors.RED_400)
            return
            
        state.is_working = True
        log(f"'{query}' için veri tabanı taranıyor...", ft.colors.PURPLE_ACCENT)
        creator_list.controls.clear()
        page.update()
        
        def _bg_search():
            try:
                url = "https://coomer.st/api/v1/creators"
                res = requests.get(url, headers=get_headers(), timeout=15)
                if res.status_code != 200:
                    log(f"API Engeli: HTTP {res.status_code}", ft.colors.RED_400)
                    state.is_working = False; page.update(); return
                
                data = json.loads(res.text)
                clean_q = query.replace(" ", "")
                matches = [u for u in data if clean_q in u.get('name','').lower().replace(" ","") or clean_q in u.get('id','').lower().replace(" ","")]
                
                matches.sort(
                    key=lambda x: (clean_q == x.get('name','').lower().replace(" ","") or clean_q == x.get('id','').lower().replace(" ",""), x.get('favorited',0)),
                    reverse=True
                )
                
                if len(matches) > 100: matches = matches[:100]
                
                if not matches:
                    log("Arama sonucu bulunamadı.", ft.colors.RED_400)
                else:
                    log(f"{len(matches)} kullanıcı bulundu.", ft.colors.GREEN_400)
                    for c in matches:
                        name = c.get('name', 'Bilinmeyen')
                        service = c.get('service', 'Bilinmeyen')
                        cid = c.get('id', '')
                        btn = ft.ElevatedButton(
                            text=f"{name} ({service})",
                            on_click=lambda e, i=cid, s=service: fetch_posts(i, s)
                        )
                        creator_list.controls.append(btn)
            except Exception as ex:
                log(f"Arama hatası: {ex}", ft.colors.RED_400)
            
            state.is_working = False
            page.update()

        threading.Thread(target=_bg_search, daemon=True).start()

    search_btn = ft.ElevatedButton("Ara", on_click=search_creators, bgcolor=ft.colors.PURPLE)
    creator_list = ft.ListView(expand=True, spacing=10)
    
    # ================= POSTS SEKMESİ =================
    post_list = ft.ListView(expand=True, spacing=5)
    page_text = ft.Text("Sayfa 1/1")
    post_count_text = ft.Text("Seçim Yapılmadı", color=ft.colors.GREY_300)
    
    select_all_chb = ft.Checkbox(label="Tümünü Seç", value=True, on_change=lambda e: toggle_all(e))
    
    def toggle_all(e):
        val = select_all_chb.value
        for p in state.loaded_posts:
            p["var"] = val
            p["checkbox"].value = val
        page.update()

    def fetch_posts(cid, service):
        if state.is_working: return
        state.is_working = True
        log(f"@{cid} kullanıcısının verileri çekiliyor...", ft.colors.GREY_400)
        tabs.selected_index = 1 # Gönderiler tab'ına atla
        post_list.controls.clear()
        page.update()
        
        def _bg_fetch():
            base_url = "https://coomer.st"
            offset = 0
            all_posts = []
            
            while True:
                api_url = f"{base_url}/api/v1/{service}/user/{cid}/posts?o={offset}"
                success = False
                stream_ended = False
                for att in range(3):
                    try:
                        res = requests.get(api_url, headers=get_headers(), timeout=15)
                        if res.status_code in [400, 404]: stream_ended=True; success=True; break
                        if res.status_code != 200: time.sleep(2); continue
                        posts = json.loads(res.text)
                        if not posts: stream_ended=True; success=True; break
                        all_posts.extend(posts)
                        offset += 50
                        log(f"Sayfa {offset} indiriliyor...", ft.colors.GREEN_400)
                        post_count_text.value = f"{len(all_posts)} gönderi bulundu..."
                        page.update()
                        success = True
                        break
                    except:
                        time.sleep(3)
                if stream_ended or not success:
                    break
            
            log(f"Toplam {len(all_posts)} gönderi analiz edildi.", ft.colors.PURPLE_ACCENT)
            state.current_creator = cid
            state.current_service = service
            
            state.loaded_posts.clear()
            for p in all_posts:
                m_items = []
                if p.get("file") and p.get("file").get("path"): m_items.append(p["file"])
                for att in p.get("attachments", []):
                    if att.get("path"): m_items.append(att)
                if not m_items: continue
                title = p.get("title", "İsimsiz") or "İsimsiz"
                if len(title) > 30: title = title[:27] + "..."
                
                def make_chb():
                    cb = ft.Checkbox(label=f"{title} ({len(m_items)} Medya)", value=True)
                    return cb
                
                chb = make_chb()
                state.loaded_posts.append({"title": title, "media": m_items, "var": True, "checkbox": chb})
            
            state.total_pages = max(1, math.ceil(len(state.loaded_posts) / state.posts_per_page))
            state.current_page = 1
            render_page()
            state.is_working = False
            page.update()

        threading.Thread(target=_bg_fetch, daemon=True).start()

    def render_page():
        post_list.controls.clear()
        start = (state.current_page - 1) * state.posts_per_page
        end = min(start + state.posts_per_page, len(state.loaded_posts))
        
        for p in state.loaded_posts[start:end]:
            def cb_change(e, post=p): post["var"] = e.control.value 
            p["checkbox"].on_change = cb_change
            post_list.controls.append(p["checkbox"])
            
        page_text.value = f"Sayfa {state.current_page}/{state.total_pages}"
        post_count_text.value = f"Toplam {len(state.loaded_posts)} Gönderi"
        
    def prev_pg(e):
        if state.is_working or state.current_page <= 1: return
        state.current_page -= 1
        render_page()
        page.update()
        
    def next_pg(e):
        if state.is_working or state.current_page >= state.total_pages: return
        state.current_page += 1
        render_page()
        page.update()

    # ================= DOWNLOAD SEKMESİ =================
    progress_bar = ft.ProgressBar(value=0, color=ft.colors.GREEN_400)
    progress_text = ft.Text("Bekliyor")
    
    def start_download(e):
        if state.is_working: return
        sel = []
        for p in state.loaded_posts:
            if p["var"]: sel.extend(p["media"])
        if not sel:
            log("Lütfen en az bir gönderi seçin.", ft.colors.RED_400)
            return
            
        state.is_working = True
        tabs.selected_index = 2 # Terminal sekmesi
        page.update()
        
        def _bg_down():
            cid = state.current_creator
            base_url = "https://coomer.st"
            save_folder = os.path.join(os.getcwd(), cid)
            photos = os.path.join(save_folder, "photos")
            videos = os.path.join(save_folder, "videos")
            for f in [save_folder, photos, videos]: os.makedirs(f, exist_ok=True)
            
            total = len(sel)
            log(f">> Toplam {total} medya indirmesi başlatıldı...", ft.colors.PURPLE)
            dl_count = 0
            
            def dl_single(info):
                path_str = info.get("path","")
                url = path_str if path_str.startswith("http") else f"{base_url}{path_str}"
                name = "".join(c for c in (info.get("name","") or path_str.split("/")[-1]) if c.isalnum() or c in ".-_ ")
                if not name: name = f"nexus_file_{time.time()}.bin"
                ext = "."+name.split(".")[-1].lower() if "." in name else ""
                tf = videos if ext in [".mp4",".mov",".avi",".wmv",".webm",".mkv"] else photos
                fpath = os.path.join(tf, name)
                
                if os.path.exists(fpath): return "exists", name
                last_err = ""
                for att in range(3):
                    try:
                        r = requests.get(url, stream=True, headers=get_headers(), timeout=45)
                        if r.status_code == 200:
                            with open(fpath, 'wb') as fl:
                                for chunk in r.iter_content(chunk_size=1024*1024):
                                    if chunk: fl.write(chunk)
                            return "ok", name
                        time.sleep(2)
                    except Exception as ex:
                        last_err=str(ex)
                        time.sleep(2)
                return last_err, name

            with ThreadPoolExecutor(max_workers=3) as x:
                futs = {x.submit(dl_single, item): item for item in sel}
                for f in as_completed(futs):
                    dl_count+=1
                    s, n = f.result()
                    if s=="ok": log(f"✓ {n}", ft.colors.GREEN_400)
                    elif s=="exists": log(f"~ {n} (Zaten Var)", ft.colors.AMBER_400)
                    else: log(f"X {n} ({s})", ft.colors.RED_400)
                    progress_bar.value = dl_count/total
                    progress_text.value = f"% {int((dl_count/total)*100)} ({dl_count} / {total})"
                    page.update()
            
            log("TÜM İNDİRMELER BİTTİ.", ft.colors.PURPLE_ACCENT)
            state.is_working = False
            page.update()

        threading.Thread(target=_bg_down, daemon=True).start()

    download_btn = ft.ElevatedButton("SEÇİLENLERİ İNDİR", on_click=start_download, bgcolor=ft.colors.GREEN_800, color=ft.colors.WHITE, width=400, height=50)

    # ================= SAYFA YERLEŞİMİ (TABS) =================
    search_tab = ft.Tab("🔍 Arama", content=ft.Column([
        ft.Row([search_input, search_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        creator_list
    ], spacing=10))
    
    posts_tab = ft.Tab("📂 Dosyalar", content=ft.Column([
        ft.Row([select_all_chb, post_count_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Row([ft.IconButton(ft.icons.ARROW_BACK, on_click=prev_pg), page_text, ft.IconButton(ft.icons.ARROW_FORWARD, on_click=next_pg)], alignment=ft.MainAxisAlignment.CENTER),
        post_list,
        download_btn
    ], spacing=10))
    
    logs_tab = ft.Tab("⚙️ Terminal", content=ft.Column([
        progress_text, progress_bar,
        log_column
    ], spacing=10))

    tabs = ft.Tabs(selected_index=0, tabs=[search_tab, posts_tab, logs_tab], expand=True)
    page.add(ft.Container(content=tabs, expand=True, padding=5))

if __name__ == "__main__":
    ft.app(target=main)
