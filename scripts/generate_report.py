import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

# -----------------------------
# ✦ CONFIG – zde můžeš přidávat URL
# -----------------------------
URLS = [
    "https://www.o2.cz/",
    "https://www.o2.cz/osobni/o2spolu",
    "https://www.o2.cz/osobni/oneplay"
]

# -----------------------------
# ✦ HELPER FUNCTIONS
# -----------------------------
def fetch_html(url):
    """Stáhne HTML obsahu stránky."""
    try:
        r = requests.get(url, timeout=20)
        return r.text, r.elapsed.total_seconds(), len(r.content)
    except:
        return "", 0, 0


def measure_performance(load_time, size):
    """Výpočet performance skóre (0–100)."""
    score = 100
    if load_time > 1: score -= (load_time - 1) * 15
    if size > 800000: score -= (size - 800000) / 20000
    return max(10, min(100, int(score)))


def measure_seo(soup):
    """SEO metriky: title, description, H1 struktura."""
    score = 100
    issues = []

    title = soup.find("title")
    if not title:
        score -= 10
        issues.append("Chybí <title>")

    meta_desc = soup.find("meta", attrs={"name": "description"})
    if not meta_desc:
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
    """AI/LLM skóre založené na struktuře textu."""
    score = 100
    issues = []

    text = soup.get_text(" ", strip=True)
    word_count = len(text.split())

    if word_count < 200:
        score -= 20
        issues.append("Stránka má málo textu")
    elif word_count < 500:
        score -= 10

    h2 = soup.find_all("h2")
    if len(h2) < 2:
        score -= 10
        issues.append("Málo nadpisů H2")

    return max(10, score), issues


def analyze_images(soup):
    """Najde obrázky bez altů nebo mimo WEBP."""
    problems = []

    for img in soup.find_all("img"):
        src = img.get("src") or ""
        alt = img.get("alt")

        if not src.startswith("http"):
            continue

        if not src.lower().endswith(".webp"):
            problems.append(("Non-WEBP", src, "Obrázek není ve formátu WEBP"))

        if alt is None or alt.strip() == "":
            problems.append(("Chybí alt", src, "Prázdný nebo chybějící alt"))

    return problems


# -----------------------------
# ✦ PŘÍPRAVA SOUBORŮ
# -----------------------------
os.makedirs("reports", exist_ok=True)
os.makedirs("data", exist_ok=True)

csv_path = "data/metrics.csv"
if not os.path.exists(csv_path):
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("date,url,performance,seo,ai\n")

today = datetime.now().strftime("%d.%m.%Y")
report_path = f"reports/report_{today}.md"

rows_for_csv = []
report_sections = []

# -----------------------------
# ✦ HLAVNÍ LOGIKA PRO KAŽDOU URL
# -----------------------------
for url in URLS:

    html, load_time, size = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    perf = measure_performance(load_time, size)
    seo, seo_issues = measure_seo(soup)
    ai, ai_issues = measure_ai_score(soup)
    img_problems = analyze_images(soup)

    rows_for_csv.append([today, url, perf, seo, ai])

    # Sekce reportu
    section = f"## 🔵 {url}\n\n"
    section += f"### ⭐ Performance: **{perf}**\n"
    section += f"### ⭐ SEO: **{seo}**\n"
    section += f"### ⭐ AI/LLM: **{ai}**\n\n"

    # SEO issues
    if seo_issues or ai_issues:
        section += "### 📊 Zjištěné problémy:\n"
        for issue in seo_issues:
            section += f"- SEO: {issue}\n"
        for issue in ai_issues:
            section += f"- AI/LLM: {issue}\n"
        section += "\n"

    # Tabulka obrázků
    if img_problems:
        section += "### 📉 Problémy s obrázky\n\n"
        section += "| Typ | URL | Detail |\n"
        section += "|-----|-----|--------|\n"
        for typ, src, detail in img_problems:
            section += f"| {typ} | {src} | {detail} |\n"
        section += "\n"
    else:
        section += "### ✔ Všechny obrázky v pořádku\n\n"

    report_sections.append(section)

# -----------------------------
# ✦ GENEROVÁNÍ CSV
# -----------------------------
with open(csv_path, "a", encoding="utf-8") as f:
    for row in rows_for_csv:
        f.write(",".join(map(str, row)) + "\n")

# -----------------------------
# ✦ GRAF – JEDEN S TŘEMI LINKAMI
# -----------------------------
df = pd.read_csv(csv_path)

pivot = df.pivot(index="date", columns="url", values=["performance", "seo", "ai"])
pivot_mean = df.groupby("date")[["performance", "seo", "ai"]].mean()

plt.figure(figsize=(10, 5))
plt.plot(pivot_mean.index, pivot_mean["performance"], label="Performance")
plt.plot(pivot_mean.index, pivot_mean["seo"], label="SEO")
plt.plot(pivot_mean.index, pivot_mean["ai"], label="AI/LLM")
plt.legend()
plt.title("Vývoj skóre")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("reports/score_trend.png")
plt.close()

# -----------------------------
# ✦ VYTVOŘENÍ REPORTU
# -----------------------------
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"# Týdenní report – {today}\n\n")
    f.write("## 📈 Dlouhodobý vývoj skóre\n")
    f.write("![Vývoj skóre](score_trend.png)\n\n")
    f.writelines(report_sections)

print("Report hotový:", report_path)
print("CSV aktualizováno:", csv_path)
