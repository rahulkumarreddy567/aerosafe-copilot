FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN python -c "import subprocess, sys, tomllib; p=tomllib.load(open('pyproject.toml', 'rb'))['project']; deps=p['dependencies'] + p['optional-dependencies']['speech']; subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *deps])"
COPY README.md ./
COPY eval ./eval
COPY src ./src
RUN pip install --no-cache-dir --no-deps .
ENV AEROSAFE_AUDIT_PATH=/data/audit.jsonl
EXPOSE 8000
CMD ["uvicorn", "aerosafe.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
