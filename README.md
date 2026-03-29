# 네이버쇼핑 순위 대시보드

구글 시트 데이터를 GitHub Actions로 매일 자동 수집해 GitHub Pages로 공개하는 대시보드입니다.

## 구조

```
├── .github/workflows/update-data.yml  # 매일 자동 실행
├── scripts/fetch_data.py              # 구글 시트 → data.json 변환
└── public/
    └── index.html                     # 대시보드 (data.json만 읽음)
```

## 설정 방법 (최초 1회)

### 1. GitHub 리포지토리 생성
- GitHub에서 새 리포지토리 생성 (Public 또는 Private)
- 이 폴더의 모든 파일을 업로드

### 2. GitHub Secrets 등록
리포지토리 → Settings → Secrets and variables → Actions → New repository secret

| Secret 이름 | 값 |
|------------|-----|
| `SERVICE_ACCOUNT_EMAIL` | `sheet-reader@cafe24-dashboard.iam.gserviceaccount.com` |
| `SERVICE_ACCOUNT_KEY` | 서비스 계정 private_key 전체 (-----BEGIN ~ -----END 포함) |
| `RANK_SHEET_ID` | `1TzbpjxzFUEn9CCLisgydrqGbzoRbPEwOdcjoRRf8Xfs` |
| `RANK_TAB` | `rank_log` |
| `REVIEW_SHEET_ID` | `1RDxoO6fHWyeuy39T0vUJqfRQUrrEJWtpChEk7dhAKNI` |
| `REVIEW_TAB` | `product_re` |

### 3. GitHub Pages 활성화
리포지토리 → Settings → Pages
- Source: **GitHub Actions**

### 4. 첫 번째 실행
Actions 탭 → "데이터 업데이트 & 배포" → **Run workflow** 클릭

## 접근 URL
```
https://{GitHub유저명}.github.io/{리포지토리명}/
```

## 자동 갱신 시각
매일 **오전 9시 (KST)** 자동 실행됩니다.
수동으로 즉시 갱신하려면 Actions → Run workflow 클릭.

## 보안
- 서비스 계정 키는 GitHub Secrets에만 저장 (HTML에 노출 없음)
- `index.html`은 `data.json`만 읽으므로 URL 공유해도 키 유출 없음
- `data.json`에는 시트 데이터만 포함 (인증 정보 없음)
