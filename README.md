AI Fanpage Agent
================

Muc tieu: tu dong xu ly binh luan/inbox fanpage Facebook bang AI + automation, tang toc ban hang trong 7 ngay trien khai.

Thu muc & file (yeu cau)
------------------------
```
main.py
config.json
requirements.txt
core/
  login.py
  cookies.py
  comments.py
  actions.py
  ai_engine.py
  inbox.py
  post.py
  report.py
db/
  database.py
utils/
  logger.py
  scheduler.py
ui/
  (de sau neu can PyQt6)
```

Tinh nang MVP (demo)
--------------------
- Auto classify & reply binh luan: rule-based + co san hook LLM (OpenAI).
- Auto hide spam/chui, mo inbox khi thieu SĐT.
- Auto post (stub) va bao cao cuoi ngay (JSON).
- Scheduler vong lap chu ky, dem mo (khong can Facebook that).

Cau hinh
--------
- Sua `config.json` (demo true de chay gia lap). Truong chinh: `page_id`, `cookie_path`, `interval_seconds`, `max_actions_per_cycle`, `demo`, `openai_api_key`, `openai_model`, `report_dir`, `log_level`, `graph_access_token` (neu dung Graph API), `headless` (False de de dang nhap tay lan dau).

Chay thu nhanh
--------------
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium  # cai browser cho Playwright
python main.py --demo --cycles 1 --interval 30
```
- Bao cao se luu tai `reports/daily-YYYY-MM-DD.json`, log hanh dong tai `data/actions.json`.

Thu tu bat buoc truoc vong loop
-------------------------------
1) Login Facebook → nap cookie vao trinh duyet (Playwright). Neu cookie OK se vao newsfeed, khong can login lai; neu het han, dang nhap tay 1 lan de luu cookie moi.
2) Chon fanpage → xac dinh page lam viec. Gia lap: auto chon page demo; thuc te: goi Graph API (can `graph_access_token`) hoac truy cap /pages bang Playwright de lay danh sach, user chon va luu `page_id` vao `config.json`.
3) Bat dau vong loop chinh → Fetch comment → AI hieu → Quyet dinh → Reply/Hide/Inbox/Post → Log → Sleep 1-3 phut → lap lai.

UI dashboard (tu chon)
----------------------
- Streamlit (web) khong cai san trong requirements de tranh loi pyarrow tren Python 3.14. Neu muon dung, khuyen nghi Python 3.10-3.12 va tu cai: `pip install streamlit==1.38.*` roi chay `streamlit run ui/dashboard.py`.
- Agent: `python main.py --cycles 0`
- Dashboard Streamlit doc `reports/daily-*.json` va `data/actions.json`.

UI PyQt6 (desktop)
------------------
- Cai dep: `pip install -r requirements.txt`
- Chay: `python -m ui.qt_dashboard`
- Chuc nang: xem report moi nhat va log hanh dong trong cua so desktop, nut Reload de tai lai.

Huong phat trien tiep
---------------------
- Giai doan 1: noi Graph API hoac Playwright de lay/reply/hide comment, xu ly login cookie trong `core/login.py`.
- Giai doan 2: hoan thien kịch ban inbox va auto post; bo loc spam nang cao; rate limit/backoff.
- Giai doan 3: dashboard UI (thu muc `ui/`), them tests, bao mat cookie/token (khong commit secret).
