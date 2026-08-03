# Paper Radar

관심 저널의 최신 논문을 매일 수집하고, 제목과 초록을 바탕으로 연구 주제와 방법론을 분류하는 개인용 GitHub Pages 대시보드입니다.

## 대상 저널

- Management Science
- Information Systems Research
- Journal of Management Information Systems
- Decision Support Systems
- Information & Management
- MIS Quarterly
- Strategic Management Journal
- Strategic Entrepreneurship Journal
- Quarterly Journal of Economics
- PNAS Nexus

## 작동 방식

1. GitHub Actions가 매일 오전 6시 17분(KST)에 실행됩니다.
2. `scripts/update_papers.py`가 OpenAlex에서 최근 1년 논문과 초록을 수집합니다.
3. 제목과 초록의 표현 및 문맥을 기반으로 지정 연구주제와 정량방법론을 분류합니다.
4. 관련 주제이면서 정량연구로 판별된 논문만 `data/papers.json`에 저장합니다.
5. 결과가 바뀌면 GitHub Pages가 자동으로 재배포됩니다.

웹페이지는 Main과 Saved Papers로 구성됩니다. 연구주제는 노란색, 방법론은 연두색 태그로 표시되며, 책갈피한 논문 전체 정보는 브라우저의 `localStorage`에 보관됩니다. 따라서 논문이 최신 수집 범위에서 벗어나더라도 같은 브라우저의 Saved Papers에 유지됩니다.

분류어와 저널 목록은 각각 `scripts/update_papers.py`, `config/journals.json`에서 수정할 수 있습니다.

## 로컬 실행

```bash
python scripts/update_papers.py
python -m http.server 8000
```

브라우저에서 `http://localhost:8000`을 엽니다.

## 데이터 출처

논문 메타데이터와 초록은 [OpenAlex](https://openalex.org/)에서 가져옵니다.
