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

    # 1. 解析賽日整體資訊
    race_date = "最新賽日"
    venue = "沙田/跑馬地"
    track_condition = "好地"

    date_venue_elem = soup.select_one('.raceDate, .raceMeeting, .f_fs13')
    if date_venue_elem:
        info_text = date_venue_elem.text.strip()
        race_date_match = re.search(r'\d{4}年\d{1,2}月\d{1,2}日', info_text)
        if race_date_match:
            race_date = race_date_match.group(0)

    page_text = soup.get_text()
    if "跑馬地" in page_text:
        venue = "跑馬地"
    elif "沙田" in page_text:
        venue = "沙田"

    conditions = ["快地", "好地", "黏地", "軟地", "重地", "濕快地", "濕慢地"]
    for c in conditions:
        if c in page_text:
            track_condition = c
            break

    # 2. 自動偵測當日總場數
    numbers = []
    for a in soup.find_all('a', href=True):
        if 'RaceNo=' in a['href']:
            match = re.search(r'RaceNo=(\d+)', a['href'])
            if match:
                numbers.append(int(match.group(1)))
    race_count = max(numbers) if numbers else 10

    all_races = []

    # 3. 逐場爬取資料 (完全對齊馬會官方欄位)
    for r_no in range(1, race_count + 1):
        race_url = f"{BASE_URL}?RaceNo={r_no}"
        r_soup = get_soup(race_url) if r_no > 1 else soup

        if not r_soup:
            continue

        post_time = "--:--"
        race_class = "未知班次"
        distance = "未知途程"
        course = "草地"

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

        # 解析官方表格 (馬號、烙號、馬名、負磅、騎師、檔位、練馬師、評分)
        horses = []
        table = r_soup.select_one('table.starter, table.table_bd')
        if table:
            rows = table.select('tr')
            for row in rows:
                cols = [td.text.strip() for td in row.select('td')]
                # 馬會官方表通常有 10 欄以上
                if len(cols) >= 8 and cols[0].isdigit():
                    horses.append({
                        "number": cols[0],       # 馬號
                        "brand": cols[1],        # 烙號/馬匹編號
                        "name": cols[2].split('(')[0].strip(), # 馬名
                        "weight": cols[3],       # 負磅
                        "jockey": cols[4],       # 騎師
                        "draw": cols[5],         # 檔位
                        "trainer": cols[6],      # 練馬師
                        "rating": cols[7] if len(cols) > 7 else "-", # 評分
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
        print("✅ 成功對齊馬會官方格式並更新 data.json")
    else:
        print("❌ 爬取失敗")

if __name__ == "__main__":
    update_json()
