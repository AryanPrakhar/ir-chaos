import json
import csv

# Input and output file paths
input_json = "edge.json"
output_csv = "edge-cases.csv"

# Read the JSON data
with open(input_json, "r", encoding="utf-8") as f:
    data = json.load(f)

# Write to CSV
with open(output_csv, "w", newline='', encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=["query", "label", "type"])
    writer.writeheader()
    for entry in data:
        writer.writerow({
            "query": entry.get("query", ""),
            "label": entry.get("label", ""),
            "type": entry.get("type", "")
        })

print(f"CSV written to {output_csv}")