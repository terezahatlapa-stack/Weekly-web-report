import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

# -----------------------------
# CONFIG – seznam sledovaných URL
# -----------------------------
URLS = [
    "https://www.o2.cz/",
    "https://www.o2.cz/osobni/o2spolu",
    "https://www.o2.cz/osobni/oneplay"
]

# -----------------------------
# HELPERS
# -----------------------------
def fetch_html(url):
    """Stáhne HTML stránky."""
    try:
        r = requests.get(url, timeout=20)
        return r.text
    except:
        return ""


def fetch_pagespeed(url, strategy):
    """Stáhne performance z PSI pro mobile/desktop."""
    api = (
        "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        f"?url={url}&strategy={strategy}"
    )
    try:
        r = requests.get(api, timeout=30).json()
        score = r["lighthouseResult"]["categories"]["performance"]["score"]
        return int(score * 100)
    except:
        return 0


def measure_seo(soup):
    """SEO skóre."""
    score = 100
    issues = []

    if not soup.find("title"):
        score -= 10
        issues.append("Chybí <title>")

    if not soup.find("meta", attrs={"name": "description"}):
        score -= 10
        issues.append("Chybí meta description")

    h1 = soup.find_all("h1")
    if len(h1) == 0:
        score -= 10
        issues.append("Chybí H1")
    if len(h1) > 1:
        score -= 5
        issues.append("Více než jedno H1")

    return max(10, score), issues


def measure_ai_score(soup):
    """AI/LLM skóre."""
    score = 100
    issues = []

    text = soup.get_text(" ", strip=True)
    words = len(text.split())

    if words < 200:
        score -= 20
        issues.append("Málo textu")
    elif words < 500:
        score -= 10

    if len(soup.find_all("h2")) < 2:
        score -= 10
        issues.append("Málo H2 nadpisů")

    return max(10, score), issues


def analyze_images(soup):
    """Najde obrázky s problémy."""
    problems = []
    for img in soup.find_all("img"):
        src = img.get("src") or ""
        alt = img.get("alt")

        if not src.startswith("http"):
            continue

        if not src.lower().endswith(".webp"):
            problems.append(("Non-WEBP", src, "Obrázek není ve formátu WEBP"))

        if not alt or alt.strip() == "":
            problems.append(("Chybí ALT", src, "Chybějící nebo prázdný ALT"))

    return problems

# -----------------------------
# PŘÍPRAVA SLOŽEK A CSV
# -----------------------------
os.makedirs("reports", exist_ok=True)
os.makedirs("data", exist_ok=True)

csv_path = "data/metrics.csv"

if not os.path.exists(csv_path):
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("date,url,mobile_perf,desktop_perf,seo,ai\n")

today = datetime.now().strftime("%d.%m.%Y")
report_path = f"reports/report_{today}.md"

rows = []
sections = []

# -----------------------------
# HLAVNÍ LOGIKA ANALÝZY
# -----------------------------
for url in URLS:

    # PSI performance
    mobile_perf = fetch_pagespeed(url, "mobile")
    desktop_perf = fetch_pagespeed(url, "desktop")

    # HTML analýza
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    seo, seo_issues = measure_seo(soup)
    ai, ai_issues = measure_ai_score(soup)
    img_problems = analyze_images(soup)

    # Uložení do CSV
    rows.append([today, url, mobile_perf, desktop_perf, seo, ai])

    # -----------------------------
    # SEKCIONÁLNÍ REPORT
    # -----------------------------
    s = f"## 🔵 {url}\n\n"
    s += f"### 📱 Mobile Performance: **{mobile_perf}**\n"
    s += f"### 🖥 Desktop Performance: **{desktop_perf}**\n"
    s += f"### 🔍 SEO: **{seo}**\n"
    s += f"### 🤖 AI/LLM: **{ai}**\n\n"

    if seo_issues or ai_issues:
        s += "### 🚨 Zjištěné problémy:\n"
        for i in seo_issues: s += f"- SEO: {i}\n"
        for i in ai_issues: s += f"- AI: {i}\n"
        s += "\n"

    if img_problems:
        s += "### 🖼 Problémy s obrázky\n\n"
        s += "| Typ | URL | Detail |\n|-----|-----|--------|\n"
        for typ, src, detail in img_problems:
            s += f"| {typ} | {src} | {detail} |\n"
        s += "\n"
    else:
        s += "### ✔ Obrázky jsou v pořádku\n\n"

    sections.append(s)

# -----------------------------
# DOPLNĚNÍ CSV
# -----------------------------
with open(csv_path, "a", encoding="utf-8") as f:
    for r in rows:
        f.write(",".join(map(str, r)) + "\n")

# -----------------------------
# TVORBA GRAFŮ
# -----------------------------
df = pd.read_csv(csv_path)

# --- Graf 1: Performance ---
perf = df.groupby("date")[["mobile_perf", "desktop_perf"]].mean()

plt.figure(figsize=(10, 5))
plt.plot(perf.index, perf["mobile_perf"], label="Mobile")
plt.plot(perf.index, perf["desktop_perf"], label="Desktop")
plt.title("Vývoj Performance")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("reports/performance_trend.png")
plt.close()

# --- Graf 2: SEO + AI ---
seo_ai = df.groupby("date")[["seo", "ai"]].mean()

plt.figure(figsize=(10, 5))
plt.plot(seo_ai.index, seo_ai["seo"], label="SEO")
plt.plot(seo_ai.index, seo_ai["ai"], label="AI/LLM")
plt.title("Vývoj SEO a AI/LLM skóre")
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("reports/seo_ai_trend.png")
plt.close()

# -----------------------------
# TVORBA REPORTU
# -----------------------------
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"# Týdenní report – {today}\n\n")

    f.write("## 📈 Vývoj Performance\n")
    f.write("![Performance](performance_trend.png)\n\n")

    f.write("## 📘 Vývoj SEO + AI/LLM skóre\n")
    f.write("![SEO AI](seo_ai_trend.png)\n\n")

    f.writelines(sections)

print("Report hotový:", report_path)
print("CSV aktualizováno:", csv_path)
