#!/usr/bin/env python3
import sys
from pathlib import Path
from pdfminer.high_level import extract_text

def convert_pdf_to_txt(pdf_dir):
    """Converte PDFs para TXT, ignorando erros"""
    pdf_dir = Path(pdf_dir)
    
    for pdf_file in pdf_dir.glob("*.pdf"):
        txt_file = pdf_file.with_suffix(".txt")
        
        try:
            print(f"Convertendo {pdf_file.name}...", end=" ")
            text = extract_text(str(pdf_file))
            
            if text.strip():
                with open(txt_file, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(text)
                print("✓")
            else:
                print("✗ (vazio)")
        except Exception as e:
            print(f"✗ ({str(e)[:30]})")
            continue

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 convert_pdfs.py <diretório>")
        sys.exit(1)
    
    convert_pdf_to_txt(sys.argv[1])