import os
from bs4 import BeautifulSoup

source_dir = "isaiah.pegues.io"
output_dir = "text_versions"
os.makedirs(output_dir, exist_ok=True)

for root, _, files in os.walk(source_dir):
    for file in files:
        if file.endswith(".html"):
            input_path = os.path.join(root, file)
            relative_path = os.path.relpath(input_path, source_dir)
            output_path = os.path.join(output_dir, relative_path.replace(".html", ".txt"))
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(input_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
                text = soup.get_text(separator="\n", strip=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(text)

            print(f"Converted: {input_path} → {output_path}")