import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.image as mpimg
import numpy as np
import os
import sys
import requests
import shutil
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
from io import BytesIO

# Add project root to path for core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.paths import get_data_path, VISUALS_DIR, ASSETS_DIR, PROJECT_ROOT
try:
    from core import config
except ImportError:
    config = None

# ==========================================
# ⚙️ AYARLAR
# ==========================================
RAW_DATA_FILE = get_data_path("2_data_final.json")
AI_DATA_FILE = get_data_path("3_results.json")
OUTPUT_DIR = VISUALS_DIR
IMG_CACHE_DIR = os.path.join(ASSETS_DIR, "images_cache")

WIDTH = 1080
HEIGHT = 1350
fighter_images_cache = {}

# Versus: arka plan = _versus_background_rgb() (vektör split + vignette) + isteğe bağlı
# assets/ticket_backgrounds/bg_*.png çok düşük opaklıkta. Hayalet portreler varsayılan kapalı (okunabilirlik).
VERSUS_USE_FIGHTER_GHOST_BG = False
VERSUS_TICKET_BG_BLEND = 0.2
# Tam ekran versus_bg.png ile karışım (ensure_versus_overlay_png üretir)
VERSUS_BG_PNG_BLEND = 0.72
# ensure_versus_overlay_png çıktısı değişince artır → bir kez yeniden üretilir
VERSUS_OVERLAY_GENERATION = 3

_BUNDLED_FONT_PATHS = {
    "headline": os.path.join(ASSETS_DIR, "fonts", "BebasNeue-Regular.ttf"),
    "body_bold": os.path.join(ASSETS_DIR, "fonts", "Roboto-Bold.ttf"),
    "body_regular": os.path.join(ASSETS_DIR, "fonts", "Roboto-Regular.ttf"),
}

try:
    sys.stdout.reconfigure(encoding='utf-8')
except: pass

# 🎨 RENK PALETİ
COLORS = {
    "bg": "#0a0a0a", "text": "#ffffff", "accent": "#00ffff",
    "f1": "#00ff41", "f1_fill": "#00ff4133",
    "f2": "#ff0055", "f2_fill": "#ff005533",
    "primary": "#00FF41",
    "secondary": "#FFD700",
    "bg_card": "#1a1a1a",
    "text_white": "#FFFFFF",
    "text_light": "#EEEEEE",
    "text_dark": "#AAAAAA",
    "grid": "#444444",
    "card_bg": "#080808",
    "bar_fill": "#FFD700",
    "bar_empty": "#222222",
    "bar_text_label": "#CCCCCC",
    "bar_text_score": "#FFFFFF",
    "record_text": "#AAAAAA"
}

# ==========================================
# 🛠️ YARDIMCI FONKSİYONLAR
# ==========================================
def clean_visuals_folder():
    if os.path.exists(OUTPUT_DIR):
        print(f"🧹 Cleaning old visuals in '{OUTPUT_DIR}/'...")
        for filename in os.listdir(OUTPUT_DIR):
            file_path = os.path.join(OUTPUT_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path): os.unlink(file_path)
                elif os.path.isdir(file_path): shutil.rmtree(file_path)
            except: pass

def load_font(font_key, size, fallback_bold=True):
    """TTF yükleme: config → paket fontları (tüm yedekler) → Win/Linux sistem → default.

    Yalnızca OSError değil; bozuk TTF / fonttools edge case için Exception yakalanır.
    Bilinmeyen font_key için bile Bebas/Roboto sırası denenir.
    """
    size = max(8, int(size))
    candidates = []
    if config and hasattr(config, "FONT_PATHS"):
        rel = config.FONT_PATHS.get(font_key, "")
        if rel:
            abs_p = rel if os.path.isabs(rel) else os.path.join(PROJECT_ROOT, *rel.replace("/", os.sep).split(os.sep))
            candidates.append(os.path.normpath(abs_p))
    for k in (font_key, "headline", "body_bold", "body_regular"):
        p = _BUNDLED_FONT_PATHS.get(k)
        if p:
            np = os.path.normpath(p)
            if np not in candidates:
                candidates.append(np)
    for p in candidates:
        if p and os.path.isfile(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    for sys_path in (
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.isfile(sys_path):
            try:
                return ImageFont.truetype(sys_path, size)
            except Exception:
                continue
    return ImageFont.load_default()

class ImageHunter:
    """Multi-source fighter portrait hunter with robust fallback chain.

    Source order:
        1. Local cache (assets/images_cache/<name>.png)
        2. UFC.com athlete page (hero-profile__image)
        3. UFCStats.com fighter page (search → profile photo)
        4. Wikipedia (search → infobox image)
        5. Sherdog (search → fighter photo)
        6. None (caller falls back to silhouette)

    Every successful fetch is cached so the next run is offline-fast.
    Negative results are remembered in-memory (per process) to skip retries.
    """

    DESKTOP_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"
    )

    def __init__(self):
        if not os.path.exists(IMG_CACHE_DIR):
            os.makedirs(IMG_CACHE_DIR)
        self.headers = {
            "User-Agent": self.DESKTOP_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._negative_cache = set()

    # ---------- public API ----------
    def get_fighter_image(self, name):
        safe_name = self._safe_name(name)
        local_path = os.path.join(IMG_CACHE_DIR, f"{safe_name}.png")
        if os.path.exists(local_path):
            return local_path
        if name in self._negative_cache:
            return None

        print(f"   🕵️‍♂️ Hunting image for: {name}")
        for source_fn in (
            self._try_ufc_com,
            self._try_ufcstats,
            self._try_wikipedia,
            self._try_sherdog,
        ):
            try:
                img_bytes = source_fn(name)
                if img_bytes and self._save_image(img_bytes, local_path):
                    print(f"      ✅ Found via {source_fn.__name__.replace('_try_', '')}")
                    return local_path
            except Exception as e:
                print(f"      ⚠️ {source_fn.__name__}: {type(e).__name__}: {str(e)[:80]}")

        print(f"      ❌ No image for {name}, using silhouette fallback")
        self._negative_cache.add(name)
        return None

    # ---------- helpers ----------
    @staticmethod
    def _safe_name(name):
        return name.replace(" ", "_").lower()

    def _save_image(self, img_bytes, local_path):
        try:
            img = Image.open(BytesIO(img_bytes))
            # convert mode if needed
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            # require a sensible minimum size
            if img.width < 150 or img.height < 150:
                return False
            img.save(local_path, "PNG")
            return True
        except Exception:
            return False

    def _get(self, url, timeout=10):
        return requests.get(url, headers=self.headers, timeout=timeout)

    # ---------- sources ----------
    def _try_ufc_com(self, name):
        slugs_tried = set()
        base_slug = name.lower().replace("'", "").replace(".", "")
        candidates = [
            base_slug.replace(" ", "-"),
            base_slug.replace(" ", "-") + "-1",
            base_slug.split(" ")[0] + "-" + base_slug.split(" ")[-1] if " " in base_slug else base_slug,
        ]
        for slug in candidates:
            if slug in slugs_tried or not slug:
                continue
            slugs_tried.add(slug)
            url = f"https://www.ufc.com/athlete/{slug}"
            resp = self._get(url)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.content, "html.parser")
            img_tag = soup.find("img", class_="hero-profile__image")
            if not img_tag:
                img_tag = soup.select_one(".c-bio__image img, .image-style-full img")
            if img_tag and img_tag.get("src"):
                img_resp = self._get(img_tag["src"])
                if img_resp.status_code == 200:
                    return img_resp.content
        return None

    def _try_ufcstats(self, name):
        # Search page
        search_url = f"http://ufcstats.com/statistics/fighters/search?query={requests.utils.quote(name)}"
        resp = self._get(search_url)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.content, "html.parser")
        link = soup.select_one("a.b-link.b-link_style_black")
        if not link or not link.get("href"):
            return None
        profile_resp = self._get(link["href"])
        if profile_resp.status_code != 200:
            return None
        pf = BeautifulSoup(profile_resp.content, "html.parser")
        img_tag = pf.select_one("img.b-content__image, .b-fight-details__person-image img")
        if img_tag and img_tag.get("src"):
            img_resp = self._get(img_tag["src"])
            if img_resp.status_code == 200:
                return img_resp.content
        return None

    def _try_wikipedia(self, name):
        # Search via MediaWiki API
        api = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "prop": "pageimages",
            "piprop": "original",
            "titles": name,
            "redirects": 1,
        }
        resp = requests.get(api, headers=self.headers, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json().get("query", {}).get("pages", {})
        for _pid, page in data.items():
            original = page.get("original") or page.get("thumbnail")
            if original and original.get("source"):
                img_resp = self._get(original["source"])
                if img_resp.status_code == 200:
                    return img_resp.content
        # fallback search if direct title miss
        search_params = {
            "action": "query",
            "format": "json",
            "list": "search",
            "srsearch": f"{name} UFC fighter",
            "srlimit": 1,
        }
        sr = requests.get(api, headers=self.headers, params=search_params, timeout=10)
        if sr.status_code == 200:
            hits = sr.json().get("query", {}).get("search", [])
            if hits:
                title = hits[0]["title"]
                return self._try_wikipedia(title) if title != name else None
        return None

    def _try_sherdog(self, name):
        search_url = f"https://www.sherdog.com/stats/fightfinder?SearchTxt={requests.utils.quote(name)}"
        resp = self._get(search_url, timeout=12)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.content, "html.parser")
        link = soup.select_one("table.fightfinder_result a")
        if not link or not link.get("href"):
            return None
        profile_url = link["href"]
        if profile_url.startswith("/"):
            profile_url = "https://www.sherdog.com" + profile_url
        pr = self._get(profile_url, timeout=12)
        if pr.status_code != 200:
            return None
        pf = BeautifulSoup(pr.content, "html.parser")
        img = pf.select_one(".bio_fighter img, .fighter_image img, img.profile-image-mobile")
        if img and img.get("src"):
            src = img["src"]
            if src.startswith("/"):
                src = "https://www.sherdog.com" + src
            ir = self._get(src, timeout=12)
            if ir.status_code == 200:
                return ir.content
        return None

