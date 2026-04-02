# 네이버쇼핑 순위 대시보드



## 구조

```
├── .github/workflows/update-data.yml  # 매일 자동 실행
├── scripts/fetch_data.py              # 구글 시트 → data.json 변환
└── public/
    └── index.html                     # 대시보드 (data.json만 읽음)
