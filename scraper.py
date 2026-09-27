import json
import requests
from bs4 import BeautifulSoup
import re
import os

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
        print(f"網絡請求失敗 ({url}): {e}")
    return None

def parse_race_page(soup, r_no):
    """精準提取特定場次的排位資料"""
    if not soup:
        return None

    # 解析賽事頭條 (開跑時間、途程、班次、跑道)
    header_text = ""
    race_card_hdr = soup.select_one('.race_tab, .f_fs13, .race_header, .race_tab_bg')
    if race_card_hdr:
        header_text = race_card_hdr.get_text()

    post_time = "--:--"
    time_match = re.search(r'(\d{1,2}:\d{2})', header_text)
    if time_match:
        post_time = time_match.group(1)

    race_class = "第---班"
    class_match = re.search(r'(第[一二三四五]班|Group \d|G\d|條件賽)', header_text)
    if class_match:
        race_class = class_match.group(1)

    distance = "----米"
    dist_match = re.search(r'(\d{3,4})米', header_text)
    if dist_match:
        distance = f"{dist_match.group(1)}米"

    course = "草地"
    if "全天候" in header_text:
        course = "全天候跑道"
    elif "草地" in header_text:
        course = "草地"

    horses = []
    # 尋找排位表格
    table = soup.select_one('table.starter, table.table_bd')
    if table:
        rows = table.select('tr')
        for row in rows:
            cols = row.select('td')
            # 確保為有效的馬匹資料列 (第一欄必須為數字馬號)
            if len(cols) >= 6:
                h_no_raw = cols[0].text.strip()
                if h_no_raw.isdigit():
                    
                    # 精準提取各欄位，防止隱藏列干擾
                    # 馬名 (通常包含烙號於括號內或鄰近 tds)
                    name_td = row.select_one('td.horse, td[class*="horse"]')
                    h_name = name_td.text.strip().split('(')[0] if name_td else cols[2].text.strip().split('(')[0]

                    # 烙號/編號
                    brand_match = re.search(r'([A-Z]\d{3})', row.get_text())
                    h_brand = brand_match.group(1) if brand_match else "--"

                    # 騎師
                    jockey_td = row.select_one('td.jockey, td[class*="jockey"]')
                    jockey = jockey_td.text.strip() if jockey_td else cols[3].text.strip()

                    # 檔位 (數字)
                    draw = "--"
                    for col in cols:
                        txt = col.text.strip()
                        if txt.isdigit() and int(txt) <= 14 and col != cols[0]:
                            draw = txt

                    # 負磅 (通常在 105 ~ 135 磅之間)
                    weight = "--"
                    weight_match = re.search(r'(1[0-3]\d)', row.get_text())
                    if weight_match:
                        weight = weight_match.group(1)

                    # 練馬師
                    trainer = cols[-2].text.strip() if len(cols) > 6 else "--"

                    horses.append({
                        "number": h_no_raw,
                        "brand": h_brand,
                        "name": h_name,
                        "jockey": jockey,
                        "draw": draw,
                        "weight": weight,
                        "trainer": trainer
                    })

    return {
        "race_number": r_no,
        "post_time": post_time,
        "class": race_class,
        "distance": distance,
        "course": course,
        "horses": horses
    }

def update_all_races():
    # 1. 先載入舊有 data.json 檔案，防止舊賽事前幾場資料被覆蓋遺失
    existing_data = {}
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print("讀取舊 data.json 失敗，將建立新檔:", e)

    soup = get_soup(BASE_URL)
    if not soup:
        print("無法訪問馬會主頁")
        return

    # 2. 獲取當日賽日基礎資訊
    race_date = "2026年9月27日"
    venue = "沙田"
    track_condition = "快地"

    page_text = soup.get_text()
    date_match = re.search(r'\d{4}年\d{1,2}月\d{1,2}日', page_text)
    if date_match:
        race_date = date_match.group(0)

    if "跑馬地" in page_text:
        venue = "跑馬地"

    conditions = ["快地", "好地", "黏地", "軟地", "重地", "濕快地", "濕慢地"]
    for c in conditions:
        if c in page_text:
            track_condition = c
            break

    # 3. 偵測總場次 (8~11場)
    numbers = []
    for a in soup.find_all('a', href=True):
        if 'RaceNo=' in a['href']:
            m = re.search(r'RaceNo=(\d+)', a['href'])
            if m:
                numbers.append(int(m.group(1)))
    total_races = max(numbers) if numbers else 11

    # 建立或複製原有場次字典 (key: race_number)
    races_dict = {}
    if existing_data.get("races") and existing_data.get("race_date") == race_date:
        for r in existing_data["races"]:
            races_dict[r["race_number"]] = r

    # 4. 爬取最新場次資料並合併
    for r_no in range(1, total_races + 1):
        url = f"{BASE_URL}?RaceNo={r_no}"
        r_soup = get_soup(url) if r_no > 1 else soup
        race_data = parse_race_page(r_soup, r_no)

        # 若成功爬到該場次的馬匹，則更新；若該場已完賽且無新排位表，保留舊資料
        if race_data and len(race_data["horses"]) > 0:
            races_dict[r_no] = race_data
        elif r_no not in races_dict:
            races_dict[r_no] = race_data or {
                "race_number": r_no,
                "post_time": "--:--",
                "class": "已完賽",
                "distance": "----",
                "course": "草地",
                "horses": []
            }

    # 轉回 List 格式並排序
    all_races = [races_dict[k] for k in sorted(races_dict.keys())]

    final_data = {
        "race_date": race_date,
        "venue": venue,
        "track_condition": track_condition,
        "total_races": len(all_races),
        "races": all_races
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 成功記錄 1~{len(all_races)} 場完整賽事資料至 data.json！")

if __name__ == "__main__":
    update_all_races()
