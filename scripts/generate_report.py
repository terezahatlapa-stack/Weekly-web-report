# scripts/generate_report.py
import requests
from bs4 import BeautifulSoup
import re
import os
from datetime import datetime
import csv
import math

# volitelné - pro grafy a práci s tabulkami
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------
# KONFIGURACE (upravit kdykoli)
# -----------------------
URLS = [
    "https://www.o2.cz/",
    "https://www.o2.cz/osobni/o2spolu",
    "https://www.o2.cz/osobni/oneplay"
]

CSV_PATH = "data/metrics.csv"
REPORTS_DIR = "reports"
GRAPH_PATH = os.path.join(REPORTS_DIR, "score_trend.png")
DATE_FMT = "%d.%m.%Y"

# -----------------------
# Pomocné funkce
# -----------------------
def safe_get(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 (compatible)"})
        return r
    except Exception as e:
        return None

def text_from_soup(soup):
    # vezmeme hlavní text z <article> nebo všechny <p>
    article = soup.find("article")
    if article:
        text = article.get_text(separator=" ", strip=True)
    else:
        ps = soup.find_all("p")
        text = " ".join(p.get_text(separator=" ", strip=True) for p in ps)
    # odstranit vícenásobné mezery
    text = re.sub(r"\s+", " ", text).strip()
    return text

def count_syllables(word):
    # jednoduchý heuristický odhad slabik (angl. orientovaný) — postačí pro srovnání
    word = word.lower()
    word = re.sub(r'[^a-záčďéěíňóřšťůúýž]', '', word)  # zachová i CZ znaky
    if len(word) <= 3:
        return 1
    # základní pravidlo: počet samohlásek jako slabiky
    sylls = re.findall(r'[aeiouyáéíóúůýěěů]', word)
    count = len(sylls)
    # úpravy heuristikou
    count -= len(re.findall(r'ia|io|ea|ee|ou|au', word))
    if count <= 0:
        count = 1
    return count

def flesch_reading_ease(text):
    # Flesch (upravený approximate; používáme pro relativní srovnání)
    sentences = re.split(r'[.!?]+', text)
    sentences = [s for s in sentences if s.strip()]
    num_sentences = max(1, len(sentences))
    words = re.findall(r'\w+', text)
    num_words = max(1, len(words))
    syllables = sum(count_syllables(w) for w in words)
    # Flesch formula (angl.)
    try:
        ASL = num_words / num_sentences
        ASW = syllables / num_words
        score = 206.835 - 1.015 * ASL - 84.6 * ASW
    except Exception:
        score = 50.0
    # normalizovat na 0-100
    score = max(0, min(100, score))
    return score

def normalize_score(val, minv=0, maxv=100):
    return max(0, min(100, (val - minv) / (maxv - minv) * 100))

# -----------------------
# Heuristické skórování
# -----------------------
def compute_performance_metrics(soup, resp):
    # jednoduché ukazatele: velikost HTML, počet skriptů, css, obrázků, TTFB approx via response.elapsed
    html_size = len(resp.content) if resp is not None else 0
    scripts = len(soup.find_all("script"))
    css = len(soup.find_all("link", rel=lambda x: x and 'stylesheet' in x))
    imgs = soup.find_all("img")
    img_count = len(imgs)
    # TTFB aproximace - response.elapsed gives total time; good enough for relative changes
    ttfb_ms = int(resp.elapsed.total_seconds() * 1000) if resp is not None else 0

    # Jednoduché skóre: menší html, méně skriptů -> lepší
    # nomalizace: html_size (0..500k), scripts (0..50), css (0..20), img_count (0..100), ttfb (0..2000 ms)
    w_html = 0.35
    w_scripts = 0.25
    w_css = 0.15
    w_imgs = 0.10
    w_ttfb = 0.15

    s_html = normalize_score(max(0, 500000 - html_size), 0, 500000)  # větší = horší -> invert
    s_scripts = normalize_score(max(0, 50 - scripts), 0, 50)
    s_css = normalize_score(max(0, 20 - css), 0, 20)
    s_imgs = normalize_score(max(0, 100 - img_count), 0, 100)
    s_ttfb = normalize_score(max(0, 2000 - ttfb_ms), 0, 2000)

    perf_score = (
        s_html * w_html +
        s_scripts * w_scripts +
        s_css * w_css +
        s_imgs * w_imgs +
        s_ttfb * w_ttfb
    )
    perf_score = int(max(0, min(100, perf_score)))
    return {
        "performance_score": perf_score,
        "html_size": html_size,
        "scripts": scripts,
        "css": css,
        "img_count": img_count,
        "ttfb_ms": ttfb_ms
    }

def compute_seo_metrics(soup):
    # title, meta description, h1,h2, canonical, structured data
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    md = ""
    meta_desc_tag = soup.find("meta", attrs={"name":"description"})
    if meta_desc_tag and meta_desc_tag.get("content"):
        md = meta_desc_tag.get("content").strip()
    h1s = soup.find_all("h1")
    h2s = soup.find_all("h2")
    canonical = ""
    can_tag = soup.find("link", rel="canonical")
    if can_tag and can_tag.get("href"):
        canonical = can_tag.get("href").strip()
    # structured data JSON-LD
    jsonld = soup.find_all("script", type="application/ld+json")
    structured_ok = len(jsonld) > 0

    # SEO score simple heuristic:
    # title presence, meta_desc length, canonical, structured data, one h1
    score = 0
    score += 25 if title else 0
    score += 25 if meta_desc_tag and 50 <= len(md) <= 320 else 0
    score += 15 if canonical else 0
    score += 20 if structured_ok else 0
    score += 15 if len(h1s) == 1 else 0

    score = int(max(0, min(100, score)))
    return {
        "seo_score": score,
        "title": title,
        "meta_desc": md,
        "h1_count": len(h1s),
        "h2_count": len(h2s),
        "canonical": canonical,
        "structured_ok": structured_ok
    }

def compute_ai_score(soup, text):
    # Heuristická B: víc odstavců, logická hierarchie (h1/h2), čitelnost, strukturovaný obsah
    paragraphs = soup.find_all("p")
    p_count = len(paragraphs)
    h1_count = len(soup.find_all("h1"))
    h2_count = len(soup.find_all("h2"))
    has_lists = len(soup.find_all(["ul","ol"])) > 0
    structured_ok = len(soup.find_all("script", type="application/ld+json")) > 0

    flesch = flesch_reading_ease(text)

    # weights
    w_p = 0.20
    w_h = 0.25
    w_f = 0.30
    w_list = 0.10
    w_struct = 0.15

    s_p = normalize_score(min(p_count, 20), 0, 20)
    s_h = normalize_score(max(0, (h1_count + 0.5*h2_count)), 0, 5)
    s_f = normalize_score(flesch, 0, 100)
    s_list = 100 if has_lists else 50
    s_struct = 100 if structured_ok else 40

    ai_score = int(
        s_p * w_p +
        s_h * w_h +
        s_f * w_f +
        s_list * w_list +
        s_struct * w_struct
    )
    ai_score = max(0, min(100, ai_score))
    return {
        "ai_score": ai_score,
        "flesch": flesch,
        "paragraphs": p_count,
        "h1_count": h1_count,
        "h2_count": h2_count,
        "has_lists": has_lists,
        "structured_ok": structured_ok
    }

def check_images(soup, base_url):
    imgs = soup.find_all("img")
    non_webp = []
    missing_alt = []
    for img in imgs:
        src = img.get("src") or img.get("data-src") or ""
        src = src.strip()
        # make absolute if needed
        if src.startswith("//"):
            src = "https:" + src
        if src.startswith("/"):
            src = base_url.rstrip("/") + src
        # ignore data: URIs
        if src.startswith("data:"):
            continue
        # extension check
        if not src.lower().endswith(".webp"):
            non_webp.append(src)
        alt = img.get("alt")
        if not alt or not alt.strip():
            missing_alt.append(src)
    return non_webp, missing_alt

# -----------------------
# CSV utilities
# -----------------------
def ensure_csv_header():
    if not os.path.exists(CSV_PATH):
        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["date","url","performance","seo","ai_score"])

