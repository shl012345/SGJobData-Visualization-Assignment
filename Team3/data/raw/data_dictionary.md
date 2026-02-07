# Data Dictionary: SGJobData.db

## Overview

`SGJobData.db` is a DuckDB database file containing cleaned and normalized Singapore job market data (Oct 2022 - May 2024). It is built from `SGJobData.csv` using the script `scripts/build_duckdb.py`.

**How to connect:**
```python
import duckdb
con = duckdb.connect('data/raw/SGJobData.db', read_only=True)
df = con.execute("SELECT * FROM jobs_enriched LIMIT 10").fetchdf()
```

**Rebuild the DB** (if CSV data changes):
```bash
python scripts/build_duckdb.py
```

---

## Table Relationships

```
SGJobData.csv (1,048,585 rows)
    │
    ▼ Clean: remove empty rows + placeholder salaries
    │
jobs_raw (1,042,793 rows x 22 cols)
    │  Original column names, raw data types
    │
    ▼ Normalize: rename columns, compute avg_salary, application_rate
    │
jobs_base (1,042,793 rows x 22 cols)
    │  Clean column names, computed fields
    │
    ▼ Enrich: add salary_band, experience_band, time dimensions
    │
jobs_enriched (1,042,793 rows x 29 cols)    ← Primary table for most queries
    │
    ▼ Flatten: explode JSON categories array
    │
jobs_categories (1,764,956 rows x 14 cols)  ← One row per job-category pair
```

---

## Table 1: `jobs_raw`

**Purpose:** Cleaned raw data with original column names. Use this only if you need access to fields not carried forward to `jobs_base`.

**Cleaning applied:**
- Removed 3,988 completely empty rows (NULL `metadata_jobPostId`)
- Removed 1,804 placeholder salary rows (`salary_minimum = 1 AND salary_maximum = 1 AND average_salary = 1`)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `categories` | VARCHAR | JSON array of job categories | `[{"id":21,"category":"Information Technology"}]` |
| `employmentTypes` | VARCHAR | Employment type | `Permanent`, `Full Time`, `Contract` |
| `metadata_expiryDate` | DATE | Job posting expiry date | `2023-05-08` |
| `metadata_isPostedOnBehalf` | BOOLEAN | Whether posted by a recruiter/agency | `true`, `false` |
| `metadata_jobPostId` | VARCHAR | Unique job posting identifier (primary key) | `MCF-2023-0273977` |
| `metadata_newPostingDate` | DATE | Most recent posting/reposting date | `2023-04-08` |
| `metadata_originalPostingDate` | DATE | Original first posting date | `2023-04-08` |
| `metadata_repostCount` | BIGINT | Number of times reposted | `0`, `2`, `5` |
| `metadata_totalNumberJobApplication` | BIGINT | Total applications received | `0`, `6`, `150` |
| `metadata_totalNumberOfView` | BIGINT | Total views/impressions | `0`, `113`, `5000` |
| `minimumYearsExperience` | BIGINT | Minimum years of experience required | `0`, `3`, `10` |
| `numberOfVacancies` | BIGINT | Number of open positions | `1`, `5` |
| `occupationId` | VARCHAR | Occupation ID (100% NULL - unusable) | `None` |
| `positionLevels` | VARCHAR | Position seniority level | `Executive`, `Senior Executive` |
| `postedCompany_name` | VARCHAR | Company name | `DBS BANK LTD.` |
| `salary_maximum` | BIGINT | Maximum monthly salary (SGD) | `6500` |
| `salary_minimum` | BIGINT | Minimum monthly salary (SGD) | `4000` |
| `salary_type` | VARCHAR | Salary period (always "Monthly") | `Monthly` |
| `status_id` | BIGINT | Job status code | `0` |
| `status_jobStatus` | VARCHAR | Job status | `Open`, `Closed`, `Re-open` |
| `title` | VARCHAR | Job title | `Senior Software Engineer` |
| `average_salary` | DOUBLE | Pre-computed average salary | `5250.0` |

---

## Table 2: `jobs_base`

**Purpose:** Normalized version of `jobs_raw` with clean column names and computed fields. Use this when you need the full dataset with readable column names.

