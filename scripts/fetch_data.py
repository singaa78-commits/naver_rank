"""
구글 시트 데이터를 가져와 public/data.json 으로 저장
rank_log 헤더: timestamp | keyword | product_name | mall_name | rank | price | link | title
product_re 헤더: 날짜 | product_name | url | 판매가 | 평점 | 리뷰수 | 수집시각
"""
import json, os, time, urllib.parse, urllib.request, re
from datetime import datetime
import google.auth.crypt
import google.auth.jwt

CLIENT_EMAIL    = os.environ["SERVICE_ACCOUNT_EMAIL"]
PRIVATE_KEY     = os.environ["SERVICE_ACCOUNT_KEY"].replace("\\n", "\n")
RANK_SHEET_ID   = os.environ["RANK_SHEET_ID"]
RANK_TAB        = os.environ.get("RANK_TAB", "rank_log")
REVIEW_SHEET_ID = os.environ["REVIEW_SHEET_ID"]
REVIEW_TAB      = os.environ.get("REVIEW_TAB", "product_re")

# ── 자사 mall_name (순위 필터링용 — 비어있으면 전체 포함) ──
MY_MALL = os.environ.get("MY_MALL", "가시제거연구소")

def get_token():
    now = int(time.time())
    payload = {
        "iss":   CLIENT_EMAIL,
        "scope": "https://www.googleapis.com/auth/spreadsheets.readonly",
        "aud":   "https://oauth2.googleapis.com/token",
        "exp":   now + 3600,
        "iat":   now,
    }
    signer = google.auth.crypt.RSASigner.from_service_account_info({
        "private_key":  PRIVATE_KEY,
        "client_email": CLIENT_EMAIL,
    })
    jwt_token = google.auth.jwt.encode(signer, payload).decode()
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion":  jwt_token,
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]

def fetch_sheet(token, sheet_id, tab):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{urllib.parse.quote(tab)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()).get("values", [])

def col(hdr, keys, fallback):
    for i, h in enumerate(hdr):
        if any(k in h.lower() for k in keys):
            return i
    return fallback

def clean_num(s):
    try:
        return float(str(s).replace(",", "").strip())
    except:
        return None

def to_dt(s):
    """다양한 날짜 형식 파싱 — '2026. 3. 28' 포함"""
    s = str(s).strip()
    # 숫자만 추출해서 파싱
    nums = re.findall(r'\d+', s)
    if len(nums) >= 3:
        y, m, d = int(nums[0]), int(nums[1]), int(nums[2])
        try:
            return datetime(y, m, d)
        except:
            pass
    return None

def normalize_date(s):
    """날짜를 YYYY-MM-DD 표준 형식으로 변환"""
    dt = to_dt(s)
    return dt.strftime("%Y-%m-%d") if dt else str(s).strip()

def sort_asc(date_strs):
    """날짜 문자열 리스트 → 오름차순(과거→최신) 정렬"""
    pairs = [(to_dt(d), d) for d in date_strs if to_dt(d)]
    pairs.sort(key=lambda x: x[0])
    return [p[1] for p in pairs]

def label(d):
    dt = to_dt(d)
    return f"{dt.month}.{dt.day}" if dt else d

