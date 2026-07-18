# 🏢 내 손안의 맞춤형 임대주택 알리미 (hangbok_is_nearby)

> **"행복주택은 늘 가까이에 있습니다."**  
> 마이홈 포털에서 매일 신규 분양/임대주택 공고를 실시간 수집하고, **Gemini AI**를 활용해 사용자 프로필 기반의 청약 자격 요건을 자동으로 심사하여 텔레그램으로 알려주는 스마트 비서 서비스입니다.

---

## 🌟 핵심 기능

1. **자동화된 맞춤 지역 수집 (1차 필터링)**
   * 프로필 타겟에 맞춘 **서울/경기/인천** 거주 및 생활권 맞춤형 공고 필터링.
   * 공고 게재일과 상관없이 **접수 시작 당일 아침**에 사용자에게 안내하도록 날짜 매칭 설계.

2. **단 1회 호출로 끝내는 벌크 통합 분석 (Bulk Analysis)**
   * 오늘 접수를 시작하는 공고가 여러 건 존재할 때, 개별 공고마다 LLM API를 호출하는 대신 **모든 PDF 파일을 단 한 번의 Gemini API 요청으로 묶어서 전송**합니다.
   * 일일 API 호출 횟수를 획기적으로 줄이고(N번 ➡️ 1번), 요청 한도 초과(429) 문제를 근본적으로 해결하며 분석 속도를 10배 이상 향상시켰습니다.

3. **철저한 자격(Hard) vs 순위(Soft) 분리 심사**
   * 나이, 무주택, 소득, 자산 요건은 **필수 자격 요건(Hard Rules)**으로 엄격히 심사하여 미달 시 제외합니다.
   * 거주지 및 직장 위치 요건은 **우선순위 요건(Soft Rules)**으로 분류하여, 1순위 지역이 아니더라도 수도권 거주자 자격으로 2~3순위 청약 신청이 가능하다면 탈락시키지 않고 적합(`Yes`)으로 판정해 상세 순위 정보를 함께 안내합니다.

4. **초안전 12단계 다중 모델 폴백 (12-Step Fallback)**
   * API 쿼터 한도나 일시적 장애에 대응하여 고성능 Pro 모델부터 Flash/Lite 계열까지 **총 12개의 활성 멀티모달 모델**이 순차적으로 분석을 릴레이 시도합니다.
   * **폴백 후보군 (최신/고성능 우선 순서):**
     1. `gemini-3.1-pro-preview` (최고성능 3.1 Pro)
     2. `gemini-3-pro-preview` (3.0 Pro)
     3. `gemini-2.5-pro` (2.5 Pro)
     4. `gemini-pro-latest` (1.5 Pro)
     5. `gemini-3.5-flash` (최신 3.5 Flash)
     6. `gemini-3.1-flash-lite` (3.1 Lite)
     7. `gemini-3-flash-preview` (3.0 Preview)
     8. `gemini-2.0-flash`
     9. `gemini-2.0-flash-001`
     10. `gemini-2.0-flash-lite`
     11. `gemini-2.0-flash-lite-001`
     12. `gemini-flash-latest` (1.5 Flash)

5. **텔레그램 알림 단일 말풍선 결합 (Single Bubble Delivery)**
   * 분석 텍스트와 탈락 사유 요약 PDF 보고서 파일이 대화방에 쪼개져서 오지 않고, **1개의 말풍선(캡션 형태)으로 묶여 깔끔하게 전송**됩니다.
   * 텔레그램 API 캡션 글자 수 한계(1,024자)를 자동 연산하여 한도 초과 시에만 예외적으로 안전 분할 발송을 처리합니다.

---

## 🛠️ 기술 스택 및 라이브러리

* **Language:** Python 3.9+
* **Libraries:**
  * `BeautifulSoup4` (MyHome HTML 파싱)
  * `google-generativeai` (Gemini LLM 활용 입주 자격 조건 검증)
  * `requests` (AJAX API 호출 및 PDF 다운로드, 텔레그램 API 통신)
  * `reportlab` (한글 폰트가 적용된 자격 부적합 요약 PDF 리포트 빌드)
* **Execution Environment:** GitHub Actions (Cron Scheduler)

---

## 📂 프로젝트 구조

```text
hangbok_is_nearby/
├── .github/
│   └── workflows/
│       └── housing_alert.yml  # GitHub Actions 서버리스 크론 스케줄러 (8:18 AM KST)
├── .env.example               # 환경 변수 템플릿 파일
├── README.md                  # 본 설명서
├── requirements.txt           # 프로젝트 의존성 관리 파일
├── get_chat_id.py             # 텔레그램 봇 채팅 ID 수집 툴
├── main.py                    # 알리미 메인 파이프라인 엔진 (벌크 분석 및 12단 폴백 탑재)
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
pip install -r requirements.txt
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
# 2026년 7월 20일 날짜를 가정하여 실행 (성남 금토지구 및 영구임대 포함 12건 벌크 분석 시뮬레이션)
./run.sh 2026-07-20

# Gemini API 호출 없이 메시지/PDF UI 레이아웃만 테스트하고 싶은 경우
./run.sh 2026-07-20 --mock
```

---

## 🤖 GitHub Actions 서버리스 스케줄러 구축 방법

매일 아침 자동으로 공고를 수집하고 알림을 주기 위해 GitHub Actions의 서버리스 환경을 구성합니다.

### 1. 워크플로우 작동 스케줄 (지연 우회 기법)
GitHub Actions의 크론 스케줄러는 혼잡 시간대(정각, 30분 단위)에 심각한 실행 지연이 발생합니다. 이를 우회하기 위해 **오전 8시 18분 KST(23:18 UTC)**이라는 독자적인 홀수 분 스케줄링을 설정해 두었습니다.

```yaml
on:
  schedule:
    # 매일 아침 한국 시간(KST) 오전 8시 18분에 실행 (UTC 기준 전날 23:18)
    # 정시 혼잡 시간대를 피해 대기 지연 없이 8시 30분 전 도착을 노립니다.
    - cron: '18 23 * * *'
```

### 2. GitHub 저장소 Secrets 등록
배포할 깃허브 레포지토리의 설정 창에 환경 변수 3종을 등록합니다.
1. 대상 저장소의 **Settings** ➡️ **Secrets and variables** ➡️ **Actions**로 이동합니다.
2. **New repository secret** 버튼을 눌러 아래 변수들을 저장합니다.
   * `GEMINI_API_KEY` (AI Studio API 키)
   * `TELEGRAM_BOT_TOKEN` (텔레그램 봇 토큰)
   * `TELEGRAM_CHAT_ID` (내 텔레그램 채팅 ID)

이후 매일 오전 8시 18분~30분 사이에 크론에 의해 스크립트가 실행되어 폰으로 알림이 전송됩니다.
