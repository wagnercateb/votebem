#!/usr/bin/env python3
import os
import pdfplumber
from markitdown import MarkItDown

FOLDER = "."  # change this or keep "." for current directory


def convert_with_markitdown(pdf_path):
    """Try MarkItDown conversion. Return Markdown string or None."""
    try:
        md = MarkItDown(enable_plugins=False)
        result = md.convert(pdf_path)
        return getattr(result, "markdown", None) or result.text_content
    except Exception:
        return None


def convert_with_pdfplumber(pdf_path):
    """Fallback conversion using pdfplumber, returning Markdown text."""
    md_lines = [f"# {os.path.basename(pdf_path)}", ""]
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                md_lines.append(f"\n---\n\n## Page {i}\n\n{text}")
    except Exception as e:
        raise RuntimeError(f"pdfplumber failed: {e}")
    
    return "\n".join(md_lines)


def convert_pdf_to_md(pdf_path, md_path):
    print(f"→ Converting: {pdf_path}")

    # Try MarkItDown first
    md_content = convert_with_markitdown(pdf_path)
    
    if md_content and md_content.strip():
        print("   ✓ MarkItDown succeeded.")
    else:
        print("   ⚠ MarkItDown failed. Falling back to pdfplumber...")
        md_content = convert_with_pdfplumber(pdf_path)
        print("   ✓ pdfplumber fallback succeeded.")

    # Write Markdown file
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)


def main():
    for fname in os.listdir(FOLDER):
        if fname.lower().endswith(".pdf"):
            pdf_path = os.path.join(FOLDER, fname)
            md_path = os.path.join(FOLDER, os.path.splitext(fname)[0] + ".md")

            if os.path.exists(md_path):
                print(f"Skipping (MD exists): {md_path}")
                continue

            try:
                convert_pdf_to_md(pdf_path, md_path)
            except Exception as e:
                print(f"❌ Failed to convert {fname}: {e}")


if __name__ == "__main__":
    main()