# ==========================================
# Versus card: UFCStats height scrape + derived bar scores
# ==========================================
_height_scrape_cache = {}


def _ufcstats_req_headers():
    return {
        "User-Agent": ImageHunter.DESKTOP_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def fetch_height_ufcstats(url):
    """Parse Height from ufcstats.com fighter-details page (cached per URL)."""
    if not url or "ufcstats.com" not in url.lower():
        return None
    if url in _height_scrape_cache:
        return _height_scrape_cache[url]
    try:
        r = requests.get(url, headers=_ufcstats_req_headers(), timeout=10)
        if r.status_code != 200:
            _height_scrape_cache[url] = None
            return None
        soup = BeautifulSoup(r.content, "html.parser")
        for li in soup.select("li.b-list__box-list-item, li[class*='b-list__box-list-item']"):
            text = li.get_text(" ", strip=True)
            if "Height:" not in text and not text.startswith("Height"):
                continue
            if "Height:" in text:
                h = text.split("Height:", 1)[1]
            else:
                h = text.replace("Height", "", 1).lstrip(" :")
            for sep in ("Weight:", "WEIGHT:", "Reach:", "REACH:", "Class:", "CLASS:"):
                if sep in h:
                    h = h.split(sep, 1)[0]
            h = h.strip()
            _height_scrape_cache[url] = h or None
            return _height_scrape_cache[url]
    except Exception:
        pass
    _height_scrape_cache[url] = None
    return None


def _parse_pct_stat(val, default=50.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return default


def _float_stat(stats, key, default=0.0):
    if not isinstance(stats, dict):
        return default
    try:
        return float(stats.get(key) or 0)
    except (TypeError, ValueError):
        return default


def derive_versus_bar_scores(stats, deep):
    """
    Map UFC official stats → 0–100 bar chart scores (always differs when inputs differ).
    Used when AI spotlight is missing or unreliable on Versus cards.
    """
    stats = stats if isinstance(stats, dict) else {}
    deep = deep if isinstance(deep, dict) else {}
    s_acc = _parse_pct_stat(stats.get("Str_Acc"))
    s_def = _parse_pct_stat(stats.get("Str_Def"))
    slpm = _float_stat(stats, "SLpM")
    sapm = _float_stat(stats, "SApM")
    td_avg = _float_stat(stats, "TD_Avg")
    sub_avg = _float_stat(stats, "Sub_Avg")
    ko_rate = float(deep.get("ko_rate") or 0)
    sub_rate = float(deep.get("sub_rate") or 0)
    dec_rate = float(deep.get("dec_rate") or 0)
    avg_sec = float(deep.get("avg_fight_time_sec") or 540)

    power = int(min(88, max(48, 44 + ko_rate * 0.48 + slpm * 2.35)))
    sig_diff = slpm - sapm
    strike_vol = min(28.0, slpm * 3.9)
    strike_def = min(22.0, max(0.0, 6.2 - sapm) * 4.2)
    acc_pts = s_acc * 0.21
    technique = int(
        min(91, max(50, 49 + acc_pts + strike_vol + strike_def + sig_diff * 3.0))
    )
    grappling = int(min(96, max(44, 40 + td_avg * 20.0 + sub_avg * 12.0 + sub_rate * 0.42)))
    stamina = int(min(96, max(50, 50 + (avg_sec / 820.0) * 24.0 + dec_rate * 0.32)))
    chin = int(min(96, max(46, 44 + s_def * 0.48 + max(0.0, 5.2 - sapm) * 4.5)))

    return {
        "power": power,
        "technique": technique,
        "grappling": grappling,
        "stamina": stamina,
        "chin": chin,
    }


def versus_bar_scores_for_card(spotlight, stats, deep):
    st = stats if isinstance(stats, dict) else {}
    has_official = bool(st.get("SLpM") or st.get("Str_Acc") or st.get("Str_Def"))
    if has_official:
        return derive_versus_bar_scores(st, deep if isinstance(deep, dict) else {})
    if isinstance(spotlight, dict) and spotlight:
        out = {}
        for k in ("power", "technique", "grappling", "stamina", "chin"):
            v = spotlight.get(k, 70)
            try:
                out[k] = int(v) if not isinstance(v, str) else int("".join(c for c in v if c.isdigit()) or 70)
            except Exception:
                out[k] = 70
        return out
    return derive_versus_bar_scores(st, deep if isinstance(deep, dict) else {})


def _try_versus_ambient_base(fighter_a="", fighter_b=""):
    """
    Load up to three cached ticket backgrounds (safe / violence / value).
    Used as layers on top of procedural base — not the sole background.
    """
    bg_dir = os.path.join(ASSETS_DIR, "ticket_backgrounds")
    names = ("bg_safe.png", "bg_violence.png", "bg_value.png")
    loaded = []
    for n in names:
        p = os.path.join(bg_dir, n)
        if not os.path.isfile(p):
            continue
        try:
            im = Image.open(p).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
            loaded.append(im)
        except Exception:
            continue
    if not loaded:
        return None
    seed = abs(hash((str(fighter_a).lower(), str(fighter_b).lower()))) % (10**9)
    primary_i = seed % len(loaded)
    base = Image.new("RGB", (WIDTH, HEIGHT), (5, 5, 8))
    base = Image.blend(base, loaded[primary_i], 0.38)
    for i, im in enumerate(loaded):
        if i == primary_i:
            continue
        base = Image.blend(base, im, 0.16)
    return base


def _versus_background_rgb(fa, fb):
    """
    Always-on vector base: split green / cyan mood + vignette (readable on phones).
    Ticket PNGs (if any) stack on top at moderate opacity.
    """
    xx = np.linspace(0.0, 1.0, WIDTH, dtype=np.float32)
    yy = np.linspace(0.0, 1.0, HEIGHT, dtype=np.float32)[:, np.newaxis]
    g_side = (1.0 - xx) * (1.0 - yy * 0.55)
    c_side = xx * (1.0 - yy * 0.55)
    r = 8.0 + g_side * 18.0 + c_side * 12.0 + yy * 6.0
    g = 10.0 + g_side * 42.0 + c_side * 30.0 + yy * 5.0
    b = 12.0 + g_side * 16.0 + c_side * 48.0 + yy * 7.0
    arr = np.stack([r, g, b], axis=-1)
    cx, cy = 0.52, 0.42
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    vig = np.clip(dist * 1.2, 0.0, 0.5)[..., np.newaxis]
    arr *= 1.0 - vig
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    layers = _try_versus_ambient_base(fa, fb)
    if layers is not None:
        img = Image.blend(img, layers, VERSUS_TICKET_BG_BLEND)
    return img


def ensure_versus_overlay_png():
    """assets/versus_bg.png: VERSUS_OVERLAY_GENERATION değişince veya dosya yoksa üretilir."""
    path = os.path.join(ASSETS_DIR, "versus_bg.png")
    meta = os.path.join(ASSETS_DIR, ".versus_overlay_gen")
    try:
        if os.path.isfile(path) and os.path.getsize(path) > 4096 and os.path.isfile(meta):
            with open(meta, "r", encoding="ascii") as mf:
                if int(mf.read().strip()) == VERSUS_OVERLAY_GENERATION:
                    return path
    except (OSError, ValueError):
        pass
    os.makedirs(ASSETS_DIR, exist_ok=True)
    w, h = WIDTH, HEIGHT
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)
    ys = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, np.newaxis]
    # Sol sıcak kızıl-gül, sağ soğuk mavi-mor — taban gradyandan belirgin ayrılsın
    r = 14.0 + ys * 28.0 + (1.0 - xs) * 42.0 + xs * 8.0
    g = 8.0 + ys * 16.0 + (1.0 - xs) * 18.0 + xs * 28.0
    b = 26.0 + ys * 36.0 + xs * 52.0
    arr = np.stack([r, g, b], axis=-1)
    cx, cy = 0.5, 0.22
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    spot = np.clip(1.0 - d * 1.15, 0.0, 1.0)
    arr[..., 0] += spot * 48.0
    arr[..., 1] += spot * 38.0
    arr[..., 2] += spot * 18.0
    xx = np.arange(w, dtype=np.int32)
    yy = np.arange(h, dtype=np.int32)[:, None]
    cage = (((xx + yy) % 56 == 0) | ((xx - yy + w) % 56 == 0)).astype(np.float32) * 18.0
    arr[..., 0] += cage * 0.45
    arr[..., 1] += cage * 0.5
    arr[..., 2] += cage * 0.55
    vx = xs - 0.5
    vy = ys - 0.5
    vig = np.clip(np.sqrt(vx * vx + vy * vy) * 1.02, 0.0, 1.0)
    arr *= (1.0 - 0.22 * vig)[..., np.newaxis]
    out = np.clip(arr, 0, 255).astype(np.uint8)
    Image.fromarray(out).save(path, format="PNG", optimize=True)
    try:
        with open(meta, "w", encoding="ascii") as mf:
            mf.write(str(VERSUS_OVERLAY_GENERATION))
    except OSError:
        pass
    print(f"   🖼 Versus arka plan katmanı yazıldı: {path} (gen {VERSUS_OVERLAY_GENERATION})")
    return path


