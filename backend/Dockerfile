FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/appuser/.cache/huggingface

WORKDIR /app

# Runtime library used by numerical/ML packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU-only PyTorch, matching your installed version.
RUN pip install --no-cache-dir torch==2.14.1 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Run the application without root privileges.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/chroma_db /home/appuser/.cache/huggingface \
    && chown -R appuser:appuser /app/chroma_db /home/appuser/.cache

COPY --chown=appuser:appuser app ./app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]