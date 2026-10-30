"""Model: analisis karakteristik leksikal/struktural URL (proposal bab 3.3)."""
import re
from urllib.parse import urlparse

BRANDS = {
    "paypal": "paypal.com", "google": "google.com", "facebook": "facebook.com",
    "instagram": "instagram.com", "microsoft": "microsoft.com", "apple": "apple.com",
    "netflix": "netflix.com", "shopee": "shopee.co.id", "tokopedia": "tokopedia.com",
    "gopay": "gopay.co.id", "dana": "dana.id", "bca": "bca.co.id", "bni": "bni.co.id",
    "bri": "bri.co.id", "mandiri": "bankmandiri.co.id",
}
KEYWORDS = ["login", "signin", "verify", "update", "secure", "account", "password", "confirm", "wallet", "bonus"]
RISKY_TLDS = {"xyz", "top", "tk", "ml", "ga", "cf", "gq", "click", "work", "zip", "icu", "cyou", "buzz"}
SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "s.id", "rb.gy"}
SLD = {"co", "ac", "go", "or", "sch", "web", "net"}


def analyze_url(raw: str) -> dict:
    """Kembalikan {'error': str} atau {'url','host','indicators':[{'weight','text'}]}."""
    s = (raw or "").strip()
    if not s:
        return {"error": "Masukkan URL terlebih dahulu."}
    if re.search(r"\s", s):
        return {"error": "URL tidak boleh mengandung spasi."}
    if not re.match(r"^[a-z][a-z0-9+.-]*://", s, re.I):
        s = "https://" + s
    try:
        u = urlparse(s)
        host = (u.hostname or "").lower()
        port = u.port
    except ValueError:
        return {"error": "Format URL tidak valid. Contoh: https://contoh.com"}
    if u.scheme not in ("http", "https"):
        return {"error": "Hanya URL berawalan http:// atau https:// yang dapat diperiksa."}
    is_ip = bool(re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host)) or ":" in host
    if not host or (not is_ip and "." not in host):
        return {"error": "Nama domain tidak valid. Contoh: https://contoh.com"}

    parts = host.split(".")
    tld = parts[-1]
    reg_n = 3 if len(parts) > 2 and parts[-2] in SLD and len(tld) == 2 else 2
    reg = ".".join(parts[-reg_n:])
    subs = len(parts) - reg_n
    netloc = s.split("://", 1)[1].split("/", 1)[0]

    ind = []
    add = lambda w, t: ind.append({"weight": w, "text": t})
    if is_ip: add(30, "Menggunakan alamat IP sebagai pengganti nama domain.")
    if u.scheme == "http": add(20, "Tidak menggunakan HTTPS, sehingga data yang dikirim tidak terenkripsi.")
    if "@" in netloc: add(25, "Mengandung simbol @ yang dapat menyembunyikan tujuan sebenarnya.")
    if len(s) > 75: add(12, f"URL terlalu panjang ({len(s)} karakter).")
    if not is_ip and subs >= 3: add(15, f"Memiliki banyak subdomain ({subs} tingkat).")
    if "xn--" in host: add(25, "Menggunakan karakter internasional (punycode) yang bisa meniru domain lain.")
    if not is_ip and tld in RISKY_TLDS: add(15, f"Menggunakan akhiran domain .{tld} yang sering disalahgunakan.")
    if not is_ip and "-" in reg.split(".")[0]: add(8, "Nama domain mengandung tanda hubung (-).")
    if reg in SHORTENERS: add(15, "Menggunakan layanan pemendek tautan sehingga tujuan asli tersembunyi.")
    if port and port not in (80, 443): add(10, f"Menggunakan port tidak lazim ({port}).")
    found = [k for k in KEYWORDS if k in (host + u.path).lower()]
    if found: add(min(42, len(found) * 14), "Memuat kata yang sering dipakai pada phishing: " + ", ".join(found) + ".")
    if not is_ip:
        for brand, official in BRANDS.items():
            if brand in host and reg != official:
                add(35, f'Nama domain menyerupai merek "{brand}", tetapi bukan domain resminya ({official}).')
                break
    return {"url": s, "host": host, "indicators": ind}
