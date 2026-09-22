FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /suite

COPY pyproject.toml README.md ./
COPY app ./app
COPY tools ./tools
RUN pip install --no-cache-dir -e . && playwright install --with-deps chromium

COPY tests_after ./tests_after
COPY tests_before ./tests_before
COPY tests_repo ./tests_repo
COPY measurements ./measurements
COPY .github ./.github

CMD ["pytest", "tests_after"]
