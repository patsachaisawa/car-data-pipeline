# Car Data Pipeline

โปรเจกต์ data pipeline ครบวงจรสำหรับข้อมูลรถยนต์ 100,000 คัน จาก Kaggle ไปจนถึง Dashboard บน Looker Studio (เดิมชื่อ Data Studio) อัปเดตทั้งระบบได้ด้วยคำสั่งเดียว

```
Car_Data.csv ──ingest.py──▶ PostgreSQL (raw_data) ──transform.py──▶ PostgreSQL (production)
                                                                          │
                                       Looker Studio ◀── Google Sheets ◀──┘ publish.py
```

`run_pipeline.py` เรียก ingest → transform → publish ต่อกันให้อัตโนมัติ

## ชุดข้อมูล

- **ที่มา:** Car Data จาก Kaggle (ไฟล์ `Car_Data.csv`) ลิงก์: _[ใส่ลิงก์ชุดข้อมูลที่นี่]_
- **ขนาด:** 100,000 แถว × 8 คอลัมน์ (`ID`, `Brand`, `Model`, `Year`, `Color`, `Mileage`, `Price`, `Condition`)
- **ข้อควรทราบ:** ค่าในแต่ละคอลัมน์สัมพันธ์กันน้อยมาก (ข้อมูลน่าจะสังเคราะห์) ผลวิเคราะห์จึงไม่สะท้อนตลาดรถจริง

## ผลลัพธ์

- **Dashboard:** _[ใส่ลิงก์ Looker Studio ที่ตั้งเป็น "Anyone with the link can view"]_
- **ตารางใน PostgreSQL:**
  - `raw_data.car_data` ข้อมูลดิบ
  - `production.car_clean` ข้อมูลหลัง cleaning พร้อมคอลัมน์ใหม่ (`age`, `decade`, `mileage_bucket`, `price_segment`, `is_generic_model`, `price_per_1k_mileage`, `is_new`)
  - `production.agg_brand`, `agg_year`, `agg_mileage_bucket`, `agg_condition_brand`, `agg_color`, `agg_model`, `agg_price_segment` ตารางสรุปสำหรับ Dashboard
- **Google Sheets:** ตาราง `agg_*` ทั้ง 7 ตารางถูกส่งเป็น 7 tab (รวมประมาณ 1,000 cell) ส่วน `car_clean` ไม่ส่งขึ้น Sheets เพราะมี 1.5 ล้าน cell ซึ่งใหญ่เกินจำเป็นและใกล้เพดาน 10 ล้าน cell ของ Google

## โครงสร้างโฟลเดอร์

```
.
├── data/
│   └── Car_Data.csv          # ไฟล์ข้อมูลต้นฉบับ
├── docker-compose.yml        # PostgreSQL 16
├── ingest.py                 # CSV -> raw_data
├── transform.py              # raw_data -> production
├── publish.py                # production -> Google Sheets
├── run_pipeline.py           # รันทุกขั้นตอนต่อกัน
├── requirements.txt
├── .env.example              # ตัวอย่างการตั้งค่า (คัดลอกเป็น .env)
└── .gitignore                # กัน .env และ credentials.json
```

## สิ่งที่ต้องมี

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (หรือ Docker Engine + Compose)
- Python 3.10 ขึ้นไป
- บัญชี Google (สำหรับ Google Sheets และ Looker Studio)

## วิธีติดตั้งและรัน

### 1. เตรียมโปรเจกต์

```bash
git clone <URL ของ repository นี้>
cd <ชื่อโฟลเดอร์>

# แนะนำให้ใช้ virtual environment
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# macOS / Linux:       source .venv/bin/activate

pip install -r requirements.txt
```

ตรวจว่ามีไฟล์ `data/Car_Data.csv` (ถ้าไม่มี ให้ดาวน์โหลดจาก Kaggle แล้ววางไว้ที่ `data/`)

### 2. ตั้งค่า `.env`

คัดลอก `.env.example` เป็น `.env` แล้วแก้ค่า

```bash
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
```

| ตัวแปร | ความหมาย |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | ชื่อผู้ใช้ รหัสผ่าน และชื่อฐานข้อมูลของ PostgreSQL (ตั้งอะไรก็ได้ ใช้ร่วมกับ `docker-compose.yml`) |
| `POSTGRES_HOST`, `POSTGRES_PORT` | ปกติ `localhost` และ `5432` (ถ้าพอร์ต 5432 ถูกใช้อยู่ ให้เปลี่ยนเป็น `5433`) |
| `GOOGLE_SHEET_ID` | **เฉพาะ ID** ของ Google Sheet ที่ใช้ (ส่วนระหว่าง `/d/` กับ `/edit` ใน URL) ไม่ใช่ URL ทั้งเส้น |
| `GOOGLE_CREDENTIALS_FILE` | ชื่อไฟล์คีย์ของ Service Account ปกติ `credentials.json` |

