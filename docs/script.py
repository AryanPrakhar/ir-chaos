import os

def aggregate_markdown(folder_path, exclude_files=None):
    if exclude_files is None:
        exclude_files = []
    aggregated_text = ""
    for filename in os.listdir(folder_path):
        if filename.endswith(".md") and filename not in exclude_files:
            file_path = os.path.join(folder_path, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                aggregated_text += f.read() + "\n\n"
    return aggregated_text

# Example usage:
folder = "/home/ubuntu/dev/lfx/krkn-hub/docs"
excludes = [    "all_scenarios_env.md",
    "contribute.md",
    "test_your_changes.md",
    "error_cases.md",
    "cerberus.md",
    "chaos-recommender.md"]  # Add any files you want to exclude
result = aggregate_markdown(folder, excludes)

# Save or print the result
with open("aggregated_docs.md", "w", encoding="utf-8") as out_file:
    out_file.write(result)