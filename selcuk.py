import re
import sys
import time
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

# --- YENİ ---
# Güncel adresi bulmak için kullanılacak portal adresi
PORTAL_DOMAIN = "https://www.selcuksportshd.is/"

# --- YENİ FONKSİYON: GÜNCEL DOMAIN'İ BULMA ---
def find_working_domain(page):
    """
    Portal sayfasını ziyaret eder ve 'a.site-button' class'ına sahip
    elementin href özelliğinden güncel domain'i çeker.
    """
    print(f"\n🔎 Güncel domain {PORTAL_DOMAIN} adresinden alınıyor...")
    try:
        page.goto(PORTAL_DOMAIN, timeout=20000, wait_until='domcontentloaded')
        
        # Sizin belirttiğiniz CSS seçici
        selector = "a.site-button"
        page.wait_for_selector(selector, timeout=10000)
        
        link_element = page.query_selector(selector)
        
        if not link_element:
             print("-> ❌ Portal sayfasında 'a.site-button' elementi bulunamadı.")
             return None
        
        domain = link_element.get_attribute('href')
        
        if not domain:
            print("-> ❌ Link elementinde 'href' özelliği bulunamadı.")
            return None

        # Domain'i temizle (sonundaki '/' karakterini kaldır)
        domain = domain.rstrip('/')
        print(f"✅ Güncel domain başarıyla bulundu: {domain}")
        return domain
        
    except Exception as e:
        print(f"❌ Portal sayfasına ulaşılamadı veya domain alınamadı: {e.__class__.__name__}")
        return None

# --- GÜNCELLENEN FONKSİYON: KANAL GRUPLAMA MANTIĞI ---
def get_channel_group(channel_name):
    """
    Verilen kanal ismine göre bir grup adı döndürür.
    """
    channel_name_lower = channel_name.lower()
    group_mappings = {
        'BeinSports': ['bein sports', 'beın sports'],
        'S Sports': ['s sport'],
        'Tivibu': ['tivibu spor'],
        'Ulusal Kanallar': ['a spor', 'trt spor', 'trt 1'],
        'Diğer Spor': ['smart spor', 'nba tv', 'eurosport'],
        'Belgesel': ['national geographic', 'nat geo', 'discovery', 'dmax', 'bbc earth', 'history'],
        'Film & Dizi': ['bein series', 'bein movies', 'movie smart']
    }
    for group, keywords in group_mappings.items():
        for keyword in keywords:
            if keyword in channel_name_lower:
                return group
    return "Maç Yayınları"

# --- GÜNCELLENEN FONKSİYON: ARTIK DOMAIN PARAMETRESİ ALIYOR ---
def scrape_channel_links(page, domain_to_scrape):
    """
    Selçuk Sports ana sayfasını ziyaret eder ve tüm kanalları
    isim, URL ve grup bilgisiyle birlikte toplar.
    """
    print(f"\n📡 Kanallar {domain_to_scrape} adresinden çekiliyor...")
    channels = []
    try:
        page.goto(domain_to_scrape, timeout=25000, wait_until='domcontentloaded')
        
        link_elements = page.query_selector_all("a[data-url]")
        
        if not link_elements:
            print("❌ Ana sayfada 'data-url' içeren hiçbir kanal linki bulunamadı.")
            return []
            
        for link in link_elements:
            player_url = link.get_attribute('data-url')
            name_element = link.query_selector('div.name')
            
            if name_element and player_url:
                channel_name = name_element.inner_text().strip()
                
                # --- GÜNCELLENDİ: Global değişken yerine parametreyi kullan ---
                if player_url.startswith('/'):
                    base_domain = domain_to_scrape.rstrip('/')
                    player_url = f"{base_domain}{player_url}"
                
                group_name = get_channel_group(channel_name)
                
                channels.append({
                    'name': channel_name,
                    'url': player_url,
                    'group': group_name
                })

        print(f"✅ {len(channels)} adet potansiyel kanal linki bulundu ve gruplandırıldı.")
        return channels
        
    except PlaywrightError as e:
        print(f"❌ Selçuk Sports ana sayfasına ulaşılamadı. Hata: {e.__class__.__name__}")
        return []

