"""Convert model HF sang CTranslate2 int8. Chi chay o tang build cua Docker."""
import os
import sys

from ctranslate2.converters import TransformersConverter
from transformers import AutoTokenizer

MODEL = os.environ.get("MODEL_ID", "VietAI/envit5-translation")
OUT = os.environ.get("OUT_DIR", "/ct2")
QUANT = os.environ.get("QUANT", "int8")

print(f"Convert {MODEL} -> {OUT} ({QUANT})", flush=True)
TransformersConverter(MODEL).convert(OUT, quantization=QUANT, force=True)

# Luu tokenizer canh model de tang chay khong can tai lai tu mang.
print("Luu tokenizer", flush=True)
AutoTokenizer.from_pretrained(MODEL).save_pretrained(OUT)

total = sum(os.path.getsize(os.path.join(r, f))
            for r, _, fs in os.walk(OUT) for f in fs)
print(f"Xong: {total/1e6:.0f} MB", flush=True)
sys.exit(0)
