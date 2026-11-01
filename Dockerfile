# Merge AI Kokoro TTS service - Hugging Face Spaces (Docker SDK), CPU only.
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends espeak-ng libsndfile1 \
 && rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces run the container as user 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# CPU-only PyTorch (about 200 MB instead of several GB of CUDA libraries).
RUN pip install --no-cache-dir --user torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt \
 && python -m spacy download en_core_web_sm

# Bake the Kokoro model and the am_liam voice into the image,
# so a restart never has to download them again.
COPY --chown=user preload.py .
RUN python preload.py

COPY --chown=user server.py .

EXPOSE 7860
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
