"""Model: analisis konten HTML (form, input password, iframe). Dipakai setelah scraper siap."""
from html.parser import HTMLParser


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = self.iframes = self.password_inputs = self.links = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form": self.forms += 1
        elif tag == "iframe": self.iframes += 1
        elif tag == "a": self.links += 1
        elif tag == "input" and a.get("type") == "password": self.password_inputs += 1


def analyze_content(html: str) -> list[dict]:
    c = _Collector()
    c.feed(html or "")
    ind = []
    if c.password_inputs: ind.append({"weight": 15, "text": "Halaman memiliki formulir yang meminta kata sandi."})
    if c.iframes: ind.append({"weight": 10, "text": f"Halaman memuat {c.iframes} iframe."})
    return ind
