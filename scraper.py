import os
import json
import requests
from bs4 import BeautifulSoup

def fetch_hkjc_racecard():
    """
    抓取香港賽馬會最新賽事資料（日期、場次、途程、開跑時間與參賽馬匹）
    """
    url = "https://racing.hkjc.com/racing/info/meeting/Racecard/chinese/Local/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        if response.status_code != 200:
            print(f"無法存取馬會網站，HTTP 狀態碼: {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. 擷取比賽基本資訊 (日期、場地)
        race_date = "最新賽事"
        venue = "沙田 / 跑馬地"

        date_elem = soup.select_one('.raceDate, .raceMeeting p, .f_fs13')
        if date_elem:
            race_date = date_elem.text.strip()

        races = []
        
        # 2. 擷取各場次資訊 (可根據馬會頁面結構調校)
        # 抓取參賽馬匹表格 (馬號、馬名、騎師、練馬師、檔位、負磅)
        horse_table = soup.select_one('table.starter')
        horses = []

        if horse_table:
            rows = horse_table.select('tr')[1:] # 跳過表頭
            for row in rows:
                cols = [td.text.strip() for td in row.select('td')]
                if len(cols) >= 6:
                    horses.append({
                        "horse_no": cols[0],     # 馬號
                        "horse_name": cols[2],   # 馬名
                        "jockey": cols[3],       # 騎師
                        "trainer": cols[4],      # 練馬師
                        "draw": cols[5],         # 檔位
                        "weight": cols[6] if len(cols) > 6 else "-" # 負磅
                    })

        # 組裝成 1 號場次示範結構 (可擴展為多場次迴圈)
        races.append({
            "race_no": 1,
            "post_time": "13:00",
            "distance": "1200米",
            "class": "第四班",
            "track": "草地 - C+3 賽道",
            "horses": horses
        })

        race_data = {
            "last_updated": race_date,
            "venue": venue,
            "races": races
        }

        return race_data

    except Exception as e:
        print(f"爬取資料時發生錯誤: {e}")
        return None

def update_data_json():
    data = fetch_hkjc_racecard()
    if data and data.get("races"):
        # 覆蓋專案中的 data.json
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ 成功更新 data.json！")
    else:
        print("⚠️ 抓取失敗或無賽事資料，保持原 data.json 不變。")

if __name__ == "__main__":
    update_data_json()
