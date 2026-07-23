import os
import re
import sys
import json
import tempfile
import datetime
import requests
import html
import time
from bs4 import BeautifulSoup
import google.generativeai as genai
import base64

# ReportLab PDF 생성 모듈 추가
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 한글 폰트 등록 (Mac 기본 애플고딕 또는 Linux 나눔고딕 연동)
def register_korean_font():
    font_candidates = [
        # macOS 기본 폰트
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
        "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf",
        # Linux (Ubuntu) 나눔 폰트 설치 경로
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/nanum/NanumGothic.ttf"
    ]
    
    selected_font = None
    for path in font_candidates:
        if os.path.exists(path):
            selected_font = path
            break
            
    if selected_font:
        try:
            pdfmetrics.registerFont(TTFont("AppleGothic", selected_font))
            print(f"한글 폰트 등록 완료: {selected_font}")
            return True
        except Exception as e:
            print(f"폰트 등록 실패: {e}")
            
    # 폰트를 못 찾거나 등록 실패 시 기본 폰트로 폴백 (Helvetica)
    print("경고: 한글 폰트를 찾지 못했습니다. 기본 영문 폰트(Helvetica)로 대체합니다. (글씨가 깨질 수 있습니다.)")
    try:
        pdfmetrics.registerFont(TTFont("AppleGothic", "Helvetica"))
    except Exception:
        pass
    return False

register_korean_font()

# 1. 환경 변수 확인 및 설정 (.env 파일 직접 파싱하여 공백/따옴표 제거)
def load_env():
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip("'\"")

