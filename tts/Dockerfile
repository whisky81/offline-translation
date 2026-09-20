# Tang 1: tai giong tu Hugging Face.
# Tach rieng de tang cuoi khong dinh cache tai ve, va de doi danh sach giong
# khong bat build lai phan cai dat pip.
FROM python:3.12-slim AS voices

ARG TTS_VOICES="vi/vi_VN/vais1000/medium/vi_VN-vais1000-medium en/en_US/amy/medium/en_US-amy-medium"
ARG TTS_VOICE_REPO=rhasspy/piper-voices
ENV TTS_VOICES=$TTS_VOICES TTS_VOICE_REPO=$TTS_VOICE_REPO VOICE_DIR=/voices

COPY download_voices.py /download_voices.py
RUN python /download_voices.py


# Tang 2: Piper + onnxruntime + giong da tai. Khong co torch, khong co mang.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    VOICE_DIR=/voices \
    PORT=8100

# onnxruntime nap libgomp.so.1 luc chay. python:3.12-slim khong co san, va
# thieu no thi container chet ngay o 'import piper' voi loi kho doan.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir "piper-tts>=1.3,<2" \
 && useradd --system --uid 1034 tts

# onnxruntime thu ghi mot "telemetry device ID" luc import va that bai (user
# he thong khong co thu muc home), de lai mot dong canh bao moi lan khoi dong.
# Tat han thay vi tao cho cho no ghi: cong cu nay chay offline, khong co ly do
# gi de sinh va luu mot dinh danh may.
ENV ORT_DISABLE_TELEMETRY=1

COPY --from=voices /voices /voices
COPY server.py /app/server.py

USER tts
WORKDIR /app
EXPOSE 8100

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=30s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8100/health',timeout=4)" || exit 1

CMD ["python", "server.py"]
