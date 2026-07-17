#!/bin/bash

# .env 파일이 존재하는 경우 환경 변수로 로드
if [ -f .env ]; then
    echo ".env 파일 발견: 환경 변수 로드 중..."
    # 주석(#)과 빈 줄을 제외하고 환경 변수로 export
    export $(grep -v '^#' .env | xargs)
else
    echo "경고: .env 파일이 없습니다. '.env.example' 파일을 복사해서 '.env'를 생성한 뒤 값을 채워주세요."
fi

# 가상환경의 python3로 main.py 실행
if [ -f .venv/bin/python3 ]; then
    .venv/bin/python3 main.py "$@"
else
    echo "오류: 가상환경(.venv)이 존재하지 않습니다. 먼저 setup을 실행하세요."
fi
