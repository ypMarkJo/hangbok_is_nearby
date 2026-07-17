import sys
import requests

def main():
    print("=== 텔레그램 Chat ID 확인 도우미 ===")
    token = input("1. 발급받으신 텔레그램 봇 토큰(HTTP API Token)을 입력해주세요:\n> ").strip()
    
    if not token:
        print("토큰이 입력되지 않았습니다. 종료합니다.")
        return
        
    print("\n2. 이제 폰의 텔레그램 앱에서 생성하신 봇을 찾아 들어가 '시작' 또는 아무 메시지나 보내주세요.")
    input("봇에게 메시지를 보내셨다면 엔터(Enter) 키를 눌러주세요...\n")
    
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("result", [])
        if not results:
            print("\n⚠️ 아직 봇이 받은 메시지가 없습니다.")
            print("대화방에 들어가서 꼭 '시작(Start)' 버튼을 누르거나 대화를 보내셨는지 확인 후 다시 실행해 주세요.")
            return
            
        # 가장 최근 메시지 정보 추출
        latest_update = results[-1]
        message = latest_update.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        username = chat.get("username", "이름없음")
        first_name = chat.get("first_name", "")
        
        if chat_id:
            print("\n" + "="*40)
            print(f"🎉 Chat ID 확인 완료!")
            print(f"- 사용자: {first_name} (@{username})")
            print(f"- Chat ID: {chat_id}")
            print("="*40)
            print("\n이 값을 '.env' 파일의 'TELEGRAM_CHAT_ID=' 뒤에 넣어주시면 됩니다.")
        else:
            print("\n오류: 메시지는 발견되었으나 Chat ID를 파싱하지 못했습니다.")
            print("응답 데이터:", data)
            
    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
        print("토큰이 올바른지 확인하시고, 인터넷 연결 상태를 확인해 주세요.")

if __name__ == "__main__":
    main()
