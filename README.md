# iCIR Lab 프로젝트 페이지 템플릿

연구 프로젝트 소개 페이지(제목·저자·링크, 데모 영상, 케이스 영상 갤러리, 초록, 시스템 개요)를
`content.yaml` 하나만 수정해서 만드는 템플릿입니다. 디자인과 동작은
[클린룸 프로젝트 페이지](https://icirlab.github.io/icir_cleanroom_page/)와 같습니다.

- 한·영 전환 지원(선택). 한 언어만 쓰면 전환 버튼이 사라집니다.
- 데스크톱·모바일 대응, 화면에 보이는 영상만 무음 자동 반복 재생
- 빌드 도구 설치 없이 Python 스크립트 하나로 `docs/index.html` 생성, GitHub Pages로 배포

이 템플릿은 출발점입니다. 구성이나 디자인이 프로젝트에 맞지 않으면 코드를 참고해 자유롭게 고쳐 쓰세요.
어디를 고치면 되는지는 [직접 고쳐 쓰기](#직접-고쳐-쓰기)에 정리했습니다.

## 준비물

Python 3와 PyYAML. ROS 2가 설치된 PC에는 보통 이미 있습니다. 없다면:

```sh
sudo apt install python3-yaml   # 또는 pip install pyyaml
```

## 새 프로젝트 페이지 만들기

### 1. 저장소 만들기

1. GitHub에서 이 저장소 오른쪽 위의 **Use this template → Create a new repository**를 누릅니다.
2. Owner는 `iCIRLab`, Repository name은 `<프로젝트>_page`처럼 정하고, **Public**을 선택한 뒤
   **Create repository**를 누릅니다. GitHub 무료 플랜에서는 Public 저장소만 Pages로 게시할 수 있습니다.
3. 만든 저장소를 clone합니다.

   ```sh
   git clone https://github.com/iCIRLab/<프로젝트>_page.git
   cd <프로젝트>_page
   ```

### 2. 내용 작성하기

1. `content.yaml`을 수정합니다. 파일 안의 주석에 각 항목의 설명이 있습니다.
2. 영상·이미지를 `docs/media/`에 넣고 `content.yaml`의 `media` 경로를 바꿉니다.
   예시용 `docs/media/placeholder.svg`는 다 바꾼 뒤 지워도 됩니다.
3. 페이지를 생성하고 미리 봅니다.

   ```sh
   python3 build.py --serve
   ```

   <http://localhost:8000/>에서 확인하고 `Ctrl+C`로 종료합니다.
   `content.yaml`을 고칠 때마다 다시 실행하세요.
4. `content.yaml`, `docs/` 전체(생성된 `docs/index.html` 포함)를 커밋하고 push합니다.

   ```sh
   git add content.yaml docs
   git commit -m "Add project page content"
   git push
   ```

### 3. GitHub Pages 켜기 (저장소마다 처음 한 번)

1. GitHub의 저장소 화면에서 **Settings** 탭 → 왼쪽 메뉴의 **Pages**로 갑니다.
2. **Build and deployment**의 Source가 **Deploy from a branch**인지 확인합니다.
3. **Branch**에서 `None`을 `main`으로, 옆의 폴더를 `/ (root)`에서 `/docs`로 바꾸고 **Save**를 누릅니다.
4. 1~2분 뒤 Pages 화면 위쪽에 `Your site is live at ...`과 주소가 표시됩니다.
   진행 상황은 **Actions** 탭의 *pages build and deployment*에서 볼 수 있습니다.

주소는 `https://icirlab.github.io/<저장소 이름>/`입니다(개인 계정 저장소라면 `https://<아이디>.github.io/<저장소 이름>/`).
이후에는 `main`에 push할 때마다 자동으로 다시 게시됩니다.

## content.yaml 작성법

텍스트는 두 가지로 쓸 수 있습니다.

```yaml
title: Same text in every language          # 모든 언어에 같은 텍스트
title: {en: English title, ko: 한국어 제목}   # 언어별 텍스트
body:                                        # 긴 글: 빈 줄로 문단 구분
  en: |
    First paragraph.

    Second paragraph.
  ko: |
    첫 번째 문단.

    두 번째 문단.
```

- `languages: [en, ko]`의 첫 번째가 기본 언어입니다. `[ko]`나 `[en]`만 쓰면 단일 언어 페이지가 됩니다.
- 한·영 페이지에서 언어별 텍스트의 한쪽이 빠지면 빌드가 멈추고 위치를 알려줍니다.
- 텍스트 안에 `<a href="...">`, `<strong>`, `<em>`, `<br>` 같은 HTML을 쓸 수 있습니다.
  다른 사이트로 가는 링크는 자동으로 새 탭에서 열립니다.
- `media`는 `docs/` 기준 경로입니다. `.mp4`·`.webm`은 영상으로, 그 외(`.png`, `.jpg`, `.svg`, `.gif`)는
  이미지로 표시합니다. 파일이 없으면 빌드가 멈춥니다.

섹션은 `sections` 목록의 순서대로 페이지와 상단 메뉴에 표시됩니다.

| `type` | 내용 | 기본 제목 |
| --- | --- | --- |
| `cases` | 케이스 영상 갤러리(데스크톱 2열, 모바일 1열). `items`에 `media`, `title`, `text` | Case videos / 케이스별 영상 |
| `abstract` | 초록. `body`에 문단 | Abstract / 초록 |
| `overview` | 단계별 시스템 구성도(`flow`) 또는 직접 만든 그림(`media`, `caption`) | System overview / 시스템 개요 |
| `text` | 자유 섹션. `title`(필수), `body`, `media`, `caption` | — |

모든 섹션에 `kicker`(제목 위 작은 문구), `title`, `intro`(한 줄 소개), `band`(배경색 여부),
`id`(메뉴 링크 주소)를 쓸 수 있습니다. 오타가 난 키는 빌드 시 알려줍니다.

## 주의할 점

- `docs/index.html`은 생성 파일입니다. 직접 고치면 다음 빌드에서 덮어씁니다.
  `python3 build.py --check`로 커밋 전에 최신 상태인지 확인할 수 있습니다.
- GitHub는 100 MB가 넘는 파일을 거부합니다. 웹용으로는 영상 하나에 수십 MB 이하가 좋습니다.
  소리를 빼고 압축하는 예:

  ```sh
  ffmpeg -i input.mp4 -c:v libx264 -crf 28 -preset slow -an -movflags +faststart output.mp4
  ```

## 직접 고쳐 쓰기

섹션 구성, 레이아웃, 디자인 등 프로젝트에 맞지 않는 부분은 아래 파일을 참고해 고쳐 쓰세요.
고친 내용은 각자의 저장소에만 반영되고 이 템플릿에는 영향을 주지 않습니다.

| 바꾸고 싶은 것 | 고칠 파일 |
| --- | --- |
| 색상·글꼴·여백·레이아웃 | `docs/assets/site.css` |
| 언어 전환, 상단 메뉴, 영상 재생 같은 동작 | `docs/assets/site.js` |
| 섹션의 HTML 구조, 새 섹션 종류, `content.yaml` 항목 | `build.py` |

- `site.css`와 `site.js`는 빌드로 생성되지 않으므로 직접 고치면 됩니다. 수정하면 브라우저 캐시가 자동으로 갱신됩니다.
- 섹션 HTML은 `build.py`의 `Page.section()`에서 만듭니다. `content.yaml`에 새 항목이나 섹션 종류를 추가하면
  `build.py`의 `SCHEMA`(와 `SECTION_TYPES`)에도 추가해야 빌드 검사를 통과합니다.
- 원본 클린룸 페이지에 있던 수식(KaTeX), 평가지표, 결과 표 섹션은 이 템플릿에서 뺐습니다. 필요하면
  [원본 저장소](https://github.com/iCIRLab/icir_cleanroom_page)의 `docs/index.html`을 참고하세요.
- 코드 구조 요약은 `AGENTS.md`에 있습니다. Claude Code, Codex, Copilot, Cursor 같은 AI 도구도 고칠 때 이 파일을 읽습니다.