def extract_m3u8_from_page(page, player_url):
    """
    Oynatıcı sayfasından M3U8 linkini doğrudan oluşturur.
    """
    try:
        page.goto(player_url, timeout=20000, wait_until="domcontentloaded")
        content = page.content()
        base_url_match = re.search(r"this\.baseStreamUrl\s*=\s*['\"](https?://.*?)['\"]", content)
        if not base_url_match:
            print(" -> ❌ 'baseStreamUrl' bulunamadı.", end="")
            return None
        base_url = base_url_match.group(1)
        
        parsed_url = urlparse(player_url)
        query_params = parse_qs(parsed_url.query)
        stream_id = query_params.get('id', [None])[0]
        if not stream_id:
            print(" -> ❌ 'id' parametresi bulunamadı.", end="")
            return None

        m3u8_link = f"{base_url}{stream_id}/playlist.m3u8"
        return m3u8_link

    except Exception:
        print(" -> ❌ Sayfa yüklenirken hata oluştu.", end="")
        return None

# --- GÜNCELLENEN MAIN FONKSİYONU ---
def main():
    with sync_playwright() as p:
        print("🚀 Playwright ile Selçuk Sports M3U8 Kanal İndirici Başlatılıyor...")
        
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # --- YENİ ADIM: ÖNCE GÜNCEL DOMAIN'İ BUL ---
        selcuksports_domain = find_working_domain(page)

        if not selcuksports_domain:
            print("❌ UYARI: Güncel domain portal sayfasından alınamadı. İşlem sonlandırılıyor.")
            browser.close()
            sys.exit(1)
        # --- BİTTİ ---

        # --- GÜNCELLENDİ: Bulunan domain'i fonksiyona parametre olarak ver ---
        channels = scrape_channel_links(page, selcuksports_domain)

        if not channels:
            print("❌ UYARI: Hiçbir kanal bulunamadı, işlem sonlandırılıyor.")
            browser.close()
            sys.exit(1)
        
        m3u_content = []
        output_filename = "selcuksports_kanallar.m3u8"
        print(f"\n📺 {len(channels)} kanal için M3U8 linkleri işleniyor...")
        created = 0
        
        for i, channel_info in enumerate(channels, 1):
            channel_name = channel_info['name']
            player_url = channel_info['url']
            group_name = channel_info['group']
            
            print(f"[{i}/{len(channels)}] {channel_name} (Grup: {group_name}) işleniyor...", end="")
            
            m3u8_link = extract_m3u8_from_page(page, player_url)
            
            if m3u8_link:
                print(" -> ✅ Link bulundu.")
                m3u_content.append(f'#EXTINF:-1 tvg-name="{channel_name}" group-title="{group_name}",{channel_name}')
                m3u_content.append(m3u8_link)
                created += 1
            else:
                print(" -> ❌ Link bulunamadı.")
        
        browser.close()

        if created > 0:
            header = "#EXTM3U"
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(header + "\n") 
                f.write("\n".join(m3u_content))
            print(f"\n\n📂 {created} kanal başarıyla '{output_filename}' dosyasına kaydedildi.")
        else:
            print("\n\nℹ️  Geçerli hiçbir M3U8 linki bulunamadığı için dosya oluşturulmadı.")

        print("\n" + "="*50)
        print("📊 İŞLEM SONUCLARI")
        print("="*50)
        print(f"✅ Başarıyla oluşturulan link: {created}")
        print(f"❌ Başarısız veya atlanan kanal: {len(channels) - created}")
        print("\n🎉 İşlem başarıyla tamamlandı!")

if __name__ == "__main__":
    main()