def _normalize_height_field(h):
    if h is None:
        return None
    s = str(h).strip()
    if not s or s.upper() in ("N/A", "--", "NONE", "NULL"):
        return None
    return s


def _versus_official_cell_display(raw):
    """UFCStats cell: empty / meaningless numeric zero → NO DATA (English copy)."""
    if raw is None:
        return "NO DATA"
    s = str(raw).strip()
    if not s or s in ("—", "-", "--", "N/A", "n/a", "nan", "None"):
        return "NO DATA"
    s_num = s.replace("%", "").strip()
    try:
        if abs(float(s_num)) < 1e-9:
            return "NO DATA"
    except ValueError:
        pass
    return s


def _draw_text_cx_mid(draw, cx, cy, text, font, fill):
    """True optical center at (cx, cy) — avoids anchor quirks with Bebas/custom fonts."""
    if not text:
        return
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=fill)


def _soften_stats_panel(img, top, bottom):
    """Blend lower stats zone into the card (no pasted-on black slab)."""
    if bottom <= top + 24 or top < 0 or bottom > HEIGHT:
        return
    patch = img.crop((0, top, WIDTH, bottom))
    arr = np.asarray(patch, dtype=np.float32)
    h, w, _ = arr.shape
    tint = np.array([11.0, 13.0, 19.0], dtype=np.float32)
    for i in range(h):
        rel = i / max(h - 1, 1)
        top_feather = max(0.0, 1.0 - (i / 42.0))
        mix = 0.32 + 0.28 * rel + 0.12 * top_feather
        mix = min(0.72, mix)
        arr[i, :, :] = arr[i, :, :] * (1.0 - mix) + tint * mix
    out = np.clip(arr, 0, 255).astype(np.uint8)
    img.paste(Image.fromarray(out), (0, top))

# ==========================================
# 1. RADAR CHART ENGINE
# ==========================================
def create_radar_chart(fight_data):
    f1, f2 = fight_data['fighters']
    stats = fight_data.get('stats', [{}, {}])
    deep_stats = fight_data.get('deep_stats', [{}, {}])
    
    def get_score(source, key, multiplier=1.0, is_percent=False):
        try:
            val = source.get(key, 0)
            if is_percent and isinstance(val, str): val = float(val.replace('%', ''))
            return min(float(val) * multiplier, 10.0)
        except: return 0.0

    categories = ['Striking\nVol', 'Grappling', 'Finisher', 'Defense', 'Exp']
    v1 = [get_score(stats[0], 'SLpM', 1.6), get_score(stats[0], 'TD_Avg', 2.0),
          (get_score(deep_stats[0], 'ko_rate') + get_score(deep_stats[0], 'sub_rate')) / 10,
          get_score(stats[0], 'Str_Def', 1.0, True) / 10, get_score(deep_stats[0], 'total_fights', 0.33)]
    v2 = [get_score(stats[1], 'SLpM', 1.6), get_score(stats[1], 'TD_Avg', 2.0),
          (get_score(deep_stats[1], 'ko_rate') + get_score(deep_stats[1], 'sub_rate')) / 10,
          get_score(stats[1], 'Str_Def', 1.0, True) / 10, get_score(deep_stats[1], 'total_fights', 0.33)]

    v1 += v1[:1]; v2 += v2[:1]
    angles = [n / 5 * 2 * np.pi for n in range(5)]; angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    fig.patch.set_facecolor(COLORS['bg']); ax.set_facecolor(COLORS['bg'])
    plt.xticks(angles[:-1], categories, color='white', size=11, weight='bold')
    ax.set_rlabel_position(0); plt.yticks([2,4,6,8,10], [], color=COLORS['grid']); plt.ylim(0,10)
    ax.spines['polar'].set_color(COLORS['grid']); ax.grid(color=COLORS['grid'], linestyle='--', alpha=0.5)
    
    ax.plot(angles, v1, color=COLORS['f1'], linewidth=3, label=f1)
    ax.fill(angles, v1, color=COLORS['f1_fill'])
    ax.plot(angles, v2, color=COLORS['f2'], linewidth=3, label=f2)
    ax.fill(angles, v2, color=COLORS['f2_fill'])
    
    plt.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), facecolor=COLORS['bg'], edgecolor=COLORS['grid'], labelcolor='white')
    plt.title(f"{f1.upper()} VS {f2.upper()}", color='white', weight='bold', size=16, pad=30)
    
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    safe_name = f"{f1.replace(' ','_')}_vs_{f2.replace(' ','_')}.png"
    plt.savefig(f"{OUTPUT_DIR}/Radar_{safe_name}", facecolor=COLORS['bg'], dpi=120, bbox_inches='tight')
    plt.close()