| Column | Type | Source / Calculation | Description |
|--------|------|---------------------|-------------|
| `job_id` | VARCHAR | `metadata_jobPostId` | Unique job identifier (primary key) |
| `title` | VARCHAR | `title` | Job title |
| `company_name` | VARCHAR | `postedCompany_name` | Company name |
| `position_level` | VARCHAR | `positionLevels` | Seniority level (see values below) |
| `employment_type` | VARCHAR | `employmentTypes` | Employment type (see values below) |
| `salary_minimum` | BIGINT | `salary_minimum` | Min monthly salary (SGD) |
| `salary_maximum` | BIGINT | `salary_maximum` | Max monthly salary (SGD) |
| `salary_type` | VARCHAR | `salary_type` | Always "Monthly" |
| `avg_salary` | DOUBLE | `(min + max) / 2` or fallback to `average_salary` | Computed average salary |
| `salary_range` | BIGINT | `salary_maximum - salary_minimum` | Salary band width |
| `min_experience` | BIGINT | `minimumYearsExperience` | Required years of experience |
| `vacancies` | BIGINT | `numberOfVacancies` | Number of open positions |
| `job_status` | VARCHAR | `status_jobStatus` | Job status |
| `posting_date` | DATE | `metadata_originalPostingDate` | Original posting date |
| `new_posting_date` | DATE | `metadata_newPostingDate` | Latest reposting date |
| `expiry_date` | DATE | `metadata_expiryDate` | Posting expiry date |
| `applications` | BIGINT | `metadata_totalNumberJobApplication` | Total applications |
| `views` | BIGINT | `metadata_totalNumberOfView` | Total views |
| `application_rate` | FLOAT | `applications / views` (NULL if views = 0) | Application conversion rate |
| `repost_count` | BIGINT | `metadata_repostCount` | Times reposted |
| `is_posted_on_behalf` | BOOLEAN | `metadata_isPostedOnBehalf` | Recruiter posting flag |
| `categories` | VARCHAR | `categories` | Raw JSON categories string |

---

## Table 3: `jobs_enriched`

**Purpose:** The primary analysis table. Extends `jobs_base` with salary bands, experience bands, and time dimensions. **Use this table for most Streamlit charts and queries.**

Includes all 22 columns from `jobs_base`, plus these 7 derived columns:

| Column | Type | Calculation | Description |
|--------|------|-------------|-------------|
| `salary_band` | VARCHAR | Binned from `avg_salary` | Salary category (see values below) |
| `experience_band` | VARCHAR | Binned from `min_experience` | Experience category (see values below) |
| `posting_year` | BIGINT | `EXTRACT(YEAR FROM posting_date)` | Year of posting (2022-2024) |
| `posting_month` | BIGINT | `EXTRACT(MONTH FROM posting_date)` | Month of posting (1-12) |
| `posting_quarter` | BIGINT | `EXTRACT(QUARTER FROM posting_date)` | Quarter of posting (1-4) |
| `posting_day_of_week` | BIGINT | `EXTRACT(DOW FROM posting_date)` | Day of week (0=Sunday, 6=Saturday) |
| `days_active` | BIGINT | `expiry_date - posting_date` | Number of days posting was active |

### Categorical Value Reference

**`salary_band`** (6 values):

| Value | Range (SGD/month) | Typical Count |
|-------|-------------------|---------------|
| `< 3K` | $0 - $2,999 | ~269K |
| `3K - 5K` | $3,000 - $4,999 | ~457K |
| `5K - 8K` | $5,000 - $7,999 | ~194K |
| `8K - 12K` | $8,000 - $11,999 | ~88K |
| `12K - 20K` | $12,000 - $19,999 | ~30K |
| `20K+` | $20,000+ | ~5K |

**`experience_band`** (4 values):

| Value | Range | Typical Count |
|-------|-------|---------------|
| `Entry (0-2 years)` | 0-2 years | ~575K |
| `Mid (3-5 years)` | 3-5 years | ~310K |
| `Senior (6-10 years)` | 6-10 years | ~120K |
| `Executive (10+ years)` | 10+ years | ~38K |

**`position_level`** (9 values):
`Executive`, `Fresh/entry level`, `Junior Executive`, `Manager`, `Middle Management`, `Non-executive`, `Professional`, `Senior Executive`, `Senior Management`

**`employment_type`** (8 values):
`Contract`, `Flexi-work`, `Freelance`, `Full Time`, `Internship/Attachment`, `Part Time`, `Permanent`, `Temporary`

**`job_status`** (3 values):
`Open` (86.4%), `Closed` (11.5%), `Re-open` (2.1%)

---

## Table 4: `jobs_categories`

**Purpose:** Flattened version of the JSON `categories` field. Each row represents one job-category pair. A job with 3 categories appears as 3 rows. **Use this table for category-based analysis.**

