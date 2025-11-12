from datetime import datetime
import csv
import os

# Vytvoření složek, pokud neexistují
os.makedirs("data", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# Datum ve formátu DD.MM.YYYY
today = datetime.now().strftime("%d.%m.%Y")

# Testovací data (zatím napevno)
performance_score = 85
LCP = 2400
CLS = 0.03
FID_INP = 160
TTFB = 420
SEO_score = 91
LLM_scoring = 70

# CSV cesta
csv_path = "data/metrics.csv"

# Pokud CSV neexistuje, vytvoří se s hlavičkou
file_exists = os.path.isfile(csv_path)
with open(csv_path, "a", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(["date", "performance_score", "LCP", "CLS", "FID_INP", "TTFB", "SEO_score", "LLM_scoring"])
    writer.writerow([today, performance_score, LCP, CLS, FID_INP, TTFB, SEO_score, LLM_scoring])

# Markdown report
report_path = f"reports/report_{today.replace('.', '-')}.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"""### Report – {today}

#### 🔹 Performance
- Performance score: {performance_score}
- LCP: {LCP/1000:.2f} s
- CLS: {CLS}
- INP: {FID_INP} ms
- TTFB: {TTFB} ms

#### 🔹 SEO
- SEO score: {SEO_score}
- Titulek: ✅
- Meta description: ✅
- Structured data: ❌ chybí

#### 🔹 AI/LLM čitelnost
- LLM scoring: {LLM_scoring}/100

#### 🔹 Obrázky
- Obrázky ve WebP: 100 %
- Obrázky s alt atributem: 100 %
""")

print(f"Vytvořen report: {report_path}")
