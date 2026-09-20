# Tang 1: tai model tu Hugging Face va convert sang CTranslate2 int8.
# PyTorch chi can o day, KHONG di vao image cuoi.
FROM python:3.12-slim AS converter

ARG MODEL_ID=VietAI/envit5-translation
ARG QUANT=int8
ENV MODEL_ID=$MODEL_ID QUANT=$QUANT OUT_DIR=/ct2 HF_HUB_DISABLE_TELEMETRY=1

RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
 && pip install --no-cache-dir "ctranslate2>=4.5,<5" "transformers>=4.40,<5" sentencepiece protobuf

COPY convert.py /convert.py
RUN python /convert.py


# Tang 2: chi CTranslate2 + tokenizer. Khong co torch -> image nho hon nhieu.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    MODEL_DIR=/model \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN pip install --no-cache-dir "ctranslate2>=4.5,<5" "transformers>=4.40,<5" sentencepiece \
 && useradd --system --uid 1033 engine

COPY --from=converter /ct2 /model
COPY server.py /app/server.py

USER engine
WORKDIR /app
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=60s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=4)" || exit 1

CMD ["python", "server.py"]