def parse_rank(rows):
    if len(rows) < 2:
        return {"today":"—","yesterday":"—","products":[],"trends":{"dates":[],"data":{}}}

    hdr  = [str(h).strip() for h in rows[0]]
    data = [r for r in rows[1:] if len(r) > 1 and r[0] and r[1]]

    print(f"  rank_log 헤더: {hdr}")

    # 실제 컬럼: timestamp | keyword | product_name | mall_name | rank | price
    iD    = col(hdr, ["timestamp","date","날짜","일자"], 0)
    iK    = col(hdr, ["keyword","키워드"], 1)
    iN    = col(hdr, ["product_name","product","제품","상품","name","품명"], 2)
    iMall = col(hdr, ["mall_name","mall","쇼핑몰","판매처"], 3)
    iR    = col(hdr, ["rank","순위"], 4)
    iP    = col(hdr, ["price","가격","자사","판매가"], 5)

    def get(r, i):
        return str(r[i]).strip() if 0 <= i < len(r) else ""

    # 날짜 정규화 후 오름차순 정렬
    def norm(r): return normalize_date(get(r, iD))

    all_dates = sort_asc(list(set(norm(r) for r in data if norm(r))))

    today     = all_dates[-1] if all_dates else "—"
    yesterday = all_dates[-2] if len(all_dates) > 1 else today

    print(f"  rank 날짜 마지막 5개: {all_dates[-5:]}")
    print(f"  오늘={today}, 어제={yesterday}")

    # 자사 제품 필터 (가시제거연구소 또는 네이버 카탈로그)
    def is_mine(r):
        mall = get(r, iMall)
        return MY_MALL in mall or "네이버" in mall or mall == ""

    today_rows = [r for r in data if normalize_date(get(r, iD)) == today and is_mine(r)]
    yest_rows  = [r for r in data if normalize_date(get(r, iD)) == yesterday and is_mine(r)]
    yest_map   = {get(r, iN): r for r in yest_rows}

    print(f"  오늘 자사 행: {len(today_rows)}개")

    products = []
    for r in today_rows:
        name      = get(r, iN)
        raw_rank  = get(r, iR)
        # rank가 '미노출' 등 숫자가 아니면 None
        rank      = int(raw_rank) if raw_rank.isdigit() else None
        prev      = yest_map.get(name)
        prev_raw  = get(prev, iR) if prev else ""
        prev_rank = int(prev_raw) if prev_raw.isdigit() else None
        price_str = get(r, iP).replace(",","").replace("₩","")
        price     = int(price_str) if price_str.isdigit() else 0
        keyword   = get(r, iK)
        products.append({
            "name":     name,
            "myPrice":  price,
            "rank":     rank,
            "prevRank": prev_rank,
            "keyword":  keyword,
        })

    # 추이: 최근 90일
    trend_dates = all_dates[-90:]
    names = list(dict.fromkeys(get(r, iN) for r in data if is_mine(r) and get(r, iN)))

    dm = {}
    for r in data:
        if not is_mine(r): continue
        k   = (normalize_date(get(r, iD)), get(r, iN))
        raw = get(r, iR)
        dm[k] = int(raw) if raw.isdigit() else None

    used = [d for d in trend_dates if any(dm.get((d, n)) is not None for n in names)]
    trend_data = {name: [dm.get((d, name)) for d in used] for name in names}

    return {
        "today":     today,
        "yesterday": yesterday,
        "products":  products,
        "trends":    {"dates": [label(d) for d in used], "data": trend_data},
    }

def parse_reviews(rows):
    if len(rows) < 2:
        return {"latest":[],"trends":{"dates":[],"data":{}}}

    hdr  = [str(h).strip() for h in rows[0]]
    data = [r for r in rows[1:] if len(r) > 1 and r[0] and r[1]]

    print(f"  product_re 헤더: {hdr}")

    iD   = col(hdr, ["date","날짜","timestamp"], 0)
    iN   = col(hdr, ["product_name","product","제품","name"], 1)
    iURL = col(hdr, ["url","링크"], 2)
    iP   = col(hdr, ["판매가","price","가격"], 3)
    iRat = col(hdr, ["평점","rating","score"], 4)
    iCnt = col(hdr, ["리뷰수","review","count"], 5)

    def get(r, i):
        return str(r[i]).strip() if 0 <= i < len(r) else ""
    def norm(r): return normalize_date(get(r, iD))

    all_dates = sort_asc(list(set(norm(r) for r in data if norm(r))))
    latest    = all_dates[-1] if all_dates else ""

    print(f"  review 날짜 마지막 5개: {all_dates[-5:]}")

    result_latest = []
    for r in [x for x in data if norm(x) == latest]:
        price = clean_num(get(r, iP))
        rat   = clean_num(get(r, iRat))
        cnt   = clean_num(get(r, iCnt))
        result_latest.append({
            "name":   get(r, iN),
            "url":    get(r, iURL),
            "price":  int(price) if price else 0,
            "rating": rat or 0,
            "count":  int(cnt) if cnt else 0,
            "date":   latest,
        })

    trend_dates = all_dates[-90:]
    names = list(dict.fromkeys(get(r, iN) for r in data if get(r, iN)))

    rm = {}
    for r in data:
        k = (norm(r), get(r, iN))
        rm[k] = {
            "rating": clean_num(get(r, iRat)) or 0,
            "count":  int(clean_num(get(r, iCnt)) or 0),
        }

    used = [d for d in trend_dates if any((d, n) in rm for n in names)]
    trend_data = {}
    for name in names:
        trend_data[name] = {
            "ratings": [rm[(d,name)]["rating"] if (d,name) in rm else None for d in used],
            "counts":  [rm[(d,name)]["count"]  if (d,name) in rm else None for d in used],
        }

    return {
        "latest":  result_latest,
        "trends":  {"dates": [label(d) for d in used], "data": trend_data},
    }

