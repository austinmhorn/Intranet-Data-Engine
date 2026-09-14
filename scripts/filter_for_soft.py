import csv

from config import NOTION_DATA_FILE, NOTION_DATA_SOFT_FILE


with open(NOTION_DATA_FILE, "r", newline="", encoding="utf-8-sig") as infile:
    reader = csv.DictReader(infile)

    with open(NOTION_DATA_SOFT_FILE, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
        writer.writeheader()

        for row in reader:
            if row.get("Location", "").strip() == "Corporate Office":
                if row.get("Active", "").strip() == "TRUE":
                    writer.writerow(row)

print(f"Filtered file written to: {NOTION_DATA_SOFT_FILE}")