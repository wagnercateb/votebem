import os
from PyPDF2 import PdfReader

folder = r"."   # ← change to your folder path or leave "." for current folder

for file in os.listdir(folder):
    if file.lower().endswith(".pdf"):
        pdf_path = os.path.join(folder, file)
        txt_path = os.path.join(folder, os.path.splitext(file)[0] + ".txt")

        # Skip if TXT already exists
        if os.path.exists(txt_path):
            print(f"Skipping (TXT exists): {txt_path}")
            continue

        try:
            print(f"Converting: {pdf_path}")
            reader = PdfReader(pdf_path)
            text = ""

            for page in reader.pages:
                text += page.extract_text() or ""

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)

        except Exception as e:
            print(f"Error converting {file}: {e}")


print('_'*80)
print('Todos os pdfs foram convertidos para txt!')