def fetch_okr_data():
    """OKR 시트에서 최신 데이터를 읽어 okr_data.json 으로 저장"""
    okr_key_json = os.environ.get("OKR_SERVICE_ACCOUNT_KEY", "")
    okr_sheet_id = os.environ.get("OKR_SHEET_ID", "")
    if not okr_key_json or not okr_sheet_id:
        print("OKR_SERVICE_ACCOUNT_KEY 또는 OKR_SHEET_ID 없음 — 건너뜀")
        return

    # OKR 전용 토큰 발급
    key_obj = json.loads(okr_key_json)
    okr_email = key_obj["client_email"]
    okr_pk    = key_obj["private_key"].replace("\\n", "\n")
    now = int(time.time())
    payload = {
        "iss":   okr_email,
        "scope": "https://www.googleapis.com/auth/spreadsheets",
        "aud":   "https://oauth2.googleapis.com/token",
        "exp":   now + 3600,
        "iat":   now,
    }
    signer = google.auth.crypt.RSASigner.from_service_account_info({
        "private_key":  okr_pk,
        "client_email": okr_email,
    })
    jwt_token = google.auth.jwt.encode(signer, payload).decode()
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion":  jwt_token,
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req) as resp:
        token = json.loads(resp.read())["access_token"]

    # 시트 읽기
    rows = fetch_sheet(token, okr_sheet_id, "OKR")
    if len(rows) < 2:
        print("OKR 시트 데이터 없음")
        return

    headers = rows[0]  # date, kr1, kr2, kr3_싹그로스, ...
    latest  = {}
    latest_date = ""

    # 각 컬럼별 가장 최신 값 추출
    for row in rows[1:]:
        date = row[0] if row else ""
        for i, h in enumerate(headers):
            if h == "date":
                continue
            val = row[i] if i < len(row) else ""
            if val != "":
                latest[h] = val
                if date > latest_date:
                    latest_date = date

    output = {
        "updatedAt": latest_date,
        "data": latest,
        "headers": headers,
    }
    os.makedirs("public", exist_ok=True)
    with open("public/okr_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ OKR 데이터 저장 완료 (기준일: {latest_date})")


def main():
    print("토큰 발급 중…")
    token = get_token()
    print("✅ 완료")

    print("rank_log 로드…")
    rank_rows = fetch_sheet(token, RANK_SHEET_ID, RANK_TAB)
    print(f"  {len(rank_rows)}행")

    print("product_re 로드…")
    rev_rows = fetch_sheet(token, REVIEW_SHEET_ID, REVIEW_TAB)
    print(f"  {len(rev_rows)}행")

    rank_data = parse_rank(rank_rows)
    rev_data  = parse_reviews(rev_rows)

    output = {
        "updatedAt": time.strftime("%Y-%m-%d %H:%M UTC"),
        "rank":   rank_data,
        "review": rev_data,
    }

    os.makedirs("public", exist_ok=True)
    with open("public/data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 저장 완료 — 제품 {len(rank_data['products'])}개, 리뷰 {len(rev_data['latest'])}개")
    print("OKR 데이터 수집 중…")
    fetch_okr_data()

if __name__ == "__main__":
    main()