load_env()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not all([GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    print("오류: 필수 환경 변수가 누락되었습니다.")
    print("설정 필요: GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

# 마이홈 릴레이 서버 설정 (GitHub Actions에서 사용)
MYHOME_RELAY_URL = os.environ.get('MYHOME_RELAY_URL')  # e.g., http://woojoo720.dothome.co.kr/myhome_relay.php
MYHOME_RELAY_KEY = os.environ.get('MYHOME_RELAY_KEY', 'hangbok_relay_2026')

def myhome_request(action, params, timeout=15):
    """마이홈 API 요청 - 릴레이 서버가 설정되어 있으면 릴레이를 통해, 아니면 직접 요청"""
    if not MYHOME_RELAY_URL:
        return None  # 릴레이 미설정 시 None 반환 → 기존 직접 호출 로직 사용
    
    try:
        response = requests.post(MYHOME_RELAY_URL, json={
            'api_key': MYHOME_RELAY_KEY,
            'action': action,
            'params': params
        }, timeout=timeout)
        response.raise_for_status()
        return response
    except Exception as e:
        print(f"릴레이 요청 실패 ({action}): {e}")
        return None

# 사용자 프로필 설정
USER_PROFILE = """
- 나이: 만 33세 (1993년생, 미혼 남성)
- 세대주 여부: 단독세대주 (1인 가구)
- 현 주소지: 경기도 광명시 (주민등록상 거주지)
- 직장 위치: 서울시 용산구 (소득세 납부지 기준)
- 소득 수준: 연 소득 5,000만 원 (월평균 소득 약 4,166,666원)
- 총 자산: 2억 원 미만 (자동차 없음)
"""

# 타겟 지역 정의
TARGET_REGIONS = ["서울", "경기", "인천", "광명", "용산"]

def send_telegram_message(message):
    """텔레그램 봇을 통해 메시지 발송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("텔레그램 알림 발송 성공!")
    except Exception as e:
        print(f"텔레그램 알림 발송 실패: {e}")

def send_telegram_document(pdf_path, caption):
    """텔레그램 봇을 통해 PDF 보고서 파일 전송"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption,
        "parse_mode": "HTML"
    }
    try:
        with open(pdf_path, 'rb') as f:
            files = {"document": f}
            response = requests.post(url, data=payload, files=files, timeout=30)
            response.raise_for_status()
            print("텔레그램 PDF 보고서 발송 성공!")
    except Exception as e:
        print(f"텔레그램 PDF 보고서 발송 실패: {e}")

def generate_ineligible_pdf(ineligible_list, today_str, pdf_path):
    """ReportLab을 사용하여 자격 미달 공고와 그 사유를 명시한 PDF 생성"""
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # 한국어 폰트(AppleGothic)를 사용하는 전용 단락 스타일 선언
    title_style = ParagraphStyle(
        'PDFTitle',
        parent=styles['Heading1'],
        fontName='AppleGothic',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#222222'),
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'PDFSubtitle',
        parent=styles['Normal'],
        fontName='AppleGothic',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#555555'),
        spaceAfter=20
    )
    
    notice_title_style = ParagraphStyle(
        'PDFNoticeTitle',
        parent=styles['Heading2'],
        fontName='AppleGothic',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#C62828'), # 부적합 표시용 짙은 빨간색
        spaceBefore=12,
        spaceAfter=6
    )
    
    body_style = ParagraphStyle(
        'PDFBody',
        parent=styles['Normal'],
        fontName='AppleGothic',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#333333'),
        spaceAfter=4
    )
    
    reason_style = ParagraphStyle(
        'PDFReason',
        parent=styles['Normal'],
        fontName='AppleGothic',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#424242'),
        spaceAfter=12
    )
    
    story = []
    
    # 1. 헤더 영역
    story.append(Paragraph("🏢 [마이홈] 청약 자격 미달 제외 공고 상세 보고서", title_style))
    story.append(Paragraph(f"기준 날짜: {today_str}  |  총 자격 미달 제외 건수: {len(ineligible_list)}건", subtitle_style))
    story.append(Spacer(1, 10))
    
    # 2. 제외 공고 목록 작성
    for idx, item in enumerate(ineligible_list, 1):
        # 공고 제목
        story.append(Paragraph(f"{idx}. {item['title']}", notice_title_style))
        # 상세 필드
        story.append(Paragraph(f"• <b>주택 유형:</b> {item['housing_type']}", body_style))
        story.append(Paragraph(f"• <b>공고 상세 링크:</b> <font color='#1565C0'><u>{item['link']}</u></font>", body_style))
        story.append(Paragraph("• <b>자격 미달 구체적 분석 사유:</b>", body_style))
        
        # 줄바꿈 가공하여 제외 사유 삽입
        reason_text = item['reason'].replace("\n", "<br/>")
        story.append(Paragraph(reason_text, reason_style))
        
        # 구분선 생성 (Table을 얇은 실선으로 활용)
        if idx < len(ineligible_list):
            divider = Table([[""]], colWidths=[530], rowHeights=[0.5])
            divider.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#E0E0E0')),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(divider)
            story.append(Spacer(1, 5))
            
    doc.build(story)

def parse_application_start_dates(pblanc_id):
    """상세 페이지에서 접수 일정 시작일을 다각도로 추출"""
    detail_url = f"https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId={pblanc_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    start_dates = set()
    try:
        # 릴레이 서버를 통한 요청 시도
        relay_resp = myhome_request('detail', {'pblancId': pblanc_id})
        if relay_resp is not None:
            response = relay_resp
        else:
            response = requests.get(detail_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return list(start_dates)
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 날짜 정규식 패턴 (YYYY년 MM월 DD일, YYYY.MM.DD, YYYY-MM-DD 등)
        date_pattern = r'(\d{4})[년\.\-]\s*(\d{1,2})[월\.\-]\s*(\d{1,2})'

        # 1차: 테이블 헤더(th)에 '일정', '접수', '기간', '신청' 키워드가 있는 항목 전수 조사
        schedule_ths = soup.find_all(lambda tag: tag.name == 'th' and any(k in tag.get_text() for k in ['일정', '접수', '기간', '신청']))
        
        for th in schedule_ths:
            th_text = th.get_text().strip()
            # '안내', '당첨자' 관련 문구는 제외
            if any(skip in th_text for skip in ['안내', '당첨자', '발표']):
                continue
                
            td = th.find_next_sibling('td')
            if td:
                text = re.sub(r'\s+', ' ', td.get_text()).strip()
                matches = re.findall(date_pattern, text)
                for y, m, d in matches:
                    start_dates.add(f"{int(y):04d}-{int(m):02d}-{int(d):02d}")
                    
        # 2차: th에서 못 찾은 경우 전체 테이블(table)의 td 셀 중 접수 일정 패턴 탐색 (백업)
        if not start_dates:
            for td in soup.find_all('td'):
                text = re.sub(r'\s+', ' ', td.get_text()).strip()
                if any(k in text for k in ['순위', '접수', '신청']):
                    matches = re.findall(date_pattern, text)
                    for y, m, d in matches:
                        start_dates.add(f"{int(y):04d}-{int(m):02d}-{int(d):02d}")

    except Exception as e:
        print(f"상세 페이지 파싱 오류 (ID: {pblanc_id}): {e}")
        
    return list(start_dates)

def analyze_eligibility_bulk(notices_to_analyze):
    """
    여러 개의 공고문을 한 번의 Gemini API 호출로 묶어서 벌크 분석 진행 (API 요청 횟수 최소화)
    notices_to_analyze: [(pblanc_nm, pdf_bytes, pblanc_id, suply_ty_nm), ...]
    """
    if not notices_to_analyze:
        return []
        
    all_bulk_results = []
    chunk_size = 5 # 토큰 초과(1M) 방지를 위해 5개 단위로 묶어서 처리
    
    chunks = [notices_to_analyze[i:i + chunk_size] for i in range(0, len(notices_to_analyze), chunk_size)]
    
    for chunk_idx, chunk in enumerate(chunks):
        try:
            # 1. 콘텐츠 리스트 구성 (PDF 바이트들을 인라인 데이터로 순서대로 추가)
            contents = []
            for pblanc_nm, pdf_bytes, pblanc_id, _ in chunk:
                contents.append({
                    'mime_type': 'application/pdf',
                    'data': pdf_bytes
                })
                
            # 각 PDF 인덱스를 식별하기 위한 매핑 목록 문자열 생성
            notices_index_str = "\n".join([
                f"[{idx+1}] {item[0]} (ID: {item[2]})"
                for idx, item in enumerate(chunk)
            ])
            
            # 2. 벌크 전송용 단일 통합 프롬프트 작성
            prompt = f"""
            당신은 대한민국 공공임대주택 자격 요건 분석 전문가입니다.
            제공된 {len(chunk)}개의 청약 모집공고문 PDF 파일들(순서대로 전달됨)과 아래의 '신청자 정보'를 면밀히 비교하여 각 공고별 신청 가능 여부를 평가해 주세요.

            [신청자 정보]
            {USER_PROFILE}

            [분석 대상 공고 목록 (순서 매칭)]
            {notices_index_str}

            [요구 조건 및 심사 지침 (중요)]
            1. **자격 요건 (Hard Rules - 필수 자격)**
               - 나이(만 33세), 무주택 여부, 미혼 요건, 자산 기준, 소득 한도 기준은 신청 가능 여부를 결정하는 필수 자격 요건(Hard Rules)입니다.
               - 이 필수 자격 조건 중 하나라도 탈락(예: 1인 가구 소득 한도를 명백히 초과하거나 나이 제한을 넘어섬)하는 경우에만 `"eligible": "No"`로 판정하십시오.
            
            2. **순위 요건 (Soft Rules - 거주지/직장 위치에 따른 우선순위)**
               - 해당 주택이 건설되는 시/군에 거주하지 않더라도(예: 성남시 공고인데 신청자는 광명시 거주/용산구 직장인인 경우), 대한민국 수도권 거주자 자격으로 **2순위 또는 3순위 등으로 신청이 가능하다면 절대 `"eligible": "No"`로 판정하지 마십시오.**
               - 1순위 조건에 부합하지 않더라도 2순위, 3순위로 청약 접수 자체가 가능한 경우 `"eligible": "Yes"`로 판정하고, 설명란(reason)에 "1순위 지역 요건은 미달하나, 수도권 거주자 자격으로 3순위 신청이 가능합니다."라고 상세히 명시해 주십시오.
               - 거주지나 직장 위치가 공고의 우선순위 지역과 맞지 않다는 이유만으로 신청이 불가능한 것으로 분류하지 않도록 각별히 유의하십시오.

            [출력 형식]
            반드시 다음 구조의 JSON 리스트 형식으로만 답변을 제공해 주세요. 다른 설명이나 텍스트는 포함하지 마십시오.
            [
              {{
                "title": "공고명",
                "eligible": "Yes" 또는 "No" 또는 "Unsure",
                "housing_type": "행복주택/국민임대/청년안심주택 등 파악된 주택 유형",
                "reason": "신청 가능 여부에 대한 구체적인 분석 사유 (한국어로 서술. 필수 자격 요건 대조 결과 및 순위/우선순위 대조 결과 포함)"
              }},
              ...
            ]
            """
            contents.append(prompt)
            
            # 사용 가능한 폴백 모델 목록 순서대로 정의
            candidate_models = [
                # 1. 최상위 추론 성능 Pro 계열 (최신 순서)
                'gemini-3.1-pro-preview',
                'gemini-3-pro-preview',
                'gemini-2.5-pro',
                'gemini-pro-latest',
                
                # 2. 보급형 Flash & Lite 계열 (최신 순서)
                'gemini-3.5-flash',
                'gemini-3.1-flash-lite',
                'gemini-3-flash-preview',
                'gemini-2.0-flash',
                'gemini-2.0-flash-001',
                'gemini-2.0-flash-lite',
                'gemini-2.0-flash-lite-001',
                'gemini-flash-latest'
            ]
            
            last_exception = None
            chunk_success = False
            
            for model_name in candidate_models:
                try:
                    print(f"\n[Chunk {chunk_idx+1}/{len(chunks)}] {len(chunk)}건의 공고에 대해 {model_name} 모델로 통합 분석 시도 중...")
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(
                        contents,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    
                    # 3. 결과 파싱 (마크다운 코드 블록 펜스가 포함되어 있을 경우 정제)
                    raw_text = response.text.strip()
                    if raw_text.startswith("```"):
                        first_newline = raw_text.find("\n")
                        if first_newline != -1:
                            raw_text = raw_text[first_newline:].strip()
                        if raw_text.endswith("```"):
                            raw_text = raw_text[:-3].strip()
                            
                    result = json.loads(raw_text)
                    print(f"[{model_name}] 모델 Chunk {chunk_idx+1} 벌크 분석 성공!")
                    all_bulk_results.extend(result)
                    chunk_success = True
                    break
                    
                except Exception as e:
                    err_str = str(e)
                    print(f"{model_name} 분석 오류: {err_str[:120]}")
                    last_exception = e
                    # 429 등의 에러 발생 시 다음 후보 모델로 폴백
                    continue
                    
            if not chunk_success:
                print(f"❌ Chunk {chunk_idx+1} 분석 실패. (최종 에러: {last_exception})")
                for pblanc_nm, _, pblanc_id, suply_ty_nm in chunk:
                    all_bulk_results.append({
                        "title": pblanc_nm,
                        "eligible": "Unsure",
                        "housing_type": suply_ty_nm,
                        "reason": f"통합 분석 중 쿼터 초과 또는 API 오류 발생으로 수동 확인이 필요합니다. (최종 에러 내용: {last_exception})"
                    })
                    
        except Exception as e:
            print(f"Gemini 벌크 분석 Chunk {chunk_idx+1} 최종 실패: {e}")
            for pblanc_nm, _, pblanc_id, suply_ty_nm in chunk:
                all_bulk_results.append({
                    "title": pblanc_nm,
                    "eligible": "Unsure",
                    "housing_type": suply_ty_nm,
                    "reason": f"통합 분석 중 예기치 못한 오류 발생. (최종 에러 내용: {e})"
                })
                
    return all_bulk_results

def fetch_recent_notices(target_date):
    """최근 신규 공고 목록 조회 (공고일이 target_date 기준 25일 이내인 것들만 동적 수집)"""
    list_url = "https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcList.do"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcView.do",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    # 25일 이전 공고일(모집공고일)을 컷오프 기준으로 설정
    cutoff_date = target_date - datetime.timedelta(days=25)
    
    all_notices = []
    page = 1
    max_pages = 80 # 무한 루프 방지용 안전 상한선
    
    while page <= max_pages:
        data = {
            "pageIndex": str(page),
            "searchTyId": "",
            "srchSuplyTy": "",
            "srchHouseTy": "",
            "srchSuplyPrvuseAr": "",
            "srchBassMtRntchrg": "",
            "srchPrgrStts": "1", # 모집중
            "lfstsTyAt": "",
            "srchPblancNm": "",
            "srchRcritPblancDeYearMtBegin": "",
            "srchRcritPblancDeYearMtEnd": "",
        }
        
        try:
            print(f"공고 목록 가져오는 중... (페이지 {page})")
            # 릴레이 서버를 통한 요청 시도
            relay_resp = myhome_request('list', data)
            if relay_resp is not None:
                response = relay_resp
            else:
                response = requests.post(list_url, headers=headers, data=data, timeout=10)
            if response.status_code == 200:
                json_data = response.json()
                items = json_data.get('resultList', [])
                if not items:
                    break
                all_notices.extend(items)
                
                # 마지막 아이템 공고일 분석 후 컷오프일보다 과거이면 중단
                last_item_date_str = items[-1].get('rcritPblancDe')
                try:
                    last_item_date = datetime.datetime.strptime(last_item_date_str, "%Y%m%d").date()
                    if last_item_date < cutoff_date:
                        print(f"공고 수집 중단: 페이지 {page}의 마지막 공고일({last_item_date})이 컷오프일({cutoff_date})보다 오래되었습니다.")
                        break
                except Exception as e:
                    print(f"날짜 분석 파싱 에러: {e}")
            else:
                print(f"페이지 {page} 가져오기 실패: {response.status_code}")
                break
        except Exception as e:
            print(f"목록 요청 예외 발생: {e}")
            break
            
        page += 1
            
    return all_notices

def main():
    # 한국 시간(KST, UTC+9) 기준으로 오늘 날짜 정의
    kst = datetime.timezone(datetime.timedelta(hours=9))
    today_dt = datetime.datetime.now(kst)
    today_str = today_dt.strftime("%Y-%m-%d")
    
    # --mock 파라미터가 포함되었는지 확인 및 제거
    mock_mode = False
    if "--mock" in sys.argv:
        mock_mode = True
        sys.argv.remove("--mock")
        print("💡 [Mock 모드] Gemini API 호출을 우회하고 모의 분석 데이터를 사용합니다.")
    
    # 커맨드라인 인자로 날짜를 입력받은 경우 테스트 모드로 실행
    if len(sys.argv) > 1:
        if re.match(r'^\d{4}-\d{2}-\d{2}$', sys.argv[1]):
            today_str = sys.argv[1]
            print(f"🚨 [테스트 모드] 기준 날짜가 재설정되었습니다: {today_str}")
        else:
            print("오류: 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.")
            sys.exit(1)
    else:
        print(f"기준 날짜 (KST): {today_str}")
        
    # 날짜 문자열을 date 객체로 변환 (컷오프 계산용)
    target_date = datetime.datetime.strptime(today_str, "%Y-%m-%d").date()
    
    # 1. 최근 공고 조회 (target_date 전달)
    notices = fetch_recent_notices(target_date)
    print(f"총 {len(notices)}개의 공고 확보.")
    
    eligible_list = []
    ineligible_list = []
    checked_count = 0
    
    # 중복 분석 방지용 ID 셋
    processed_ids = set()
    
    # 벌크 분석을 위해 오늘 대기 중인 PDF 데이터를 저장할 목록
    notices_to_analyze = []
    
    for notice in notices:
        pblanc_id = str(notice.get("pblancId"))
        pblanc_nm = notice.get("pblancNm", "")
        
        if pblanc_id in processed_ids:
            continue
        processed_ids.add(pblanc_id)
        
        # 2. 1차 필터링: 서울/경기권 공고인지 확인
        region_matched = False
        
        # 체크할 지역 필드 목록
        region_fields = [
            notice.get("brtcCodeNm"),
            notice.get("lfstsAreaBrtcCodeNm"),
            notice.get("mhshldBrtcCodeNm"),
            pblanc_nm
        ]
        
        for field in region_fields:
            if field and any(r in field for r in TARGET_REGIONS):
                region_matched = True
                break
                
        if not region_matched:
            continue
            
        # 3. 접수 시작일이 오늘인지 확인
        start_dates = parse_application_start_dates(pblanc_id)
        is_starting_today = today_str in start_dates
        
        if not is_starting_today:
            continue
            
        # 오늘 신청 시작하는 서울/경기권 공고 발견!
        checked_count += 1
        print(f"\n★ 오늘 접수 시작 공고 발견: {pblanc_nm} (ID: {pblanc_id})")
        
        # 공고문 정보 파악
        suply_ty_nm = notice.get("suplyTyNm", "임대주택")
        atch_file_id = notice.get("atchFileId")
        
        if not atch_file_id:
            # 첨부파일이 없으면 수동 확인을 위한 대기 리스트에 Unsure 상태로 추가
            eligible_list.append({
                "title": pblanc_nm,
                "housing_type": suply_ty_nm,
                "link": f"https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId={pblanc_id}",
                "eligible": "Unsure",
                "reason": "공고문 PDF 파일 ID가 존재하지 않아 수동 확인이 필요합니다."
            })
            continue
            
        # PDF 다운로드 진행
        pdf_url = f"https://www.myhome.go.kr/hws/com/fms/cvplFileDownload.do?atchFileId={atch_file_id}&fileSn=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        try:
            print(f"[{pblanc_nm}] PDF 공고문 다운로드 중...")
            # 릴레이 서버를 통한 PDF 다운로드 시도
            relay_resp = myhome_request('pdf', {'atchFileId': atch_file_id}, timeout=60)
            if relay_resp is not None:
                relay_data = relay_resp.json()
                if relay_data.get('status') == 'ok':
                    pdf_bytes = base64.b64decode(relay_data['data'])
                    # Create a mock response-like behavior
                    class RelayResponse:
                        status_code = 200
                        content = pdf_bytes
                    response = RelayResponse()
                else:
                    raise Exception(f"릴레이 PDF 다운로드 실패: {relay_data.get('error')}")
            else:
                response = requests.get(pdf_url, headers=headers, timeout=30)
            if response.status_code != 200 or not response.content.startswith(b"%PDF"):
                eligible_list.append({
                    "title": pblanc_nm,
                    "housing_type": suply_ty_nm,
                    "link": f"https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId={pblanc_id}",
                    "eligible": "Unsure",
                    "reason": "공고문 PDF 다운로드에 실패했거나 올바른 PDF 형식이 아닙니다."
                })
            else:
                # 다운로드 성공 시 분석 대기 대열에 추가
                notices_to_analyze.append((pblanc_nm, response.content, pblanc_id, suply_ty_nm))
        except Exception as e:
            eligible_list.append({
                "title": pblanc_nm,
                "housing_type": suply_ty_nm,
                "link": f"https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId={pblanc_id}",
                "eligible": "Unsure",
                "reason": f"PDF 다운로드 오류 발생: {e}"
            })

    # 4. 벌크 분석 진행 (모아놓은 공고문이 있다면 단 1번 호출하여 분석)
    if notices_to_analyze:
        bulk_results = []
        if mock_mode:
            print(f"\n💡 [Mock 모드] {len(notices_to_analyze)}건의 공고 모의 분석 데이터 생성 중...")
            for idx, item in enumerate(notices_to_analyze):
                pblanc_nm, _, pblanc_id, suply_ty_nm = item
                if "성남" in pblanc_nm:
                    bulk_results.append({
                        "title": pblanc_nm,
                        "eligible": "No",
                        "housing_type": "국민임대/영구임대",
                        "reason": "신청인의 연 소득(5,000만 원, 월평균 약 416만 원)이 국민임대주택 1인 가구 소득 기준(월평균 소득 70% 이하: 약 280만 원) 또는 영구임대/고령자복지주택 대상 자격을 초과하여 제외되었습니다."
                    })
                elif "관악봉천" in pblanc_nm:
                    bulk_results.append({
                        "title": pblanc_nm,
                        "eligible": "Yes",
                        "housing_type": "행복주택",
                        "reason": "신청인의 조건(나이 만 33세 청년, 미혼, 서울/경기 생활권, 1인 가구 소득 기준 약 457만 원 이하)이 본 공고의 청년 행복주택 지원 요건에 완벽하게 부합합니다."
                    })
                else:
                    bulk_results.append({
                        "title": pblanc_nm,
                        "eligible": "No",
                        "housing_type": suply_ty_nm,
                        "reason": "공고의 신청 자격 요건(나이, 거주지역, 소득 조건 등) 중 일부가 신청인의 프로필 요건을 충족하지 못해 부적합합니다."
                    })
            time.sleep(0.5)
        else:
            bulk_results = analyze_eligibility_bulk(notices_to_analyze)
            
        # 벌크 결과 매핑 및 목록 분류
        for idx, notice_item in enumerate(notices_to_analyze):
            pblanc_nm, _, pblanc_id, suply_ty_nm = notice_item
            
            # 기본 폴백값 정의
            item_result = {
                "title": pblanc_nm,
                "housing_type": suply_ty_nm,
                "link": f"https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId={pblanc_id}",
                "eligible": "Unsure",
                "reason": "벌크 분석 결과 매칭 오류"
            }
            
            # 매칭 결과 탐색 (인덱스 우선 매칭 후 제목 매칭 지원)
            matched_data = None
            if idx < len(bulk_results):
                matched_data = bulk_results[idx]
            else:
                for res in bulk_results:
                     if res.get("title") and pblanc_nm in res.get("title"):
                         matched_data = res
                         break
                         
            if matched_data:
                item_result["eligible"] = matched_data.get("eligible", "Unsure")
                item_result["reason"] = matched_data.get("reason", "분석 사유 누락")
                item_result["housing_type"] = matched_data.get("housing_type", suply_ty_nm)
                
            if item_result["eligible"] in ["Yes", "Unsure"]:
                eligible_list.append(item_result)
            else:
                ineligible_list.append(item_result)
                
    # 5. 최종 알림 구성 및 발송
    pdf_report_path = None
    
    # 5-1. 부적합 공고가 있을 경우 PDF 파일 미리 생성
    if ineligible_list:
        pdf_report_path = os.path.join(tempfile.gettempdir(), f"ineligible_report_{today_str}.pdf")
        try:
            generate_ineligible_pdf(ineligible_list, today_str, pdf_report_path)
            print("PDF 보고서 생성 완료:", pdf_report_path)
        except Exception as e:
            print("PDF 보고서 생성 실패:", e)
            pdf_report_path = None
            
    if eligible_list:
        message_parts = [f"🔔 <b>[마이홈] 오늘 접수 시작! 맞춤형 임대주택 공고 알림</b>\n\n오늘({today_str}) 자격 충족 가능성이 있는 공고가 접수를 시작합니다.\n"]
        for idx, item in enumerate(eligible_list, 1):
            status_tag = "✅ 신청 가능" if item["eligible"] == "Yes" else "⚠️ 검증 모호 (확인 요망)"
            escaped_title = html.escape(item['title'])
            escaped_housing_type = html.escape(item['housing_type'])
            escaped_reason = html.escape(item['reason'])
            escaped_link = html.escape(item['link'])
            message_parts.append(
                f"{idx}. <b>{escaped_title}</b>\n"
                f"- 유형: {escaped_housing_type}\n"
                f"- 상태: {status_tag}\n"
                f"- LLM 판단 사유:\n{escaped_reason}\n"
                f"- 👉 <a href=\"{escaped_link}\">상세 공고 보러가기</a>\n"
            )
        
        if ineligible_list:
            message_parts.append(
                f"\n" + "-"*30 + f"\n❌ <b>자격 미달 제외 공고</b>: 총 {len(ineligible_list)}건\n"
                f"※ 상세 제외 사유는 첨부된 PDF 보고서 파일을 확인해 주세요."
            )
            
        telegram_message = "\n".join(message_parts)
        
        # 텔레그램 메시지와 PDF 문서 전송 통합 처리
        if pdf_report_path:
            # 캡션 글자수 제한(1024자) 이내인 경우 통합 전송
            if len(telegram_message) <= 1024:
                send_telegram_document(pdf_report_path, telegram_message)
            else:
                # 글자수 초과 시 분할 전송 (안전 대비책)
                send_telegram_message(telegram_message)
                send_telegram_document(pdf_report_path, f"❌ {today_str} 자격 미달 제외 공고 상세 사유 보고서")
        else:
            send_telegram_message(telegram_message)
            
    else:
        if ineligible_list:
            telegram_message = (
                f"ℹ️ <b>[마이홈] 오늘 접수 시작 공고 알림</b>\n\n"
                f"오늘({today_str}) 서울/경기권에서 접수를 시작한 공고가 {checked_count}건 존재하나, "
                f"분석 결과 신청자의 요건(나이, 미혼, 소득 등)에 부합하는 공고는 없었습니다.\n\n"
                f"❌ <b>자격 미달 제외 공고</b>: 총 {len(ineligible_list)}건\n"
                f"※ 상세 제외 사유는 첨부된 PDF 보고서 파일을 확인해 주세요."
            )
            
            if pdf_report_path and len(telegram_message) <= 1024:
                send_telegram_document(pdf_report_path, telegram_message)
            else:
                send_telegram_message(telegram_message)
                if pdf_report_path:
                    send_telegram_document(pdf_report_path, f"❌ {today_str} 자격 미달 제외 공고 상세 사유 보고서")
        else:
            send_telegram_message(f"ℹ️ 오늘({today_str}) 신청 가능한 임대주택 공고는 없습니다.")
            
    # 사용 완료한 임시 PDF 파일 삭제
    if pdf_report_path and os.path.exists(pdf_report_path):
        try:
            os.remove(pdf_report_path)
            print("임시 PDF 보고서 파일 삭제 완료.")
        except Exception as e:
            print("임시 PDF 보고서 파일 삭제 실패:", e)

if __name__ == "__main__":
    main()
