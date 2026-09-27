import json
import requests
from bs4 import BeautifulSoup
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

BASE_URL = "https://racing.hkjc.com/racing/info/meeting/Racecard/chinese/Local/"

def get_soup(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            return BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"請求失敗 ({url}): {e}")
    return None

def fetch_all_races():
    soup = get_soup(BASE_URL)
    if not soup:
        print("無法取得馬會排位表主頁")
        return None

    # 1. 解析賽日整體資訊 (日期、場地、地質屬性)
    race_date = "最新賽日"
    venue = "沙田/跑馬地"
    track_condition = "好地" # 預設地質

    date_venue_elem = soup.select_one('.raceDate, .raceMeeting, .f_fs13')
    if date_venue_elem:
        info_text = date_venue_elem.text.strip()
        race_date_match = re.search(r'\d{4}年\d{1,2}月\d{1,2}日', info_text)
        if race_date_match:
            race_date = race_date_match.group(0)

    # 偵測賽地 (沙田 / 跑馬地)
    page_text = soup.get_text()
    if "跑馬地" in page_text:
        venue = "跑馬地"
    elif "沙田" in page_text:
        venue = "沙田"

    # 偵測地質屬性 (快地、好地、黏地、濕慢地等)
    conditions = ["快地", "好地", "黏地", "軟地", "重地", "濕快地", "濕慢地"]
    for c in conditions:
        if c in page_text:
            track_condition = c
            break

    # 2. 自動偵測當日總場數 (8~11場)
    race_links = soup.select('table.num img, .raceNum a, img[src*="race_"]')
    race_count = 10 # 預設 10 場
    
    # 從頁面中的場次按鈕判斷總場次
    numbers = []
    for a in soup.find_all('a', href=True):
        if 'RaceNo=' in a['href']:
            match = re.search(r'RaceNo=(\d+)', a['href'])
            if match:
                numbers.append(int(match.group(1)))
    if numbers:
        race_count = max(numbers)

    print(f"偵測到賽事日期: {race_date} | 場地: {venue} | 地質: {track_condition} | 總場數: {race_count}場")

    all_races = []

    # 3. 逐場爬取資料 (1 ~ race_count)
    for r_no in range(1, race_count + 1):
        race_url = f"{BASE_URL}?RaceNo={r_no}"
        r_soup = get_soup(race_url) if r_no > 1 else soup

        if not r_soup:
            continue

        # 解析場次詳細資訊：開跑時間、班次、途程、跑道
        post_time = "--:--"
        race_class = "未知班次"
        distance = "未知途程"
        course = "草地"

        # 解析賽程頂部資訊區塊
        header_text = ""
        race_card_hdr = r_soup.select_one('.race_tab, .f_fs13, .race_header')
        if race_card_hdr:
            header_text = race_card_hdr.get_text()

        time_match = re.search(r'(\d{1,2}:\d{2})', header_text)
        if time_match:
            post_time = time_match.group(1)

        class_match = re.search(r'(第[一二三四五]班|Group \d|G\d|條件賽)', header_text)
        if class_match:
            race_class = class_match.group(1)

        dist_match = re.search(r'(\d{3,4})米', header_text)
        if dist_match:
            distance = f"{dist_match.group(1)}米"

        course_match = re.search(r'("(.*?)"|草地|全天候跑道|藍塘道|向禮頓道)', header_text)
        if course_match:
            course = course_match.group(0)

        # 解析參賽馬匹表格 (精準匹配欄位)
        horses = []
        table = r_soup.select_one('table.starter, table.table_bd')
        if table:
            rows = table.select('tr')
            for row in rows:
                cols = row.select('td')
                if len(cols) >= 7:
                    h_no = cols[0].text.strip()
                    # 判斷是否為有效馬號
                    if h_no.isdigit():
                        h_name = cols[2].text.strip().split('(')[0] # 去除括號註記
                        jockey = cols[3].text.strip()
                        trainer = cols[4].text.strip()
                        draw = cols[5].text.strip()
                        weight = cols[6].text.strip()

                        # 修正馬匹狀態與異動
                        horses.append({
                            "number": int(h_no),
                            "name": h_name,
                            "jockey": jockey,
                            "trainer": trainer,
                            "draw": draw,
                            "weight": weight,
                            "score": 75, # 預設基準分數，後續可自動結合演算法
                            "odds_t3": 10.0,
                            "status": "出賽"
                        })

        all_races.append({
            "race_number": r_no,
            "post_time": post_time,
            "class": race_class,
            "distance": distance,
            "course": course,
            "horses": horses
        })

    full_data = {
        "race_date": race_date,
        "venue": venue,
        "track_condition": track_condition,
        "total_races": len(all_races),
        "races": all_races
    }

    return full_data

def update_json():
    data = fetch_all_races()
    if data and data.get("races"):
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ 成功更新全賽日數據至 data.json")
    else:
        print("❌ 爬取失敗")

if __name__ == "__main__":
    update_json()