**Row count:** ~1.76M (average 1.7 categories per job)

| Column | Type | Description |
|--------|------|-------------|
| `job_id` | VARCHAR | Job identifier (join key to `jobs_enriched`) |
| `title` | VARCHAR | Job title |
| `company_name` | VARCHAR | Company name |
| `category_id` | INTEGER | Category numeric ID |
| `category_name` | VARCHAR | Category display name (see values below) |
| `salary_minimum` | BIGINT | Min monthly salary (SGD) |
| `salary_maximum` | BIGINT | Max monthly salary (SGD) |
| `avg_salary` | DOUBLE | Average salary |
| `posting_date` | DATE | Original posting date |
| `job_status` | VARCHAR | Job status |
| `min_experience` | BIGINT | Required years of experience |
| `vacancies` | BIGINT | Number of open positions |
| `experience_band` | VARCHAR | Experience category |
| `salary_band` | VARCHAR | Salary category |

**`category_name`** (30 values):
`Accounting / Auditing / Taxation`, `Admin / Secretarial`, `Advertising / Media`, `Arts / Design / Fashion`, `Banking and Finance`, `Building and Construction`, `Customer Service`, `Education and Training`, `Engineering`, `Entertainment`, `Environment / Health`, `Events / Promotions`, `F&B`, `General Management`, `General Work`, `Healthcare / Pharmaceutical`, `Hospitality`, `Human Resources`, `Information Technology`, `Insurance`, `Legal`, `Logistics / Supply Chain`, `Manufacturing`, `Marketing / Public Relations`, `Medical / Therapy Services`, `Others`, `Personal Care / Beauty`, `Professional Services`, `Public / Civil Service`, `Purchasing / Merchandising`, `Real Estate / Property Management`, `Repair and Maintenance`, `Risk Management`, `Sales / Retail`, `Sciences / Laboratory / R&D`, `Security and Investigation`, `Social Services`, `Telecommunications`, `Travel / Tourism`

---

## Common Query Examples

### Salary analysis by category
```sql
SELECT
    category_name,
    COUNT(*) as job_count,
    ROUND(AVG(avg_salary), 0) as mean_salary,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY avg_salary), 0) as median_salary
FROM jobs_categories
WHERE avg_salary > 0 AND avg_salary < 50000
GROUP BY category_name
ORDER BY mean_salary DESC
```

### Monthly posting trends
```sql
SELECT
    posting_year, posting_month,
    COUNT(*) as job_count,
    ROUND(AVG(avg_salary), 0) as avg_salary
FROM jobs_enriched
GROUP BY posting_year, posting_month
ORDER BY posting_year, posting_month
```

### Top companies by posting volume
```sql
SELECT
    company_name,
    COUNT(*) as job_count,
    ROUND(AVG(avg_salary), 0) as avg_salary
FROM jobs_enriched
GROUP BY company_name
ORDER BY job_count DESC
LIMIT 20
```

### Filter by category + experience band
```sql
SELECT je.*
FROM jobs_enriched je
JOIN jobs_categories jc ON je.job_id = jc.job_id
WHERE jc.category_name = 'Information Technology'
  AND je.experience_band = 'Mid (3-5 years)'
  AND je.avg_salary < 50000
```

### Application rate by salary band
```sql
SELECT
    salary_band,
    COUNT(*) as jobs,
    ROUND(AVG(application_rate) * 100, 2) as avg_app_rate_pct
FROM jobs_enriched
WHERE application_rate IS NOT NULL
GROUP BY salary_band
ORDER BY
    CASE salary_band
        WHEN '< 3K' THEN 1
        WHEN '3K - 5K' THEN 2
        WHEN '5K - 8K' THEN 3
        WHEN '8K - 12K' THEN 4
        WHEN '12K - 20K' THEN 5
        WHEN '20K+' THEN 6
    END
```

---

## Data Quality Notes

- **Salary outliers:** Use `avg_salary < 50000` to cap extreme outliers (retains 99%+ of data)
- **Zero views/applications:** Valid for newly posted jobs — do not remove
- **`occupationId`:** 100% NULL in the source data — not included in normalized tables
- **`salary_type`:** Always "Monthly" — no conversion needed
- **Date range:** October 3, 2022 to May 29, 2024 (604 days)
- **`posting_day_of_week`:** DuckDB convention — 0 = Sunday, 6 = Saturday

---

**Source:** `data/raw/SGJobData.csv` (1,048,585 rows)
**Built with:** `scripts/build_duckdb.py`
**Last updated:** 2025