### 3. ตั้งค่า Google API Credentials (ทำครั้งเดียว)

1. สร้าง Project ใน [Google Cloud Console](https://console.cloud.google.com)
2. ที่ **APIs & Services → Library** เปิดใช้ **Google Sheets API** และ **Google Drive API**
3. ที่ **APIs & Services → Credentials** สร้าง **Service Account**
4. เปิด Service Account นั้น แท็บ **Keys → Add Key → Create new key → JSON** แล้วเปลี่ยนชื่อไฟล์ที่ได้เป็น `credentials.json` วางไว้ที่โฟลเดอร์รากของโปรเจกต์
5. สร้าง Google Sheet เปล่า กด **Share** แล้วเพิ่มค่า `client_email` ในไฟล์ `credentials.json` เป็น **Editor**
6. คัดลอก Sheet ID ใส่ใน `.env`

> **ห้าม commit `credentials.json` และ `.env` ขึ้น GitHub** (อยู่ใน `.gitignore` แล้ว)

### 4. เปิดฐานข้อมูลและรัน pipeline

```bash
docker compose up -d          # เปิด PostgreSQL (รอจนสถานะเป็น healthy)
python run_pipeline.py        # ingest -> transform -> publish
```

ผลที่ควรเห็น (เวลารวมประมาณ 48 วินาที)

```
=== 1/3 Ingest   (CSV -> raw_data) ===
Done: raw_data.car_data has 100,000 rows
=== 2/3 Transform (raw_data -> production) ===
Wrote production.car_clean: 100,000 rows
... (agg_* อีก 7 ตาราง)
=== 3/3 Publish  (production -> Google Sheets) ===
Done: 7 tabs, 1,064 cells total
Pipeline completed in 48.3s
```

### 5. ตรวจผล

```bash
docker exec -it car_postgres psql -U <POSTGRES_USER> -d <POSTGRES_DB> -c "\dt production.*"
```

ควรเห็น 8 ตาราง และใน Google Sheet ควรมี 7 tab จากนั้นเชื่อม Looker Studio เข้ากับ Sheet นี้ (เลือก connector **Google Sheets** และเพิ่มทีละ tab)

### รันใหม่ตั้งแต่ศูนย์

```bash
docker compose down -v        # ลบ container และข้อมูลใน volume
docker compose up -d
python run_pipeline.py
```

ทุกขั้นตอนเขียนทับข้อมูลเดิม จึงรันซ้ำได้โดยข้อมูลไม่ซ้อนกัน

## แก้ปัญหาเบื้องต้น

| อาการ | สาเหตุและวิธีแก้ |
|---|---|
| `no configuration file provided: not found` | รัน `docker compose` ผิดโฟลเดอร์ ให้ `cd` เข้าโฟลเดอร์ที่มี `docker-compose.yml` |
| `connection refused` | PostgreSQL ยังไม่พร้อม รอให้ `docker compose ps` ขึ้น `healthy` แล้วรันใหม่ |
| พอร์ต 5432 ชน | เปลี่ยน `POSTGRES_PORT=5433` ใน `.env` |
| `SpreadsheetNotFound` (404) | `GOOGLE_SHEET_ID` ผิด (ต้องเป็น ID ล้วน) หรือยังไม่ได้แชร์ Sheet ให้ `client_email` เป็น Editor |
| `FileNotFoundError: credentials.json` | ไฟล์ไม่อยู่ในโฟลเดอร์ที่รัน หรือชื่อผิด (เช่น `credentials.json.json`) |
| `APIError 403` ที่ Google | ยังไม่ได้เปิดใช้ Sheets API หรือ Drive API |
| Dashboard กราฟว่างสำหรับผู้ชมคนอื่น | ในแหล่งข้อมูลของ Looker Studio ตั้ง Data credentials เป็น **Owner's credentials** |

## ข้อจำกัด

- ข้อมูลสังเคราะห์ จึงไม่ควรนำผลวิเคราะห์ไปใช้ประเมินราคารถจริง
- ยังไม่มีการตั้งเวลารันอัตโนมัติ (รัน `python run_pipeline.py` เองเมื่ออยากอัปเดต)
- รหัสผ่านใน `.env.example` เป็นค่าตัวอย่างสำหรับทดลองบนเครื่องตัวเองเท่านั้น
