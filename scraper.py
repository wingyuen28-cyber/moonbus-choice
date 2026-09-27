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
    """精準對齊馬會排位表所有欄位 (馬號/烙號/馬名/騎師/檔位/負磅/練馬師)"""
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
    # 尋找馬會排位表格
    table = soup.select_one('table.starter, table.table_bd')
    if table:
        rows = table.select('tr')
        for row in rows:
            cols = row.select('td')
            # 確保為有效的馬匹資料列 (第一欄必須為數字馬號)
            if len(cols) >= 6:
                h_no_raw = cols[0].text.strip()
                if h_no_raw.isdigit():
                    
                    # 1. 馬匹烙號 (例如 K114, H334)
                    brand_match = re.search(r'([A-Z]\d{3})', row.get_text())
                    h_brand = brand_match.group(1) if brand_match else "--"

                    # 2. 馬名 (尋找包含馬名連結或無數字的文字)
                    h_name = "--"
                    name_a = row.select_one('a[href*="Horse.aspx"], a[href*="horse"]')
                    if name_a:
                        h_name = name_a.text.strip().split('(')[0]
                    else:
                        for col in cols[1:4]:
                            txt = col.text.strip()
                            if txt and not txt.isdigit() and not re.search(r'[A-Z]\d{3}', txt) and len(txt) <= 6:
                                h_name = txt.split('(')[0]
                                break

                    # 3. 騎師 (馬會頁面中騎師通常帶有 JockeyProfile 或騎師連結)
                    jockey = "--"
                    jockey_a = row.select_one('a[href*="Jockey"], a[href*="jockey"]')
                    if jockey_a:
                        jockey = jockey_a.text.strip()
                    else:
                        # 備用：從欄位文字中過濾騎師名
                        for col in cols:
                            txt = col.text.strip()
                            if any(char in txt for char in ["潘頓", "田泰安", "布文", "何澤堯", "周俊樂", "潘明輝", "袁幸堯", "鍾易禮", "艾兆禮", "希威森", "黃智弘", "金誠剛"]):
                                jockey = txt
                                break

                    # 4. 檔位 (馬會檔位通常為 1~14 的獨立數字 td)
                    draw = "--"
                    for col in cols[3:8]:
                        txt = col.text.strip()
                        if txt.isdigit() and 1 <= int(txt) <= 14:
                            # 避開馬號與負磅
                            if txt != h_no_raw and not (100 <= int(txt) <= 140):
                                draw = txt
                                break

                    # 5. 負磅 (105~135 之間的數字)
                    weight = "--"
                    weight_match = re.search(r'(1[0-3]\d)', row.get_text())
                    if weight_match:
                        weight = weight_match.group(1)

                    # 6. 練馬師 (帶有 TrainerProfile 或練馬師連結)
                    trainer = "--"
                    trainer_a = row.select_one('a[href*="Trainer"], a[href*="trainer"]')
                    if trainer_a:
                        trainer = trainer_a.text.strip()
                    else:
                        for col in reversed(cols):
                            txt = col.text.strip()
                            if any(char in txt for char in ["沈集成", "告東尼", "韋達", "方嘉柏", "姚本輝", "賀賢", "文家良", "蔡約翰", "廖康銘", "鄭俊偉", "巫偉傑", "呂健威", "高伯新", "苗禮德", "羅富全", "葉楚航", "蘇偉賢", "徐雨石"]):
                                trainer = txt
                                break

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
    existing_data = {}
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            print("讀取舊 data.json 失敗:", e)

    soup = get_soup(BASE_URL)
    if not soup:
        print("無法訪問馬會主頁")
        return

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

    numbers = []
    for a in soup.find_all('a', href=True):
        if 'RaceNo=' in a['href']:
            m = re.search(r'RaceNo=(\d+)', a['href'])
            if m:
                numbers.append(int(m.group(1)))
    total_races = max(numbers) if numbers else 11

    races_dict = {}
    if existing_data.get("races") and existing_data.get("race_date") == race_date:
        for r in existing_data["races"]:
            races_dict[r["race_number"]] = r

    for r_no in range(1, total_races + 1):
        url = f"{BASE_URL}?RaceNo={r_no}"
        r_soup = get_soup(url) if r_no > 1 else soup
        race_data = parse_race_page(r_soup, r_no)

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

    print(f"✅ 成功精準對齊 1~{len(all_races)} 場排位資料！")

if __name__ == "__main__":
    update_all_races()
