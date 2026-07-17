# 🏢 내 손안의 맞춤형 임대주택 알리미 (hangbok_is_nearby)

> **"행복은 늘 가까이에 있습니다."**  
> 마이홈 포털에서 매일 신규 분양/임대주택 공고를 실시간 수집하고, **Gemini AI**를 활용해 사용자 프로필 기반의 청약 자격 요건을 자동으로 심사하여 텔레그램으로 알려주는 스마트 비서 서비스입니다.

---

## 🌟 핵심 기능

1. **자동화된 맞춤 지역 수집 (1차 필터링)**
   * 경기 광명시 거주, 서울 용산구 직장인 타겟에 맞춘 **서울/경기/인천** 거주 및 생활권 맞춤형 공고 필터링.
   * 공고 게재일과 상관없이 **접수 시작 당일 아침**에 사용자에게 안내하도록 날짜 매칭 설계.

2. **지능형 다중 모델 폴백 (Dynamic Fallback)**
   * API 쿼터(429 한도 초과) 또는 특정 모델의 서버 순간 에러에 대응하여 가용한 후보 모델을 차례로 자동 스캔하여 분석을 완수합니다.
   * 폴백 후보군 순서: `gemini-2.0-flash` ➡️ `gemini-flash-latest` (1.5 Flash) ➡️ `gemini-3.5-flash` ➡️ `gemini-2.5-flash`

3. **고성능 PDF 인라인 심사 (2차 필터링)**
   * 신규 발급된 API 키(`AQ.` 시작 규격)의 Google Discovery API 호환 오류 우회를 위해, 대용량 공고문 PDF 파일 바이트를 메모리에 로드해 직접 전송(Inline bytes)하여 정확하게 입주 적합도를 비교합니다.
   * 나이(만 33세), 미혼 여부, 세대주 조건, 월평균 소득(연 5,000만 원, 월평균 약 416만 원), 거주/직장 위치 및 자산 요건 대조.

4. **깔끔한 통합 알림 딜리버리 (Single Telegram Bubble)**
   * **적합 공고:** 텔레그램 메시지 본문에 자격 요건 분석 결과 및 바로가기 링크 노출.
   * **부적합 공고:** 텔레그램 대화방을 어지럽히지 않도록 상세 탈락 사유(소득 초과, 연령 미달 등)를 깔끔하게 **1장의 PDF 파일로 합성하여 전송**.
   * **통합 레이아웃:** 텔레그램 캡션 길이 한계(1024자) 분석을 거쳐 **텍스트 알림과 PDF 파일을 하나의 말풍선으로 묶어서** 깔끔하게 전송합니다.

---

## 🛠️ 기술 스택 및 라이브러리

* **Language:** Python 3.9+
* **Libraries:**
  * `BeautifulSoup4` (MyHome HTML 파싱)
  * `google-generativeai` (Gemini LLM 활용 입주 자격 조건 검증)
  * `requests` (AJAX API 호출 및 PDF 다운로드, 텔레그램 API 통신)
  * `reportlab` (한글 폰트 적용된 자격 부적합 요약 PDF 리포트 빌드)
* **Execution Environment:** GitHub Actions (Cron Scheduler)

---

## 📂 프로젝트 구조

```text
hangbok_is_nearby/
├── .github/
│   └── workflows/
│       └── housing_alert.yml  # GitHub Actions 서버리스 크론 스케줄러
├── .env.example               # 환경 변수 템플릿 파일
├── README.md                  # 본 설명서
├── get_chat_id.py             # 텔레그램 봇 채팅 ID 수집 툴
├── main.py                    # 알리미 메인 파이프라인 엔진
└── run.sh                     # 로컬 실행 헬퍼 쉘 스크립트
```

---

## 🚀 로컬 설치 및 사용 방법

### 1. 가상환경 구축 및 의존성 패키지 설치
```bash
# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate

# 의존성 패키지 설치
pip install -r requirements.txt  # 또는 pip install requests beautifulsoup4 google-generativeai reportlab
```

### 2. 환경 변수 설정
`.env.example` 파일을 복사하여 `.env` 파일을 생성하고 본인의 API 키와 텔레그램 토큰을 채워 넣습니다.
```bash
cp .env.example .env
vi .env
```

**설정 필드 설명:**
* `GEMINI_API_KEY`: Google AI Studio에서 발급받은 API 키
* `TELEGRAM_BOT_TOKEN`: 텔레그램 BotFather를 통해 발급받은 봇 토큰
* `TELEGRAM_CHAT_ID`: 알림을 받을 사용자의 텔레그램 채팅방 ID (`get_chat_id.py` 실행을 통해 파악 가능)

### 3. 테스트 모드 실행
오늘 접수를 시작하는 공고가 없는 경우, 특정 날짜를 가정하고 모의 테스트를 해볼 수 있습니다.

```bash
# 2026년 7월 20일 날짜를 가정하여 실행 (성남 금토지구 및 영구임대 포함 12건 분석 시뮬레이션)
./run.sh 2026-07-20

# Gemini API 호출 없이 메시지/PDF UI 레이아웃만 테스트하고 싶은 경우
./run.sh 2026-07-20 --mock
```

---

## 🤖 GitHub Actions 서버리스 스케줄러 구축 방법

매일 아침 자동으로 공고를 수집하고 알림을 주기 위해 GitHub Actions의 서버리스 환경을 구성합니다.

### 1. 워크플로우 파일 생성
`.github/workflows/housing_alert.yml` 경로에 아래 설정 내용을 담아 생성합니다.

```yaml
name: Daily Housing Announcement Alert

on:
  schedule:
    # 매일 아침 한국 시간(KST) 오전 8시 30분에 실행 (UTC 기준 전날 23:30)
    - cron: '30 23 * * *'
  workflow_dispatch: # 수동 실행 지원

jobs:
  alert:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests beautifulsoup4 google-generativeai reportlab

      - name: Run Alert Service
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: |
          python main.py
```

### 2. GitHub 저장소 Secrets 등록
배포할 깃허브 레포지토리의 설정 창에 환경 변수 3종을 등록합니다.
1. 대상 저장소의 **Settings** ➡️ **Secrets and variables** ➡️ **Actions**로 이동합니다.
2. **New repository secret** 버튼을 눌러 아래 변수들을 저장합니다.
   * `GEMINI_API_KEY` (AI Studio API 키)
   * `TELEGRAM_BOT_TOKEN` (텔레그램 봇 토큰)
   * `TELEGRAM_CHAT_ID` (내 텔레그램 채팅 ID)

이후 매일 오전 8시 30분에 크론에 의해 스크립트가 실행되어 폰으로 알림이 전송됩니다.
