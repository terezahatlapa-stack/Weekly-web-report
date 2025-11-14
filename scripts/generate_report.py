import os
from datetime import datetime

# --- Ensure directories exist ---
os.makedirs("reports", exist_ok=True)
os.makedirs("data", exist_ok=True)

# --- Prepare date ---
today = datetime.now().strftime("%d.%m.%Y")
report_filename = f"reports/report_{today}.md"

# --- Create CSV if not exists ---
csv_path = "data/metrics.csv"
if not os.path.exists(csv_path):
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("date,performance,seo,ai_score\n")

# --- Append test values to CSV ---
with open(csv_path, "a", encoding="utf-8") as f:
    f.write(f"{today},80,75,70\n")

# --- Create simple test Markdown report ---
with open(report_filename, "w", encoding="utf-8") as f:
    f.write(f"# Týdenní report – {today}\n\n")
    f.write("Toto je testovací report, který potvrzuje, že workflow funguje.\n")
    f.write("- Performance: 80\n")
    f.write("- SEO: 75\n")
    f.write("- AI/LLM score: 70\n")

print("Report vytvořen:", report_filename)
print("CSV aktualizováno:", csv_path)
