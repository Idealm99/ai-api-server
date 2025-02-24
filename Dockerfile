# 1. 베이스 이미지 설정
FROM python:3.11

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 환경 변수 설정 (환경 변수 파일 .env 사용 가능)
ENV PYTHONUNBUFFERED=1

# 4. 필요한 파일 복사
COPY requirements.txt .

# 5. 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 6. 애플리케이션 코드 복사
COPY . .

# 7. FastAPI 실행 (Uvicorn 사용)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
