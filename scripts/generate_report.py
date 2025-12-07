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
    """
    Získá performance skóre (0-100) z PageSpeed Insights bez API klíče.
    strategy: "mobile" nebo "desktop"
    Vrací int (0-100).
    """
    base = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": url,
        "strategy": strategy,
        "category": "performance"
    }
    try:
        r = requests.get(base, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        # cesta v JSONu: lighthouseResult.categories.performance.score (0..1 float)
        score = data.get("lighthouseResult", {}) \
                    .get("categories", {}) \
                    .get("performance", {}) \
                    .get("score", None)
        if score is None:
            print(f"[PSI] No performance score for {url} ({strategy}) - JSON keys missing")
            return 0
        # score je float 0..1, převedeme na 0..100 int
        try:
            return int(float(score) * 100)
        except Exception:
            return 0
    except Exception as e:
        # vypiš důvod do logu (uvidíš to v Actions)
        print(f"[PSI] Error fetching PSI for {url} ({strategy}): {e}")
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
# -----------------------------
# ✦ BEZPEČNÉ NAČTENÍ, ČIŠTĚNÍ A NORMALIZACE CSV
# -----------------------------
import csv

def load_and_clean_csv(path):
    # přečteme surově (abychom viděli i špatné řádky)
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for r in reader:
            # strip každé položky
            rows.append([c.strip() for c in r])

    if not rows or len(rows) == 1:
        # žádná data kromě hlavičky nebo prázdný soubor -> vrátíme prázdný DF se sloupci, které očekáváme
        expected_cols = ["date","url","mobile_perf","desktop_perf","seo","ai"]
        return pd.DataFrame(columns=expected_cols)

    header = rows[0]
    good_rows = []
    for r in rows[1:]:
        # přijmeme pouze řádky se stejným počtem polí jako hlavička a bez úplně prázdných (vše prázdné)
        if len(r) == len(header) and any(cell != "" for cell in r):
            good_rows.append(r)

    # vytvoříme DF podle hlavičky, pokud je hlavička nečekaná, doplníme chybějící sloupce
    df = pd.DataFrame(good_rows, columns=header)

    # očistíme duplicity a whitespace
    df = df.drop_duplicates().reset_index(drop=True)

    # standardizujeme názvy sloupců (malá písmena)
    df.columns = [c.strip() for c in df.columns]

    # zajistíme očekávané sloupce (pokud chybí, doplníme s nulami)
    expected = ["date","url","mobile_perf","desktop_perf","seo","ai"]
    for col in expected:
        if col not in df.columns:
            df[col] = 0

    # přetypujeme číselné sloupce na int (chybné hodnoty -> 0)
    for col in ["mobile_perf","desktop_perf","seo","ai"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # očistíme date sloupec (udržujeme ve formátu DD.MM.YYYY) — odstraníme whitespace
    df["date"] = df["date"].astype(str).str.strip()

    # přepíšeme CSV (čistá verze) zpět (zachováme pořadí expected sloupců)
    df_to_write = df[expected]
    df_to_write.to_csv(path, index=False, encoding="utf-8")

    return df_to_write

# načti a vyčisti CSV
df = load_and_clean_csv(csv_path)

# pokud je df prázdný (žádná data), vytvoříme prázdné struktury pro grafy
if df.empty:
    # vytvoříme prázdné DataFrame se správnými sloupci, aby zbytek kódu nepadl
    df = pd.DataFrame(columns=["date","url","mobile_perf","desktop_perf","seo","ai"])


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
    f.write("![Performance](../reports/performance_trend.png)\n\n")
    
    f.write("## 📘 Vývoj SEO + AI/LLM skóre\n")
    f.write("![SEO AI](../reports/seo_ai_trend.png)\n\n")
    
    f.writelines(sections)

print("Report hotový:", report_path)
print("CSV aktualizováno:", csv_path)
