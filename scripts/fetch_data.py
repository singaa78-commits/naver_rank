"""
구글 시트 데이터를 가져와 public/data.json 으로 저장
GitHub Actions에서 환경변수로 서비스 계정 정보를 받음
"""
import json, os, time, urllib.parse, urllib.request
import google.auth.crypt
import google.auth.jwt

# ── 환경변수에서 설정 읽기 ──────────────────────────
CLIENT_EMAIL  = os.environ["SERVICE_ACCOUNT_EMAIL"]
PRIVATE_KEY   = os.environ["SERVICE_ACCOUNT_KEY"].replace("\\n", "\n")
RANK_SHEET_ID = os.environ["RANK_SHEET_ID"]
RANK_TAB      = os.environ.get("RANK_TAB", "rank_log")
REVIEW_SHEET_ID = os.environ["REVIEW_SHEET_ID"]
REVIEW_TAB    = os.environ.get("REVIEW_TAB", "product_re")

# ── JWT 토큰 발급 ────────────────────────────────────
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

# ── 시트 데이터 가져오기 ─────────────────────────────
def fetch_sheet(token, sheet_id, tab):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{urllib.parse.quote(tab)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()).get("values", [])

# ── 헤더 자동 감지 ───────────────────────────────────
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

# ── rank_log 파싱 ─────────────────────────────────────
def parse_rank(rows):
    if len(rows) < 2:
        return {"products": [], "trends": {"dates": [], "data": {}}}

    hdr  = [str(h).strip() for h in rows[0]]
    data = [r for r in rows[1:] if len(r) > 1 and r[0] and r[1]]

    iD = col(hdr, ["date","날짜","일자"], 0)
    iN = col(hdr, ["product","제품","상품","name","품명"], 1)
    iP = col(hdr, ["price","가격","자사","판매가"], 2)
    iR = col(hdr, ["rank","순위"], 3)
    iK = col(hdr, ["keyword","키워드"], -1)

    def get(r, i): return str(r[i]).strip() if i >= 0 and i < len(r) else ""

    all_dates = sorted(set(get(r, iD) for r in data if get(r, iD)))
    today     = all_dates[-1] if all_dates else ""
    yesterday = all_dates[-2] if len(all_dates) > 1 else today

    today_rows = [r for r in data if get(r, iD) == today]
    yest_rows  = {get(r, iN): r for r in data if get(r, iD) == yesterday}

    products = []
    for r in today_rows:
        name     = get(r, iN)
        raw_rank = get(r, iR)
        rank     = int(raw_rank) if raw_rank.isdigit() else None
        prev_r   = yest_rows.get(name)
        prev_raw = get(prev_r, iR) if prev_r else ""
        prev_rank = int(prev_raw) if prev_raw.isdigit() else None
        price_str = get(r, iP).replace(",", "").replace("₩", "")
        price = int(price_str) if price_str.isdigit() else 0
        products.append({
            "name":     name,
            "myPrice":  price,
            "rank":     rank,
            "prevRank": prev_rank,
            "keyword":  get(r, iK) if iK >= 0 else "",
        })

    # 추이 (최근 30일)
    trend_dates = all_dates[-30:]
    names = list(dict.fromkeys(get(r, iN) for r in data if get(r, iN)))
    date_name_map = {}
    for r in data:
        key = (get(r, iD), get(r, iN))
        raw = get(r, iR)
        date_name_map[key] = int(raw) if raw.isdigit() else None

    trend_data = {}
    for name in names:
        pts = [date_name_map.get((d, name)) for d in trend_dates]
        trend_data[name] = [v for v in pts if v is not None]

    used_dates = [d for d in trend_dates
                  if any(date_name_map.get((d, n)) is not None for n in names)]
    short_dates = [d[5:] if len(d) >= 8 else d for d in used_dates]

    return {
        "today":     today,
        "yesterday": yesterday,
        "products":  products,
        "trends":    {"dates": short_dates, "data": trend_data},
    }

# ── product_re 파싱 ────────────────────────────────────
def parse_reviews(rows):
    if len(rows) < 2:
        return {"latest": [], "trends": {"dates": [], "data": {}}}

    hdr  = [str(h).strip() for h in rows[0]]
    data = [r for r in rows[1:] if len(r) > 1 and r[0] and r[1]]

    iD   = col(hdr, ["date","날짜"], 0)
    iN   = col(hdr, ["product_name","product","제품","name"], 1)
    iURL = col(hdr, ["url","링크"], 2)
    iP   = col(hdr, ["판매가","price","가격"], 3)
    iRat = col(hdr, ["평점","rating","score"], 4)
    iCnt = col(hdr, ["리뷰수","review","count"], 5)

    def get(r, i): return str(r[i]).strip() if i >= 0 and i < len(r) else ""

    all_dates = sorted(set(get(r, iD) for r in data if get(r, iD)))
    latest    = all_dates[-1] if all_dates else ""

    latest_rows = [r for r in data if get(r, iD) == latest]
    result_latest = []
    for r in latest_rows:
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

    # 평점·리뷰수 추이
    trend_dates = all_dates[-30:]
    names = list(dict.fromkeys(get(r, iN) for r in data if get(r, iN)))
    rev_map = {}
    for r in data:
        key = (get(r, iD), get(r, iN))
        rev_map[key] = {
            "rating": clean_num(get(r, iRat)) or 0,
            "count":  int(clean_num(get(r, iCnt)) or 0),
        }

    trend_data = {}
    for name in names:
        ratings = [rev_map[(d, name)]["rating"] for d in trend_dates if (d, name) in rev_map]
        counts  = [rev_map[(d, name)]["count"]  for d in trend_dates if (d, name) in rev_map]
        trend_data[name] = {"ratings": ratings, "counts": counts}

    used_dates = [d for d in trend_dates if any((d, n) in rev_map for n in names)]
    short_dates = [d[5:] if len(d) >= 8 else d for d in used_dates]

    return {
        "latest": result_latest,
        "trends": {"dates": short_dates, "data": trend_data},
    }

# ── 메인 ────────────────────────────────────────────────
def main():
    print("토큰 발급 중…")
    token = get_token()
    print("✅ 토큰 발급 완료")

    print(f"rank_log 시트 로드 중… ({RANK_SHEET_ID}/{RANK_TAB})")
    rank_rows = fetch_sheet(token, RANK_SHEET_ID, RANK_TAB)
    print(f"  → {len(rank_rows)}행")

    print(f"product_re 시트 로드 중… ({REVIEW_SHEET_ID}/{REVIEW_TAB})")
    review_rows = fetch_sheet(token, REVIEW_SHEET_ID, REVIEW_TAB)
    print(f"  → {len(review_rows)}행")

    rank_data   = parse_rank(rank_rows)
    review_data = parse_reviews(review_rows)

    output = {
        "updatedAt": time.strftime("%Y-%m-%d %H:%M UTC"),
        "rank":   rank_data,
        "review": review_data,
    }

    os.makedirs("public", exist_ok=True)
    with open("public/data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ public/data.json 저장 완료")
    print(f"   제품: {len(rank_data['products'])}개")
    print(f"   리뷰: {len(review_data['latest'])}개")

if __name__ == "__main__":
    main()