# ==========================================
# 2. STAT CARD ENGINE (REDESIGNED for Phase 2)
# ==========================================
def create_stat_card(fighter_name, stats, one_liner, img_path=None, record="N/A", bg_path=None):
    """
    Creates a professional fighter stat card with brand identity.
    
    Phase 2 Redesign Features:
    - Circular fighter photo at top-center
    - Two-column stat layout
    - Brand colors and typography
    - FightIQ logo placement
    """
    # Import brand colors + font paths (always core.config — never bare `config`)
    try:
        import core.config as _cfg
        COLORS = _cfg.BRAND_COLORS
        FONTS = {}
        for k, rel in _cfg.FONT_PATHS.items():
            FONTS[k] = rel if os.path.isabs(rel) else os.path.join(PROJECT_ROOT, *rel.replace("/", os.sep).split(os.sep))
    except Exception:
        COLORS = {
            "primary": "#00FF41",
            "secondary": "#FFD700",
            "accent": "#FF0055",
            "bg_card": "#1a1a1a",
            "text_white": "#FFFFFF",
            "text_light": "#EEEEEE",
            "text_dark": "#AAAAAA",
        }
        FONTS = {
            "headline": os.path.join(ASSETS_DIR, "fonts", "BebasNeue-Regular.ttf"),
            "body_bold": os.path.join(ASSETS_DIR, "fonts", "Roboto-Bold.ttf"),
        }

    # Helper: Load fonts with fallback
    def load_font(font_key, size, fallback_bold=True):
        try:
            p = FONTS.get(font_key, "")
            if p and os.path.exists(p):
                return ImageFont.truetype(p, size)
        except Exception:
            pass
        try:
            if fallback_bold:
                return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
            return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", size)
        except Exception:
            pass
        return ImageFont.load_default()
    
    # Dimensions
    WIDTH = 1080
    HEIGHT = 1350
    
    # Create image
    img = Image.new('RGB', (WIDTH, HEIGHT), color=COLORS['bg_card'])
    draw = ImageDraw.Draw(img)
    
    # === BACKGROUND: "GHOST WATERMARK" TECHNIQUE ===
    def add_noise(image, intensity=0.05):
        """Adds subtle grain/noise to the background for texture"""
        try:
            np_img = np.array(image)
            noise = np.random.randint(-255*intensity, 255*intensity, np_img.shape, dtype='int16')
            noisy_img = np.clip(np_img.astype('int16') + noise, 0, 255).astype('uint8')
            return Image.fromarray(noisy_img)
        except: return image

    # LAYER 0: Base Dark Background
    # (Already created above as 'img')
    
    # LAYER 1: "Ghost" - Fighter Image as Watermark
    if img_path and os.path.exists(img_path):
        try:
            # Load fighter image
            ghost_img = Image.open(img_path).convert("RGB")
            
            # Resize to fill canvas (preserve aspect, crop center)
            aspect = ghost_img.width / ghost_img.height
            target_aspect = WIDTH / HEIGHT
            
            if aspect > target_aspect:
                # Image is wider - fit to height
                new_height = HEIGHT
                new_width = int(HEIGHT * aspect)
            else:
                # Image is taller - fit to width
                new_width = WIDTH
                new_height = int(WIDTH / aspect)
            
            ghost_img = ghost_img.resize((new_width, new_height), Image.LANCZOS)
            
            # Center crop to canvas size
            left = (new_width - WIDTH) // 2
            top = (new_height - HEIGHT) // 2
            ghost_img = ghost_img.crop((left, top, left + WIDTH, top + HEIGHT))
            
            # Convert to grayscale
            ghost_img = ghost_img.convert("L").convert("RGB")
            
            # Apply extremely low opacity (10%)
            ghost_img = ghost_img.convert("RGBA")
            alpha = Image.new('L', (WIDTH, HEIGHT), int(255 * 0.10))  # 10% opacity
            ghost_img.putalpha(alpha)
            
            # Blend onto base
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, ghost_img)
            img = img.convert("RGB")
            
            print(f"   ✨ Ghost watermark applied")
        except Exception as e:
            print(f"   ⚠️ Ghost effect failed: {e}")
    
    # LAYER 2: Procedural Noise (on top of ghost)
    img = add_noise(img, intensity=0.08)
    
    # Re-initialize draw object (img is new object after noise)
    draw = ImageDraw.Draw(img)
    
    # === CIRCULAR FIGHTER PHOTO (Top-Center Fix) ===
    photo_diameter = 320
    photo_y_pos = 80
    
    if img_path and os.path.exists(img_path):
        try:
            fighter_img = Image.open(img_path).convert("RGB")
            
            # P0 FIX: TOP-CENTER CROP (Don't cut off head)
            # Find the square size (min dimension)
            size = min(fighter_img.size)
            
            # X: Center horizontally
            left = (fighter_img.width - size) // 2
            right = left + size
            
            # Y: Top aligned (0 to size) 
            # Note: If image is wider than tall, this is effectively center vertical too (0 to height).
            # If image is taller than wide (Portrait), this crops the TOP square (Head).
            top = 0 
            bottom = size
            
            fighter_img = fighter_img.crop((left, top, right, bottom))
            fighter_img = fighter_img.resize((photo_diameter, photo_diameter), Image.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (photo_diameter, photo_diameter), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, photo_diameter, photo_diameter), fill=255)
            
            # Create circular photo
            circular_photo = Image.new('RGBA', (photo_diameter, photo_diameter), (0, 0, 0, 0))
            circular_photo.paste(fighter_img, (0, 0))
            circular_photo.putalpha(mask)
            
            # Add glow border
            glow_diameter = photo_diameter + 12
            glow_img = Image.new('RGBA', (glow_diameter, glow_diameter), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow_img)
            # Draw glow ring
            hex_to_rgb = lambda h: tuple(int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            glow_color = hex_to_rgb(COLORS['primary']) + (255,)
            glow_draw.ellipse((0, 0, glow_diameter, glow_diameter), outline=glow_color, width=6)
            
            # Paste on main image
            photo_x_pos = (WIDTH - glow_diameter) // 2
            img.paste(glow_img, (photo_x_pos, photo_y_pos - 6), glow_img)
            img.paste(circular_photo, (photo_x_pos + 6, photo_y_pos), circular_photo)
            
        except Exception as e:
            print(f"Warning: Could not load fighter image: {e}")
            img_path = None
    
    # === FIGHTER NAME (Below Photo) ===
    name_y_pos = photo_y_pos + photo_diameter + 40
    font_name = load_font("headline", 64, True)
    
    draw.text((WIDTH // 2, name_y_pos), fighter_name.upper(), 
              font=font_name, fill=COLORS['text_white'], anchor="mt")
    
    # === RECORD (Below Name) ===
    record_y_pos = name_y_pos + 80
    font_record = load_font("body_bold", 28)
    
    draw.text((WIDTH // 2, record_y_pos), f"RECORD: {record}", 
              font=font_record, fill=COLORS['text_dark'], anchor="mt")
    
    # === ONE-LINER (Tagline) ===
    tagline_y_pos = record_y_pos + 50
    font_tagline = load_font("body_bold", 32)
    
    draw.text((WIDTH // 2, tagline_y_pos), f'"{one_liner}"', 
              font=font_tagline, fill=COLORS['primary'], anchor="mt", 
              align="center")
    
    # === SEPARATOR LINE ===
    separator_y = tagline_y_pos + 60
    separator_margin = 120
    draw.line([(separator_margin, separator_y), (WIDTH - separator_margin, separator_y)],
              fill=COLORS['primary'], width=3)
    
    # === STATS (Two-Column Layout) ===
    stats_start_y = separator_y + 60
    
    # Helper: Safe integer conversion
    def safe_int(val):
        try:
            if isinstance(val, (int, float)): return int(val)
            # Remove non-numeric chars (except dot)
            clean = "".join([c for c in str(val) if c.isdigit()])
            return int(clean) if clean else 50
        except: return 50

    # Get stats
    attributes = {
        'POWER': safe_int(stats.get('power', 50)),
        'GRAPPLING': safe_int(stats.get('grappling', 50)),
        'STAMINA': safe_int(stats.get('stamina', 50)),
        'CHIN': safe_int(stats.get('chin', 50)),
        'TECHNIQUE': safe_int(stats.get('technique', 50))
    }
    
    # Two columns
    left_stats = ['POWER', 'STAMINA', 'TECHNIQUE']
    right_stats = ['GRAPPLING', 'CHIN']
    
    font_stat_label = load_font("body_bold", 24)
    font_stat_value = load_font("headline", 56, True)
    
    # Left column
    x_left = 140
    y_pos = stats_start_y
    for stat_name in left_stats:
        value = attributes[stat_name]
        
        # Label
        draw.text((x_left, y_pos), stat_name, 
                  font=font_stat_label, fill=COLORS['text_light'], anchor="lt")
        
        # Value (large number)
        draw.text((x_left, y_pos + 30), str(value), 
                  font=font_stat_value, fill=COLORS['secondary'], anchor="lt")
        
        # Progress bar
        bar_y = y_pos + 95
        bar_width = 320
        bar_height = 8
        
        # Background bar
        draw.rectangle([x_left, bar_y, x_left + bar_width, bar_y + bar_height],
                       fill='#333333')
        
        # Filled bar
        fill_width = int(bar_width * (value / 100))
        draw.rectangle([x_left, bar_y, x_left + fill_width, bar_y + bar_height],
                       fill=COLORS['primary'])
        
        y_pos += 150
    
    # Right column
    x_right = 580
    y_pos = stats_start_y
    for stat_name in right_stats:
        value = attributes[stat_name]
        
        # Label
        draw.text((x_right, y_pos), stat_name, 
                  font=font_stat_label, fill=COLORS['text_light'], anchor="lt")
        
        # Value
        draw.text((x_right, y_pos + 30), str(value), 
                  font=font_stat_value, fill=COLORS['secondary'], anchor="lt")
        
        # Progress bar
        bar_y = y_pos + 95
        bar_width = 320
        bar_height = 8
        
        draw.rectangle([x_right, bar_y, x_right + bar_width, bar_y + bar_height],
                       fill='#333333')
        
        fill_width = int(bar_width * (value / 100))
        draw.rectangle([x_right, bar_y, x_right + fill_width, bar_y + bar_height],
                       fill=COLORS['primary'])
        
        y_pos += 150
    
    # === LOGO/BRANDING (Bottom) ===
    logo_y = HEIGHT - 80
    font_logo = load_font("headline", 36, True)
    
    # Try to load logo image (if exists)
    logo_path = "assets/fightiq_logo.png"
    if os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path).convert("RGBA")
            logo_img.thumbnail((200, 60), Image.LANCZOS)
            logo_x = (WIDTH - logo_img.width) // 2
            img.paste(logo_img, (logo_x, logo_y - 30), logo_img)
        except:
            # Text fallback
            draw.text((WIDTH // 2, logo_y), "FIGHTIQ SCOUTING REPORT", 
                      font=font_logo, fill=COLORS['text_dark'], anchor="mt")
    else:
        # Text logo
        draw.text((WIDTH // 2, logo_y), "FIGHTIQ", 
                  font=font_logo, fill=COLORS['primary'], anchor="mt")
        
        font_subtitle = load_font("body_bold", 18)
        draw.text((WIDTH // 2, logo_y + 45), "SCOUTING REPORT", 
                  font=font_subtitle, fill=COLORS['text_dark'], anchor="mt")
    
    # === SAVE ===
    safe_name = fighter_name.replace(" ", "_")
    filename = f"{OUTPUT_DIR}/Card_{safe_name}.png"
    img.save(filename, "PNG")
    print(f"   ✅ Created: {filename}")

# ==========================================
# 3. VERSUS CARD ENGINE (Oracle Mode)
# ==========================================
def create_versus_card(fighter1_data, fighter2_data, card_stats, official_stats_pair=None):
    """
    Split-screen Versus card.
    card_stats: {'fighter1': {power, technique, ...}, 'fighter2': {...}} (0–100 ints).
    official_stats_pair: optional (dict, dict) of UFCStats-style rows (e.g. SLpM) for bottom strip.

    Arka plan: _versus_background_rgb() — sol yeşil / sağ camgöbeği vektör gradyan + vignette;
    varsa assets/ticket_backgrounds/bg_{safe,violence,value}.png çok düşük opaklıkta karıştırılır.
    assets/versus_bg.png yoksa veya küçük/bozuksa ensure_versus_overlay_png() ile kod üretir (Imagen yok), ardından VERSUS_BG_PNG_BLEND ile üste bindirilir.
    """
    f1_name = fighter1_data['name']
    f2_name = fighter2_data['name']
    print(f"    Creating Versus Card: {f1_name} vs {f2_name}...")

    hunter = ImageHunter()
    path1 = hunter.get_fighter_image(f1_name)
    path2 = hunter.get_fighter_image(f2_name)

    center_x = WIDTH // 2

    # ── 1. Background: vektör taban + ticket + tam ekran versus_bg (yoksa otomatik üretilir) ──
    img = _versus_background_rgb(f1_name, f2_name)
    try:
        ensure_versus_overlay_png()
    except Exception as e:
        print(f"      ⚠️ versus_bg üretilemedi: {e}")
    bespoke_bg = os.path.join(ASSETS_DIR, "versus_bg.png")
    if os.path.isfile(bespoke_bg):
        try:
            bg_custom = Image.open(bespoke_bg).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
            img = Image.blend(img, bg_custom, VERSUS_BG_PNG_BLEND)
        except Exception:
            pass

    # Light film grain (düşük — arka planı kirletmesin)
    try:
        np_img = np.array(img)
        noise = np.random.randint(-5, 5, np_img.shape, dtype="int16")
        img = Image.fromarray(np.clip(np_img.astype("int16") + noise, 0, 255).astype("uint8"))
    except Exception:
        pass

    draw = ImageDraw.Draw(img)

    # İsteğe bağlı hayalet portreler (varsayılan kapalı — bulanık / kirli görünüm)
    if VERSUS_USE_FIGHTER_GHOST_BG:

        def draw_ghost(img_path, is_left):
            if not img_path or not os.path.exists(img_path):
                return
            try:
                ghost = Image.open(img_path).convert("RGBA")
                ghost = ImageOps.grayscale(ghost).convert("RGBA")
                g_size = int(HEIGHT * 0.75)
                ghost = ghost.resize((g_size, g_size), Image.LANCZOS)
                pixels = ghost.getdata()
                ghost.putdata([(p[0], p[1], p[2], int(p[3] * 0.15)) for p in pixels])
                x_off = -int(g_size * 0.15) if is_left else WIDTH - int(g_size * 0.85)
                img.paste(ghost, (x_off, HEIGHT - g_size - 50), ghost)
            except Exception:
                pass

        draw_ghost(path1, True)
        draw_ghost(path2, False)
        draw = ImageDraw.Draw(img)

    # ── 3. TOP BANNER ─────────────────────────────────────
    w1 = fighter1_data.get('weight_class', '').replace("Women's ", "").strip()
    w2 = fighter2_data.get('weight_class', '').replace("Women's ", "").strip()
    if w1 == w2 and w1:
        banner_text = f"{w1.upper()} BOUT  ·  FIGHTIQ ANALYSIS"
    else:
        banner_text = "FIGHTIQ  ·  MATCHUP ANALYSIS"

    font_banner = load_font("headline", 34)
    banner_h = 64
    draw.rectangle([(0, 0), (WIDTH, banner_h)], fill=(15, 15, 15))
    draw.text((WIDTH // 2, banner_h // 2), banner_text, font=font_banner,
              fill=COLORS['secondary'], anchor="mm")
    draw.line([(0, banner_h), (WIDTH, banner_h)], fill=COLORS['secondary'], width=2)

    # ── 4. Fighter photos (biraz aşağıda — üst banner ile nefes payı) ──
    photo_diameter = 298
    photo_y = 88
    glow_pad = 14

    def paste_fighter_circle(img_path, x_center, glow_color_hex):
        fallback = os.path.join(ASSETS_DIR, "silhouette.png")
        src = img_path if (img_path and os.path.exists(img_path)) else fallback
        if not (src and os.path.exists(src)):
            return
        try:
            raw = Image.open(src).convert("RGBA")
            rw, rh = raw.size
            # Scale to fill circle while keeping aspect ratio (crop from center)
            scale = max(photo_diameter / rw, photo_diameter / rh)
            new_w = int(rw * scale)
            new_h = int(rh * scale)
            raw = raw.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - photo_diameter) // 2
            top = max(0, (new_h - photo_diameter) // 4)  # bias toward top (face)
            top = min(top, new_h - photo_diameter)
            cropped = raw.crop((left, top, left + photo_diameter, top + photo_diameter))

            # Circular mask
            mask = Image.new('L', (photo_diameter, photo_diameter), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, photo_diameter, photo_diameter), fill=255)
            cropped.putalpha(mask)

            # Glow ring
            gd = photo_diameter + glow_pad * 2
            glow = Image.new('RGBA', (gd, gd), (0, 0, 0, 0))
            gd_draw = ImageDraw.Draw(glow)
            hex_rgb = tuple(int(glow_color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            for thickness, alpha in [(10, 60), (7, 120), (4, 200), (2, 255)]:
                gd_draw.ellipse((0, 0, gd - 1, gd - 1), outline=hex_rgb + (alpha,), width=thickness)

            gx = x_center - gd // 2
            gy = photo_y
            img.paste(glow, (gx, gy), glow)
            img.paste(cropped, (gx + glow_pad, gy + glow_pad), cropped)
        except Exception as e:
            print(f"      Photo error ({src}): {e}")

    paste_fighter_circle(path1, WIDTH // 4, COLORS['primary'])
    paste_fighter_circle(path2, 3 * WIDTH // 4, COLORS['accent'])
    draw = ImageDraw.Draw(img)

    # ── 5. Names & Records ────────────────────────────────
    name_y = photo_y + photo_diameter + glow_pad * 2 + 12
    font_name = load_font("headline", 56)
    font_record = load_font("body_bold", 30)
    font_nickname = load_font("body_regular", 21, fallback_bold=False)

    def truncate_name(name, max_chars=14):
        parts = name.upper().split()
        if len(' '.join(parts)) <= max_chars:
            return ' '.join(parts)
        return parts[-1] if parts else name.upper()

    def format_record(record_str):
        """Show 'DEBUT' for 0-0-0, otherwise show W-L-D."""
        if not record_str or record_str == 'N/A':
            return 'N/A'
        parts = record_str.split('-')
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            if int(parts[0]) == 0 and int(parts[1]) == 0:
                return 'UFC DEBUT'
        return record_str

    def truncate_oneliner(text, max_chars=32):
        """Trim one-liner to fit on card without overflow."""
        if not text:
            return ''
        if len(text) <= max_chars:
            return text
        # Try to cut at last space before limit
        cut = text[:max_chars].rsplit(' ', 1)[0]
        return cut + '…'

    # Left fighter
    draw.text((WIDTH // 4, name_y), truncate_name(f1_name),
              font=font_name, fill=COLORS['primary'], anchor="mt")
    rec1 = format_record(fighter1_data.get('record', 'N/A'))
    draw.text((WIDTH // 4, name_y + 62), rec1,
              font=font_record, fill=(200, 200, 200), anchor="mt")
    ol1 = truncate_oneliner(fighter1_data.get('one_liner', ''))
    if ol1:
        draw.text((WIDTH // 4, name_y + 90), f'"{ol1}"',
                  font=font_nickname, fill=(140, 140, 140), anchor="mt")

    # Right fighter
    draw.text((3 * WIDTH // 4, name_y), truncate_name(f2_name),
              font=font_name, fill=COLORS['accent'], anchor="mt")
    rec2 = format_record(fighter2_data.get('record', 'N/A'))
    draw.text((3 * WIDTH // 4, name_y + 62), rec2,
              font=font_record, fill=(200, 200, 200), anchor="mt")
    ol2 = truncate_oneliner(fighter2_data.get('one_liner', ''))
    if ol2:
        draw.text((3 * WIDTH // 4, name_y + 90), f'"{ol2}"',
                  font=font_nickname, fill=(140, 140, 140), anchor="mt")

    # ── 6. VS Badge ──
    vs_y = name_y + 22
    vs_dia = 110
    vs_cx = center_x
    vs_bg = Image.new('RGBA', (vs_dia, vs_dia), (0, 0, 0, 0))
    vs_bg_draw = ImageDraw.Draw(vs_bg)
    vs_bg_draw.ellipse((0, 0, vs_dia, vs_dia), fill=(255, 215, 0, 230))
    vs_bg_draw.ellipse((0, 0, vs_dia, vs_dia), outline=(255, 255, 255, 180), width=3)
    img.paste(vs_bg, (vs_cx - vs_dia // 2, vs_y - vs_dia // 2), vs_bg)
    draw = ImageDraw.Draw(img)
    font_vs = load_font("headline", 64)
    draw.text((vs_cx, vs_y), "VS", font=font_vs, fill=(10, 10, 10), anchor="mm")

    # ── 7. Fizik şeridi (sol | etiket ortada | sağ — üst üste binmez) + barlar + UFC resmi (aynı gövde) ──
    stat_defs = [
        ("POWER", "power"),
        ("STRIKING", "technique"),
        ("GRAPPLING", "grappling"),
        ("STAMINA", "stamina"),
        ("CHIN", "chin"),
    ]

    def get_stat(d, k):
        v = d.get(k, 70)
        if isinstance(v, str):
            clean = "".join(c for c in v if c.isdigit())
            return int(clean) if clean else 70
        return int(v) if v else 70

    stats1 = card_stats.get("fighter1", {})
    stats2 = card_stats.get("fighter2", {})
    if not stats1:
        stats1 = card_stats.get(f1_name, card_stats)
        stats2 = card_stats.get(f2_name, {})
    if not stats2:
        stats2 = {}

    def draw_center_spine(y0, y1):
        if y1 <= y0 + 4:
            return
        for dx, shade in ((0, 255), (-1, 200), (1, 200)):
            x = center_x + dx
            if 0 <= x < WIDTH:
                draw.line([(x, y0), (x, y1)], fill=(shade, int(shade * 0.84), max(0, shade - 155)), width=2 if dx == 0 else 1)

    has_official_strip = bool(
        official_stats_pair
        and isinstance(official_stats_pair, (list, tuple))
        and len(official_stats_pair) == 2
    )

    footer_band_h = 36
    content_bottom = HEIGHT - footer_band_h

    official_row_h = 38
    official_title_zone = 40
    if has_official_strip:
        official_n_rows = 5
        official_block_h = official_title_zone + official_n_rows * official_row_h + 18
    else:
        official_n_rows = 0
        official_block_h = 0

    official_top = content_bottom - official_block_h

    tape_fields = [
        ("HEIGHT", fighter1_data.get("height", "--"), fighter2_data.get("height", "--")),
        ("REACH", fighter1_data.get("reach", "--"), fighter2_data.get("reach", "--")),
        ("STANCE", fighter1_data.get("stance", "--"), fighter2_data.get("stance", "--")),
        ("AGE", str(fighter1_data.get("age", "--")), str(fighter2_data.get("age", "--"))),
    ]
    n_tape = len(tape_fields)
    tape_row_h = 42
    tape_y = int(vs_y + vs_dia // 2 + 24)
    tape_block_bottom = tape_y + n_tape * tape_row_h + 12
    stats_section_y = tape_block_bottom + 12

    bar_zone_top = stats_section_y + 24
    bar_zone_bottom = (official_top - 22) if has_official_strip else (content_bottom - 22)
    if bar_zone_bottom < bar_zone_top + 140:
        bar_zone_bottom = bar_zone_top + 140

    n_bar = len(stat_defs)
    span = max(0, bar_zone_bottom - bar_zone_top)
    if n_bar <= 1:
        bar_ys = [bar_zone_top + span // 2]
    else:
        bar_ys = [int(bar_zone_top + i * span / (n_bar - 1)) for i in range(n_bar)]

    spine_tape_top = tape_y - 12
    draw_center_spine(banner_h + 6, spine_tape_top)

    tape_lane_half = 92
    col_tape_l = center_x - tape_lane_half
    col_tape_r = center_x + tape_lane_half
    font_tape_lbl = load_font("body_bold", 21)
    font_tape_val = load_font("body_bold", 26)
    for i, (lbl, v1, v2) in enumerate(tape_fields):
        row_cy = tape_y + i * tape_row_h + tape_row_h // 2
        draw.text(
            (col_tape_l, row_cy),
            str(v1),
            font=font_tape_val,
            fill=COLORS["primary"],
            anchor="rm",
        )
        _draw_text_cx_mid(draw, center_x, row_cy, lbl, font_tape_lbl, "#D8D8D8")
        draw.text(
            (col_tape_r, row_cy),
            str(v2),
            font=font_tape_val,
            fill=COLORS["accent"],
            anchor="lm",
        )

    spine_mid_end = (official_top - 12) if has_official_strip else min(bar_zone_bottom + 8, content_bottom - 50)
    draw_center_spine(tape_block_bottom + 8, spine_mid_end)

    draw.line([(36, stats_section_y), (WIDTH - 36, stats_section_y)], fill="#777777", width=2)

    bar_h = 26
    lbl_gap = 10
    font_stat_lbl = load_font("headline", 28)
    font_stat_val = load_font("body_bold", 46)

    MARGIN = 28
    GAP = 10
    VALUE_W = 54
    max_lw = 0
    for lbl, _ in stat_defs:
        bb = draw.textbbox((0, 0), lbl, font=font_stat_lbl)
        max_lw = max(max_lw, bb[2] - bb[0])
    label_reserve = max(max_lw + lbl_gap * 2, 112)

    bar_max_w = center_x - MARGIN - label_reserve - GAP - VALUE_W - GAP - 10
    bar_L_start = MARGIN + label_reserve + GAP
    bar_L_end = bar_L_start + bar_max_w
    val_L_x = bar_L_end + GAP
    bar_R_end = WIDTH - MARGIN - label_reserve - GAP
    bar_R_start = bar_R_end - bar_max_w
    val_R_x = bar_R_start - GAP

    for idx, (lbl, key) in enumerate(stat_defs):
        y = bar_ys[idx]
        v1 = get_stat(stats1, key)
        v2 = get_stat(stats2, key) if stats2 else v1
        draw.text(
            (bar_L_start - lbl_gap, y),
            lbl,
            font=font_stat_lbl,
            fill="#E8E8E8",
            anchor="rm",
        )
        draw.rectangle([bar_L_start, y - bar_h // 2, bar_L_end, y + bar_h // 2], fill="#141414")
        draw.rectangle([bar_L_start, y - bar_h // 2, bar_L_end, y + bar_h // 2], outline="#404040", width=1)
        fill_w1 = int(bar_max_w * v1 / 100)
        if fill_w1 > 0:
            draw.rectangle(
                [bar_L_start, y - bar_h // 2, bar_L_start + fill_w1, y + bar_h // 2],
                fill=COLORS["primary"],
            )
        draw.text((val_L_x, y), str(v1), font=font_stat_val, fill=COLORS["primary"], anchor="lm")
        draw.text(
            (bar_R_end + lbl_gap, y),
            lbl,
            font=font_stat_lbl,
            fill="#E8E8E8",
            anchor="lm",
        )
        draw.rectangle([bar_R_start, y - bar_h // 2, bar_R_end, y + bar_h // 2], fill="#141414")
        draw.rectangle([bar_R_start, y - bar_h // 2, bar_R_end, y + bar_h // 2], outline="#404040", width=1)
        fill_w2 = int(bar_max_w * v2 / 100)
        if fill_w2 > 0:
            draw.rectangle(
                [bar_R_end - fill_w2, y - bar_h // 2, bar_R_end, y + bar_h // 2],
                fill=COLORS["accent"],
            )
        draw.text((val_R_x, y), str(v2), font=font_stat_val, fill=COLORS["accent"], anchor="rm")

    if has_official_strip:
        o1, o2 = official_stats_pair
        o1 = o1 if isinstance(o1, dict) else {}
        o2 = o2 if isinstance(o2, dict) else {}
        rows = [
            ("SIG STR / MIN", "SLpM"),
            ("STRIKE ACC", "Str_Acc"),
            ("STRIKE DEF", "Str_Def"),
            ("TD / 15 MIN", "TD_Avg"),
            ("SUB / 15 MIN", "Sub_Avg"),
        ]
        _soften_stats_panel(img, max(0, official_top - 10), content_bottom)
        draw = ImageDraw.Draw(img)
        cx_panel = WIDTH // 2
        col_gap = 242
        draw.line([(36, official_top), (WIDTH - 36, official_top)], fill=(140, 118, 55), width=2)
        font_strip_h = load_font("headline", 28)
        _draw_text_cx_mid(
            draw,
            cx_panel,
            official_top + 20,
            "UFC OFFICIAL  ·  PER FIGHT AVG",
            font_strip_h,
            COLORS["secondary"],
        )
        font_sr = load_font("body_bold", 22)
        font_sv = load_font("body_bold", 32)
        ry = official_top + official_title_zone + 4
        for lab, key in rows:
            if ry + official_row_h > content_bottom - 6:
                break
            row_cy = ry + official_row_h // 2
            _draw_text_cx_mid(draw, cx_panel, row_cy, lab, font_sr, "#D6D6D6")
            v1s = _versus_official_cell_display(o1.get(key))
            v2s = _versus_official_cell_display(o2.get(key))
            draw.text(
                (cx_panel - col_gap, row_cy),
                v1s,
                font=font_sv,
                fill=COLORS["primary"],
                anchor="rm",
            )
            draw.text(
                (cx_panel + col_gap, row_cy),
                v2s,
                font=font_sv,
                fill=COLORS["accent"],
                anchor="lm",
            )
            ry += official_row_h

    draw.rectangle([(0, content_bottom), (WIDTH, HEIGHT)], fill=(6, 6, 8))
    font_footer = load_font("body_bold", 17)
    _draw_text_cx_mid(draw, WIDTH // 2, content_bottom + 18, "FIGHTIQ.AI  ·  @FightIQBot", font_footer, "#888888")

    # ── Save ──────────────────────────────────────────
    safe1 = f1_name.replace(' ', '_').replace("'", '')
    safe2 = f2_name.replace(' ', '_').replace("'", '')
    out_path = os.path.join(VISUALS_DIR, f"Versus_{safe1}_vs_{safe2}.png")
    img.save(out_path, quality=95)
    print(f"   Versus Card saved: {out_path}")
    return out_path


def run_versus_only(fight_index: int):
    """Tek bir Versus kartı üretir; tüm output/visuals temizlemez (QA / önizleme)."""
    os.makedirs(VISUALS_DIR, exist_ok=True)
    try:
        with open(RAW_DATA_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        with open(AI_DATA_FILE, "r", encoding="utf-8") as f:
            ai_data = json.load(f)
    except Exception as e:
        print(f"⚠️ run_versus_only load error: {e}")
        return None
    if not raw_data:
        print("⚠️ run_versus_only: raw_data boş")
        return None
    idx = int(fight_index) % len(raw_data)
    fight = raw_data[idx]

    spotlight_lookup = {}
    for item in ai_data:
        brain = item.get("fight_brain_output", {})
        sp = brain.get("spotlight_stats", {})
        for fname, fstats in sp.items():
            spotlight_lookup[fname.lower()] = fstats

    fighters = fight.get("fighters", [])
    if len(fighters) < 2:
        print(f"⚠️ run_versus_only[{idx}]: yetersiz dövüşçü")
        return None
    f1_name, f2_name = fighters[0], fighters[1]
    stats_list = fight.get("stats", [{}, {}])
    deep_list = fight.get("deep_stats", [{}, {}])

    def build_fighter_data(name, stats_raw, deep_raw, ufc_url=None):
        ds = deep_raw if isinstance(deep_raw, dict) else {}
        st = stats_raw if isinstance(stats_raw, dict) else {}
        wins = ds.get("wins", 0) or 0
        losses = ds.get("losses", 0) or 0
        draws = ds.get("draws", 0) or 0
        rec = f"{wins}-{losses}-{draws}"
        sp_stats = spotlight_lookup.get(name.lower(), {})
        h = ds.get("height") or ds.get("Height") or st.get("Height") or st.get("height")
        h = _normalize_height_field(h)
        if (not h) and ufc_url:
            fetched = fetch_height_ufcstats(ufc_url)
            if fetched:
                h = fetched
        if not h or str(h).strip() in ("", "N/A"):
            h = "--"
        return {
            "name": name,
            "record": rec,
            "weight_class": st.get("weight_class", ds.get("weight_class", "")),
            "height": str(h).strip(),
            "reach": ds.get("reach", st.get("reach", "--")),
            "stance": ds.get("stance", st.get("stance", "--")),
            "age": ds.get("age", st.get("age", "--")),
            "one_liner": sp_stats.get("one_liner", ""),
        }

    urls = fight.get("urls") or []
    url1 = urls[0] if len(urls) > 0 else None
    url2 = urls[1] if len(urls) > 1 else None

    f1_data = build_fighter_data(
        f1_name,
        stats_list[0] if len(stats_list) > 0 else {},
        deep_list[0] if len(deep_list) > 0 else {},
        url1,
    )
    f2_data = build_fighter_data(
        f2_name,
        stats_list[1] if len(stats_list) > 1 else {},
        deep_list[1] if len(deep_list) > 1 else {},
        url2,
    )

    sp1 = spotlight_lookup.get(f1_name.lower(), {})
    sp2 = spotlight_lookup.get(f2_name.lower(), {})
    st_a = stats_list[0] if len(stats_list) > 0 else {}
    st_b = stats_list[1] if len(stats_list) > 1 else {}
    d_a = deep_list[0] if len(deep_list) > 0 else {}
    d_b = deep_list[1] if len(deep_list) > 1 else {}
    card_stats = {
        "fighter1": versus_bar_scores_for_card(sp1, st_a, d_a),
        "fighter2": versus_bar_scores_for_card(sp2, st_b, d_b),
    }
    try:
        out = create_versus_card(f1_data, f2_data, card_stats, (st_a, st_b))
        prev = os.path.join(VISUALS_DIR, f"Versus_PREVIEW_fight{idx}.png")
        shutil.copy2(out, prev)
        print(f"   📋 Önizleme kopyası: {prev}")
        return out
    except Exception as ve:
        print(f"   run_versus_only hata ({f1_name} vs {f2_name}): {ve}")
        return None


def main():
    print("--- 🎨 STEP 6: VISUAL ENGINE (DESIGN & CLEAN) ---")
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    clean_visuals_folder()
    hunter = ImageHunter()

    # 1. RADARLARI OLUŞTUR
    try:
        with open(RAW_DATA_FILE, "r", encoding="utf-8") as f: raw_data = json.load(f)
        for fight in raw_data:
            if 'deep_stats' in fight: create_radar_chart(fight)
    except: pass

    # 2. STAT KARTLARI (Canlı Mod İçin)
    try:
        # Build record lookup from deep_stats (wins/losses)
        record_lookup = {}
        with open(RAW_DATA_FILE, "r", encoding="utf-8") as f: raw_data = json.load(f)
        for fight in raw_data:
            deep = fight.get('deep_stats', [])
            for ds in deep:
                if not isinstance(ds, dict): continue
                name = ds.get('name', '')
                wins = ds.get('wins', 0) or 0
                losses = ds.get('losses', 0) or 0
                draws = ds.get('draws', 0) or 0
                if name and (wins or losses):
                    record_lookup[name.lower()] = f"{wins}-{losses}-{draws}"

        with open(AI_DATA_FILE, "r", encoding="utf-8") as f: ai_data = json.load(f)
        for item in ai_data:
            brain = item.get('fight_brain_output', {})
            spotlight = brain.get('spotlight_stats', {})
            if spotlight:
                for fname, stats in spotlight.items():
                    img_path = hunter.get_fighter_image(fname)
                    record = record_lookup.get(fname.lower(), "N/A")
                    create_stat_card(fname, stats, stats.get('one_liner', ''), img_path, record=record)
    except Exception as e:
        print(f"⚠️ Stat card error: {e}")

    # 3. VERSUS KARTLARI (Her dövüş için)
    try:
        with open(RAW_DATA_FILE, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        with open(AI_DATA_FILE, "r", encoding="utf-8") as f:
            ai_data = json.load(f)

        # Build AI spotlight lookup: fighter_name → stats
        spotlight_lookup = {}
        for item in ai_data:
            brain = item.get('fight_brain_output', {})
            sp = brain.get('spotlight_stats', {})
            for fname, fstats in sp.items():
                spotlight_lookup[fname.lower()] = fstats

        for fight in raw_data:
            fighters = fight.get('fighters', [])
            if len(fighters) < 2:
                continue
            f1_name, f2_name = fighters[0], fighters[1]
            stats_list = fight.get('stats', [{}, {}])
            deep_list  = fight.get('deep_stats', [{}, {}])

            def build_fighter_data(name, stats_raw, deep_raw, ufc_url=None):
                ds = deep_raw if isinstance(deep_raw, dict) else {}
                st = stats_raw if isinstance(stats_raw, dict) else {}
                wins   = ds.get('wins', 0) or 0
                losses = ds.get('losses', 0) or 0
                draws  = ds.get('draws', 0) or 0
                rec = f"{wins}-{losses}-{draws}"
                sp_stats = spotlight_lookup.get(name.lower(), {})
                h = ds.get("height") or ds.get("Height") or st.get("Height") or st.get("height")
                h = _normalize_height_field(h)
                if (not h) and ufc_url:
                    fetched = fetch_height_ufcstats(ufc_url)
                    if fetched:
                        h = fetched
                if not h or str(h).strip() in ("", "N/A"):
                    h = "--"
                return {
                    'name':         name,
                    'record':       rec,
                    'weight_class': st.get('weight_class', ds.get('weight_class', '')),
                    'height':       str(h).strip(),
                    'reach':        ds.get('reach',  st.get('reach',  '--')),
                    'stance':       ds.get('stance', st.get('stance', '--')),
                    'age':          ds.get('age',    st.get('age',    '--')),
                    'one_liner':    sp_stats.get('one_liner', ''),
                }

            urls = fight.get('urls') or []
            url1 = urls[0] if len(urls) > 0 else None
            url2 = urls[1] if len(urls) > 1 else None

            f1_data = build_fighter_data(
                f1_name,
                stats_list[0] if len(stats_list) > 0 else {},
                deep_list[0] if len(deep_list) > 0 else {},
                url1,
            )
            f2_data = build_fighter_data(
                f2_name,
                stats_list[1] if len(stats_list) > 1 else {},
                deep_list[1] if len(deep_list) > 1 else {},
                url2,
            )

            sp1 = spotlight_lookup.get(f1_name.lower(), {})
            sp2 = spotlight_lookup.get(f2_name.lower(), {})
            st_a = stats_list[0] if len(stats_list) > 0 else {}
            st_b = stats_list[1] if len(stats_list) > 1 else {}
            d_a = deep_list[0] if len(deep_list) > 0 else {}
            d_b = deep_list[1] if len(deep_list) > 1 else {}
            card_stats = {
                'fighter1': versus_bar_scores_for_card(sp1, st_a, d_a),
                'fighter2': versus_bar_scores_for_card(sp2, st_b, d_b),
            }
            try:
                create_versus_card(
                    f1_data,
                    f2_data,
                    card_stats,
                    (st_a, st_b),
                )
            except Exception as ve:
                print(f"   Versus card error ({f1_name} vs {f2_name}): {ve}")
    except Exception as e:
        print(f"⚠️ Versus card generation error: {e}")

    print(f"\n✅ VISUALS COMPLETE.")

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--versus-only":
        run_versus_only(int(sys.argv[2]))
    else:
        main()