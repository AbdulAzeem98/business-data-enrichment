# Business Data Enrichment Automation (Python + n8n)

A portfolio-ready MVP that reads company URLs from Google Sheets, calls a Python FastAPI service to scrape and enrich public website data, validates/normalizes the result, and writes it to a Google Sheets output tab. n8n orchestrates the process; custom business logic lives in Python. There are no JavaScript Code nodes.

## What works in this MVP

- FastAPI endpoints: `GET /health`, `POST /process`, `POST /normalize`.
- Preferred extraction: Firecrawl v2 API when `FIRECRAWL_API_KEY` is configured.
- Fallback extraction: Requests-compatible HTTP via `httpx` + BeautifulSoup for public, static HTML pages.
- Optional AI enrichment: OpenAI-compatible chat completions with JSON output.
- Deterministic fallback when no AI key is configured; the fallback deliberately flags records for review rather than claiming high confidence.
- URL normalization, public-destination checks, company-domain key, required-field validation, classification, review flags, and timestamps.
- n8n workflow export for Google Sheets → Python API → output upsert/error log.
- Separate starter Error Trigger → email notification workflow.
- Unit tests for URL cleaning, private-host rejection, whitespace normalization, and classification.

## Architecture

`Google Sheets (Input_Companies)` → `n8n` → `POST /process` → `Firecrawl or httpx/BeautifulSoup` → `OpenAI (optional)` → Python normalization/validation/classification → `Google Sheets (Processed_Companies)`.

The API returns a JSON object. `company_key` is the normalized domain without `www.`. The output sheet uses that column for an upsert. This is a useful MVP key, not a universal company identity: multi-domain companies and subsidiaries may need manual review.

## 1. Prerequisites (Windows)

Install:

- Python 3.11 or 3.12 from https://www.python.org/downloads/windows/ (check **Add Python to PATH**).
- Node.js LTS from https://nodejs.org/ (required for local n8n via npm).
- A Google account and a Google Sheet.
- Optional API keys: Firecrawl and OpenAI.

Open PowerShell and go to the folder where you extracted this project:

```powershell
cd C:\path\to\business-data-enrichment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, use a terminal session where scripts are allowed or run the venv executable directly: `\.venv\Scripts\python.exe -m pip install -r requirements.txt`.

Edit `.env` and set a long random `API_TOKEN`. Add API keys if available. Example values:

```dotenv
API_TOKEN=replace-with-a-long-random-token
FIRECRAWL_API_KEY=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
REQUEST_TIMEOUT_SECONDS=20
MAX_CONTENT_CHARS=24000
```

Keep `.env` and Google credential JSON out of Git and never share API keys in screenshots or workflow exports.

## 2. Run the Python API

In the activated PowerShell terminal:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Check the service in a browser: http://127.0.0.1:8000/health
Interactive API docs: http://127.0.0.1:8000/docs

Test the protected endpoint from a second PowerShell window (replace the token and URL):

```powershell
$headers = @{ Authorization = "Bearer replace-with-a-long-random-token" }
$body = @{ website_url = "https://example.com"; company_name = "Example" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/process -Headers $headers -ContentType "application/json" -Body $body
```

With no API keys, the API still runs. It uses static-page scraping and heuristic extraction and sets `review_status` to `Needs Review`. Add Firecrawl for more robust extraction, and OpenAI for semantic structured extraction. The `example.com` website is a connectivity smoke test, not representative of all sites.

## 3. Run tests

```powershell
pytest -q
```

Tests are intentionally deterministic where possible. DNS resolution behavior can vary by network; if a test involving public domains fails on a disconnected network, test normalization with a known public domain while online.

## 4. Create Google Sheets

Create a Google spreadsheet with these tabs and exact header rows.

### `Input_Companies`

```csv
company_name,website_url,status,attempts
Example Technologies,https://example.com,Pending,0
```

Set `status` to `Pending` for rows you want to process. Add only websites you are authorized to access and respect site terms, robots rules, rate limits, and applicable privacy/data-protection law.

### `Processed_Companies`

```csv
company_key,company_name,website,industry,description,products_services,location,public_contact,source_url,classification,missing_fields,review_status,processing_status,last_updated,extraction_method,error_message
```

### `Error_Log`

```csv
timestamp,company_key,website_url,workflow_step,error_message,attempts
```

`products_services` and `missing_fields` are stored as comma-separated strings in Sheets for easier reading.

## 5. Configure Google Sheets credentials in n8n

Start local n8n in another PowerShell terminal:

```powershell
npx n8n
```

Open http://localhost:5678 and complete the initial account setup. In n8n, create a Google Sheets OAuth2 credential and authorize the Google account that owns/has access to the spreadsheet. The workflow export contains placeholder credential IDs; choose your credential in each Google Sheets node after import.

For local n8n, use `http://127.0.0.1:8000/process` as the API URL. If you later move n8n into Docker, `127.0.0.1` points inside the container, not to the Windows host; use the appropriate host gateway/network address then.

## 6. Import the workflow

In n8n:

1. Select **Workflows → Import from File**.
2. Import `n8n/business_data_enrichment_workflow.json`.
3. Open each Google Sheets node, select your Google credential, and select the spreadsheet and correct tab. Replace `REPLACE_WITH_GOOGLE_SHEET_ID` with your spreadsheet ID if it remains in a field.
4. In **Process with Python API**, replace `REPLACE_WITH_API_TOKEN` with the same token as `.env`.
5. Ensure the HTTP Request node's **Include Response Headers and Status** / full-response option is enabled so the IF node can route based on `statusCode`.
6. Confirm the HTTP node's error handling is set to continue to the error branch for per-company failures.
7. Test with one row first, then a few rows. The workflow only processes rows with `status = Pending`.

The export is a starter and node labels/fields can differ slightly between n8n releases. After import, use the node UI to verify the Google Sheets operation names (`Get Row(s)` and `Append or Update Row`) and credential selections. This is expected when importing a portable workflow with placeholder IDs.

### Important response handling note

The API node returns a full HTTP response. Success data is under `$json.body`; failures may contain `$json.body.detail` or `$json.error`. The upsert uses `company_key`. A failure may not have a valid key; the Error_Log branch is where you should capture the original input URL. For production, consider adding a Merge node or an explicit error output to preserve the input row alongside HTTP errors.

## 7. API endpoints

### `GET /health`

Returns a simple service health response; no authentication required.

### `POST /process`

Requires `Authorization: Bearer <API_TOKEN>` when `API_TOKEN` is set.

Request:

```json
{
  "website_url": "https://example.com",
  "company_name": "Example Technologies",
  "classification_criteria": ["Software & IT", "Manufacturing", "Healthcare", "Financial Services", "Education", "Retail & E-commerce", "Professional Services", "Other"]
}
```

Returns fields including `company_key`, `company_name`, `website`, `industry`, `description`, `products_services`, `location`, `public_contact`, `source_url`, `classification`, `missing_fields`, `review_status`, `processing_status`, `last_updated`, and `extraction_method`.

### `POST /normalize`

Accepts `{ "record": { ... }, "classification_criteria": [...] }` and returns a cleaned record. Useful for testing or if extraction is handled elsewhere.

## 8. Error handling and retries

- The Python API returns a 502 response for scrape/extraction errors.
- Set retry behavior on the n8n HTTP Request node (for example, 2 retries with a short delay) for transient failures. Avoid retrying permanent 4xx failures repeatedly.
- The main workflow routes non-2xx API responses to the `Error_Log` sheet.
- Import `n8n/error_notification_workflow.json` separately, configure SMTP credentials and recipient, then activate it. The Error Trigger workflow catches workflow-level failures; the per-item error branch should log individual website failures.
- For a production workflow, add a step to update `Input_Companies.status` to `Processed`, `Review`, or `Failed`, and increment `attempts`. This starter reads pending rows but does not update the source status column yet.

## 9. Limitations and production hardening

- Requests/BeautifulSoup cannot reliably extract content rendered only by JavaScript. Use Firecrawl for those sites or add a browser-based scraper where allowed.
- The AI extraction is only as good as source content and model output; keep source URLs and review flags. Do not use guessed or inferred contact data as verified facts.
- Public contacts should be limited to relevant business information, and use should comply with applicable laws and website terms.
- Domain matching can merge unrelated entities or miss subsidiaries; add CRM IDs or human review for ambiguous matches.
- The included URL validation rejects obvious private/local destinations but is not a substitute for a hardened egress proxy, DNS-rebinding protections, strict domain allowlists, rate limiting, or production security review.
- API token auth is a simple local safeguard, not a complete public deployment security model. Do not expose the development server directly to the internet.
- Add persistent execution logs, monitoring, rate limiting, request budgets, and secret management before production use.

## 10. Suggested test cases

1. `GET /health` returns `status=ok`.
2. `/process` without token returns 401 when `API_TOKEN` is set.
3. A public static HTML site returns a record with `company_key` and source URL.
4. A site with missing description gets `Needs Review` and a `missing_fields` entry.
5. `localhost` and private IP targets are rejected.
6. Duplicate input domains resolve to the same `company_key` and update the existing output row.
7. An unreachable URL is logged in `Error_Log` without halting later items.
8. An AI response with missing fields is flagged for manual review.
9. An HTTP 429/5xx transient failure is retried a bounded number of times.
10. The error notification workflow sends a test email after a deliberate test failure.