def append_csv_row(date_str, url, perf, seo, ai):
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([date_str, url, perf, seo, ai])

def read_history_df():
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame(columns=["date","url","performance","seo","ai_score"])
    df = pd.read_csv(CSV_PATH, parse_dates=["date"], dayfirst=True, dayfirst_conflicts='infer', dayfirst_dayfirst=True)
    # CSV date stored as DD.MM.YYYY -> parse later in code; but pandas may not parse automatically — handle safe
    try:
        df['date'] = pd.to_datetime(df['date'], format=DATE_FMT)
    except Exception:
        df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
    return df

# -----------------------
# Main
# -----------------------
def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ensure_csv_header()
    today = datetime.now().strftime(DATE_FMT)
    sections = []
    summary_rows = []

    for url in URLS:
        print("Processing", url)
        resp = safe_get(url)
        if resp is None:
            sections.append((url, {"error":"request_failed"}))
            # still append a row with zeros
            append_csv_row(today, url, 0, 0, 0)
            continue

        soup = BeautifulSoup(resp.content, "lxml")
        text = text_from_soup(soup)

        perf = compute_performance_metrics(soup, resp)
        seo = compute_seo_metrics(soup)
        ai = compute_ai_score(soup, text)
        non_webp, missing_alt = check_images(soup, base_url=url)

        # append to CSV the main three scores
        append_csv_row(today, url, perf["performance_score"], seo["seo_score"], ai["ai_score"])

        # prepare section data for report
        section = {
            "url": url,
            "status_code": resp.status_code,
            "performance": perf,
            "seo": seo,
            "ai": ai,
            "non_webp": non_webp,
            "missing_alt": missing_alt
        }
        sections.append((url, section))
        summary_rows.append({"url": url, "performance": perf["performance_score"], "seo": seo["seo_score"], "ai": ai["ai_score"]})

    # --- ANALÝZA změn proti minulému měření ---
    df_hist = read_history_df()
    analysis_text = {}
    # get last measurement per url before today
    for entry in sections:
        url = entry[0]
        # historical rows for this url
        hist_rows = df_hist[df_hist['url'] == url].sort_values('date')
        last = None
        if not hist_rows.empty:
            last = hist_rows.iloc[-1]
        # if only today's row exists, last will be today's; to compare previous, take previous row
        prev = None
        if len(hist_rows) >= 2:
            prev = hist_rows.iloc[-2]
        # compute delta between latest and previous (if available)
        current_row = hist_rows.iloc[-1] if not hist_rows.empty else None
        change_lines = []
        if prev is not None and current_row is not None:
            perf_delta = int(current_row['performance'] - prev['performance'])
            seo_delta = int(current_row['seo'] - prev['seo'])
            ai_delta = int(current_row['ai_score'] - prev['ai_score'])
            # simple reasons: compare counts
            change_lines.append(f"- Performance: {perf_delta:+d} (z {int(prev['performance'])} → {int(current_row['performance'])})")
            change_lines.append(f"- SEO: {seo_delta:+d} (z {int(prev['seo'])} → {int(current_row['seo'])})")
            change_lines.append(f"- AI/LLM: {ai_delta:+d} (z {int(prev['ai_score'])} → {int(current_row['ai_score'])})")
            # add heuristické důvody (porovnáme html_size, scripts, img_count if available)
            # Try to estimate cause by re-fetching previous metrics is not stored fully; so we compare only CSV numbers.
            # For more precise causes, we'd need to keep extended history (could be added later).
        else:
            change_lines.append("- Není k dispozici předchozí měření pro porovnání.")
        analysis_text[url] = "\n".join(change_lines)

    # --- GRAF: souhrn (průměr přes URL) ---
    # vytvoříme DataFrame pivot: date x url, a průměry
    hist_df = read_history_df()
    if not hist_df.empty:
        # pivot: group by date, compute mean across URLs
        grouped = hist_df.groupby('date').agg({"performance":"mean","seo":"mean","ai_score":"mean"}).reset_index()
        # sort by date
        grouped = grouped.sort_values('date')
        # plot
        plt.figure(figsize=(9,4.5))
        plt.plot(grouped['date'], grouped['performance'], label='Performance')
        plt.plot(grouped['date'], grouped['seo'], label='SEO')
        plt.plot(grouped['date'], grouped['ai_score'], label='AI/LLM')
        plt.xlabel('Datum')
        plt.ylabel('Skóre (0-100)')
        plt.title('Dlouhodobý vývoj skóre (průměr přes sledované URL)')
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.4)
        plt.tight_layout()
        plt.savefig(GRAPH_PATH)
        plt.close()
    else:
        # pokud není historie, smažeme graf pokud existuje
        try:
            if os.path.exists(GRAPH_PATH):
                os.remove(GRAPH_PATH)
        except:
            pass

    # --- GENEROVÁNÍ MARKDOWN REPORTU ---
    report_date = datetime.now().strftime(DATE_FMT)
    report_file = os.path.join(REPORTS_DIR, f"report_{report_date}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"# Týdenní report – {report_date}\n\n")
        # vložíme graf (pokud existuje)
        if os.path.exists(GRAPH_PATH):
            f.write("## 📈 Dlouhodobý vývoj skóre\n")
            f.write(f"![Vývoj skóre]({os.path.basename(GRAPH_PATH)})\n\n")
        for url, s in sections:
            f.write(f"---\n\n")
            f.write(f"## 🔵 {url}\n\n")
            if isinstance(s, dict) and s.get("error") == "request_failed":
                f.write("**Chyba:** Nelze načíst stránku (request failed).\n\n")
                continue
            st = s
            f.write(f"- HTTP status: {st['status_code']}\n")
            f.write(f"- **Performance score:** {st['performance']['performance_score']}\n")
            f.write(f"  - LCP aproximace (html size): {st['performance']['html_size']} bytes\n")
            f.write(f"  - TTFB approx: {st['performance']['ttfb_ms']} ms\n")
            f.write(f"- **SEO score:** {st['seo']['seo_score']}\n")
            f.write(f"  - Title: {'✅' if st['seo']['title'] else '❌'}\n")
            f.write(f"  - Meta description: {'✅' if st['seo']['meta_desc'] else '❌'}\n")
            f.write(f"  - H1 count: {st['seo']['h1_count']}\n")
            f.write(f"  - Structured data (JSON-LD): {'✅' if st['seo']['structured_ok'] else '❌'}\n")
            f.write(f"- **AI/LLM score:** {st['ai']['ai_score']}\n")
            f.write(f"  - Flesch reading ease: {st['ai']['flesch']:.1f}\n")
            f.write("\n### 📉 Změny od minulého měření\n")
            f.write(analysis_text.get(url, "- Není k dispozici předchozí měření.\n") + "\n\n")

            # Obrázky - tabulka
            f.write("### 📷 Problémy s obrázky\n\n")
            if st['non_webp'] or st['missing_alt']:
                f.write("| Typ problému | URL obrázku | Detail |\n")
                f.write("|--------------|------------:|--------|\n")
                for u in st['non_webp']:
                    f.write(f"| Non-WEBP | {u} | doporučeno WEBP |\n")
                for u in st['missing_alt']:
                    f.write(f"| Chybí alt | {u} | alt atribut prázdný/neexistuje |\n")
            else:
                f.write("Žádné problémy s obrázky.\n")
            f.write("\n")

        f.write("---\n\n")
        f.write("### 🔎 Doporučení (automatické)\n")
        f.write("- Kontrolovat obrázky, doplnit alt atributy.\n")
        f.write("- Optimalizovat velké HTML/velké množství skriptů pokud performance klesá.\n")

    print("Report vytvořen:", report_file)
    print("CSV aktualizováno:", CSV_PATH)
    # konec main

if __name__ == "__main__":
    main()
