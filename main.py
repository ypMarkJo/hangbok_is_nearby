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
    """상세 페이지에서 접수 일정 시작일을 추출"""
    detail_url = f"https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId={pblanc_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    start_dates = []
    try:
        response = requests.get(detail_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return start_dates
            
        soup = BeautifulSoup(response.text, 'html.parser')
        th = soup.find(lambda tag: tag.name == 'th' and '접수 일정' in tag.get_text())
        if th:
            td = th.find_next_sibling('td')
            if td:
                # 공백 및 줄바꿈 정규화
                text = re.sub(r'\s+', ' ', td.get_text()).strip()
                
                # 'YYYY년 MM월 DD일 ~ YYYY년 MM월 DD일' 패턴 검색
                pattern = r'(\d{4}년\s*\d{2}월\s*\d{2}일)\s*~\s*(\d{4}년\s*\d{2}월\s*\d{2}일)'
                ranges = re.findall(pattern, text)
                
                if ranges:
                    for r in ranges:
                        start_str = r[0]
                        m = re.search(r'(\d{4})년\s*(\d{2})월\s*(\d{2})일', start_str)
                        if m:
                            start_dates.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
                else:
                    # 단일 날짜 포맷이 있는 경우 검색
                    m = re.search(r'(\d{4})년\s*(\d{2})월\s*(\d{2})일', text)
                    if m:
                        start_dates.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
    except Exception as e:
        print(f"상세 페이지 파싱 오류 (ID: {pblanc_id}): {e}")
        
    return start_dates

def analyze_eligibility(pblanc_id, atch_file_id, pblanc_nm):
    """Gemini를 이용해 공고문 PDF 분석 및 자격 심사 진행 (429 한도 초과 시 모델 자동 폴백 지원)"""
    if not atch_file_id:
        return {"eligible": "Unsure", "reason": "공고문 PDF 파일 ID가 존재하지 않아 수동 확인이 필요합니다."}
        
    pdf_url = f"https://www.myhome.go.kr/hws/com/fms/cvplFileDownload.do?atchFileId={atch_file_id}&fileSn=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # 1. PDF 다운로드
        print(f"[{pblanc_nm}] PDF 공고문 다운로드 중...")
        response = requests.get(pdf_url, headers=headers, timeout=30)
        if response.status_code != 200 or not response.content.startswith(b"%PDF"):
            return {"eligible": "Unsure", "reason": "공고문 PDF 다운로드에 실패했거나 올바른 PDF 형식이 아닙니다."}
            
        pdf_bytes = response.content
        
        # 2. 모델 프롬프트 설정
        prompt = f"""
        당신은 대한민국 공공임대주택 자격 요건 분석 전문가입니다.
        제공된 청약 모집공고문 PDF 파일과 아래의 '신청자 정보'를 면밀히 비교하여 신청 가능 여부를 평가해 주세요.

        [신청자 정보]
        {USER_PROFILE}

        [요구 조건 및 출력 형식]
        반드시 다음 JSON 형식으로 답변을 제공해 주세요. 다른 텍스트는 포함하지 마십시오.
        {{
            "eligible": "Yes" 또는 "No" 또는 "Unsure",
            "housing_type": "행복주택/국민임대/청년안심주택 등 파악된 주택 유형",
            "reason": "신청 가능 여부에 대한 구체적인 근거 설명 (나이, 미혼 여부, 거주지/직장, 소득 기준을 각각 대조한 결과 포함)"
        }}
        """
        
        # 사용 가능한 폴백 모델 목록 순서대로 정의
        candidate_models = [
            'gemini-2.0-flash',
            'gemini-flash-latest',
            'gemini-3.5-flash',
            'gemini-2.5-flash'
        ]
        
        last_exception = None
        
        for model_name in candidate_models:
            try:
                print(f"[{pblanc_nm}] {model_name} 모델로 분석 시도 중...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    [
                        {
                            'mime_type': 'application/pdf',
                            'data': pdf_bytes
                        },
                        prompt
                    ],
                    generation_config={"response_mime_type": "application/json"}
                )
                
                # 3. 결과 파싱 (마크다운 코드 블록 펜스가 포함되어 있을 경우 정제)
                raw_text = response.text.strip()
                if raw_text.startswith("```"):
                    # 첫 번째 줄 바꿈 찾기
                    first_newline = raw_text.find("\n")
                    if first_newline != -1:
                        raw_text = raw_text[first_newline:].strip()
                    if raw_text.endswith("```"):
                        raw_text = raw_text[:-3].strip()
                        
                result = json.loads(raw_text)
                print(f"[{pblanc_nm}] {model_name} 모델 분석 성공!")
                return result
                
            except Exception as e:
                err_str = str(e)
                print(f"[{pblanc_nm}] {model_name} 분석 오류: {err_str[:120]}")
                last_exception = e
                # 429 한도 초과 또는 404 모델 미지원 등의 에러 발생 시 다음 모델로 폴백
                continue
                
        # 모든 모델 시도가 실패한 경우 예외 발생
        raise last_exception if last_exception else Exception("모든 후보 모델의 호출에 실패했습니다.")
        
    except Exception as e:
        print(f"Gemini 최종 분석 실패: {e}")
        return {"eligible": "Unsure", "reason": f"모든 분석 모델의 한도 초과 또는 에러로 분석 실패. (최종 에러 내용: {e})"}

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
        
        # 4. LLM 2차 필터링 (자격 심사)
        if mock_mode:
            # 테스트를 위해 Gemini 호출을 우회하고 시나리오에 맞는 모의 응답 생성
            housing_type = notice.get("suplyTyNm", "임대주택")
            if "성남" in pblanc_nm:
                eligible_status = "No"
                reason = "신청인의 연 소득(5,000만 원, 월평균 약 416만 원)이 국민임대주택 1인 가구 소득 기준(월평균 소득 70% 이하: 약 280만 원) 또는 영구임대/고령자복지주택 대상 자격을 초과하여 제외되었습니다."
                housing_type = "국민임대/영구임대"
            elif "관악봉천" in pblanc_nm:
                eligible_status = "Yes"
                reason = "신청인의 조건(나이 만 33세 청년, 미혼, 서울/경기 생활권, 1인 가구 소득 기준 약 457만 원 이하)이 본 공고의 청년 행복주택 지원 요건에 완벽하게 부합합니다."
                housing_type = "행복주택"
            else:
                eligible_status = "No"
                reason = "공고의 신청 자격 요건(나이, 거주지역, 소득 조건 등) 중 일부가 신청인의 프로필 요건을 충족하지 못해 부적합합니다."
            
            # 딜레이 시뮬레이션
            time.sleep(0.5)
        else:
            atch_file_id = notice.get("atchFileId")
            analysis = analyze_eligibility(pblanc_id, atch_file_id, pblanc_nm)
            
            # API 레이트 리밋(RPM/TPM) 방지를 위한 대기 시간 추가
            time.sleep(3)
            
            eligible_status = analysis.get("eligible", "Unsure")
            reason = analysis.get("reason", "분석 실패")
            housing_type = analysis.get("housing_type", notice.get("suplyTyNm", "임대주택"))
        
        detail_link = f"https://www.myhome.go.kr/hws/portal/sch/selectRsdtRcritNtcDetailView.do?pblancId={pblanc_id}"
        
        notice_info = {
            "title": pblanc_nm,
            "housing_type": housing_type,
            "link": detail_link,
            "eligible": eligible_status,
            "reason": reason
        }
        
        if eligible_status in ["Yes", "Unsure"]:
            eligible_list.append(notice_info)
        else:
            ineligible_list.append(notice_info)
            
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
