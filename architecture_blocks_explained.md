# Dealer Insurance Tracking — Architecture Blocks Explained

**To-Be Architecture (AWS GenAI Powered)**

---

## Flow Overview

```
Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Step 6 → Step 7 → Step 8 → Step 9a/9b → Step 10 → Step 11a/11b/11c
```

Solid lines = synchronous data flow | Dashed lines = async / event-driven notifications

---

## Layer 1 — Dealers (Purple)

### Block: Dealer Submits COI
- **Step:** 1
- **What it does:** Entry point of the entire workflow. A dealer uploads their Certificate of Insurance (COI) document.
- **How:** Via Docutrax portal (web upload), email attachment, or SFTP drop.
- **Document types:** PDF, scanned image (JPG/PNG), or digital form.
- **Example:**
  > ABC Motors has a $1.2M floor plan loan. Before renewal, the TFS credit team requires updated proof of General Liability and Dealer Open Lot insurance. The dealer's operations manager logs into Docutrax and uploads `ABC_Motors_COI_2026.pdf`.

---

## Layer 2 — Document Ingestion & AI Extraction Layer (Light Blue)

### Block: Document Intake
- **Step:** 2
- **What it does:** Receives the COI document from the dealer submission channel and passes it into the processing pipeline.
- **How:** API Webhook (Docutrax sends a POST request), SFTP listener (picks up files from a shared folder), or Email listener (monitors a dedicated inbox).
- **Example:**
  > Docutrax calls `POST /api/coi/upload` with the PDF file. A Lambda function receives this webhook, validates the file type, and stores it in S3.

---

### Block: Document Store — Amazon S3
- **Step:** 3
- **What it does:** Stores the raw, unprocessed COI PDF or image files securely.
- **Why S3:** Durable (99.999999999% durability), cheap, supports versioning, and integrates natively with Textract and Lambda.
- **Folder structure example:**
  ```
  s3://dealer-insurance-bucket/
    raw/
      2026/04/17/
        ABC_Motors_COI_2026.pdf
        XYZ_Auto_COI_2026.jpg
  ```

---

### Block: Amazon Textract
- **Step:** 4
- **What it does:** AWS managed OCR service. Reads the PDF/image and extracts raw text, form fields, and key-value pairs (e.g., `Policy Number: POL-9982`).
- **Why not just OCR:** Textract understands document *layout* — it knows a value belongs to a field label even in complex multi-column insurance forms.
- **Example output:**
  ```json
  {
    "Policy Number": "POL-9982",
    "Insured": "ABC Motors Inc.",
    "Effective Date": "01/01/2026",
    "Expiration Date": "12/31/2026",
    "General Liability Limit": "$1,000,000"
  }
  ```

---

### Block: GenAI — Amazon Bedrock (Extraction)
- **Step:** 5 (Arrow 4 → 5)
- **What it does:** Sends the Textract raw output to Claude LLM via Amazon Bedrock. The LLM intelligently extracts and normalizes the key insurance fields — handling variations in formatting, abbreviations, and layouts across different insurers.
- **Why GenAI here:** Insurance COIs vary wildly by insurer format. A rule-based extractor would need hundreds of templates. The LLM understands context and extracts correctly regardless of format.
- **Example prompt sent to Bedrock:**
  > "Extract the following fields from this insurance certificate text: coverage type, per-occurrence limit, aggregate limit, policy number, effective date, expiry date, insurer name. Return as JSON."
- **Example Bedrock output:**
  ```json
  {
    "coverage_type": "General Liability",
    "per_occurrence_limit": 1000000,
    "aggregate_limit": 2000000,
    "policy_number": "POL-9982",
    "effective_date": "2026-01-01",
    "expiry_date": "2026-12-31",
    "insurer": "Hartford Insurance"
  }
  ```

---

### Block: Structured COI Record — Amazon DynamoDB
- **Step:** 5 (output stored)
- **What it does:** Saves the clean, structured JSON COI record into DynamoDB for fast downstream processing.
- **Why DynamoDB:** NoSQL, millisecond reads/writes, no schema needed — perfect for storing varying COI JSON structures per dealer.
- **Example DynamoDB item:**
  ```json
  {
    "dealer_id": "D001",
    "coi_id": "COI-20260417-001",
    "coverage_type": "General Liability",
    "limit": 1000000,
    "expiry_date": "2026-12-31",
    "status": "pending_review",
    "uploaded_at": "2026-04-17T10:30:00Z"
  }
  ```

---

## Layer 3 — Core Intelligence & Gap Analysis Layer / GenAI (Green)

### Block: Loan Amount Feed
- **Step:** 7
- **What it does:** Provides the current outstanding loan balance for the dealer from the Core Banking System. This is the key input for determining how much insurance coverage is *required*.
- **How:** Daily batch sync or real-time API call. Uses 12-month average balance for stable threshold calculation.
- **Example:**
  > Dealer ABC Motors has a current floor plan balance of $1,200,000. The system rule says: loan > $1M → minimum GL coverage = $2,000,000. The feed delivers this `$1,200,000` figure to the gap analysis agent.

---

### Block: GenAI — Gap Analysis Agent (Amazon Bedrock)
- **Step:** 6 + 7 → 8
- **What it does:** The core intelligence of the system. The LLM receives both the extracted COI data (step 6) and the loan amount (step 7), then determines:
  - Is coverage sufficient for the loan amount?
  - Is the policy expired or expiring soon?
  - Are any required coverage types missing entirely?
  - What is the gap amount if underinsured?
- **Flags produced:** `OK` / `GAP` / `EXPIRED` / `MISSING`
- **Example analysis:**
  > Loan = $1,200,000 → Required GL = $2,000,000 | Actual GL = $1,000,000 → **GAP: $1,000,000 underinsured**
  > Expiry = 2026-12-31 → 258 days remaining → **OK (not expiring soon)**

---

### Block: RAG — Policy Knowledge Base (Amazon OpenSearch)
- **Dashed arrow** (reference lookup, not pipeline step)
- **What it does:** A vector database containing insurance policy rules, regulatory requirements, and historical decisions. The Gap Analysis Agent queries this before making a decision — so it's grounded in your *actual* rules, not just general LLM knowledge.
- **Contents example:**
  - "For dealers with loans > $500K, minimum GL per occurrence = $1M, aggregate = $2M"
  - "Dealer Open Lot required for inventory > 50 vehicles"
  - "Policies expiring within 30 days trigger pre-expiry alert"
- **Why RAG:** Without it, the LLM would guess at thresholds. With it, the LLM retrieves the exact rule and applies it accurately.

---

### Block: Gap Detected? (Decision Diamond)
- **Step:** 8 → 9a / 9b
- **What it does:** A routing decision based on the Gap Analysis Agent output.
  - **9a — No Gap:** Dealer is fully compliant → record marked OK, next review scheduled.
  - **9b — Gap Found:** Coverage is insufficient, expired, or missing → automated workflow triggered.

---

### Block: Compliant ✓
- **Step:** 9a
- **What it does:** Updates the dealer's record as compliant. Schedules the next review date (e.g., 30 days before policy expiry or next quarterly check).
- **Example:** ABC Motors GL is $2.5M against required $2M → Compliant. Next review: 2026-12-01 (30 days before expiry).

---

### Block: Trigger Automated Workflow — AWS Step Functions / EventBridge
- **Step:** 9b → 10
- **What it does:** When a gap is found, this block fires the automated response workflow. Step Functions orchestrates the sequence; EventBridge routes the gap event to the notification layer.
- **Example:** Gap detected for ABC Motors → EventBridge rule fires → Step Functions starts execution → calls Bedrock Notification Writer → sends alerts in parallel.

---

## Layer 4 — Notification & Workflow Automation Layer (Yellow)

### Block: GenAI — Notification Writer (Amazon Bedrock)
- **Step:** 10 → 11a/11b/11c
- **What it does:** Instead of sending a generic template alert, Bedrock (Claude) generates a personalized, human-readable message explaining the specific gap, its impact, and what the dealer needs to do.
- **Example generated email:**
  > "Dear ABC Motors Team, our review of your Certificate of Insurance dated 17 April 2026 has identified a coverage gap. Your current General Liability limit is $1,000,000, however your outstanding floor plan balance of $1,200,000 requires a minimum limit of $2,000,000. Please contact your insurer to increase your coverage and upload the updated COI via the link below within 10 business days."

---

### Block: TFS CL Team Alert *(dashed — async)*
- **Step:** 11a
- **What it does:** Notifies the internal TFS Credit/Lending team about the gap. Sent via email or Microsoft Teams. Includes the full gap report and a recommended action (e.g., freeze credit line, request updated COI).
- **Example Teams message:**
  > ⚠️ Gap Alert — ABC Motors (D001) | GL underinsured by $1M | Loan: $1.2M | Action: Request updated COI within 10 days.

---

### Block: Dealer Alert *(dashed — async)*
- **Step:** 11b
- **What it does:** Sends the personalized gap notification directly to the dealer via email and/or SMS. Includes an upload link so the dealer can immediately submit the corrected COI.
- **Example SMS:**
  > "TFS Insurance Alert: Your GL coverage is below the required limit for your current loan. Please upload updated COI at: [link]. Deadline: 30 Apr 2026."

---

### Block: Case Created *(dashed — async)*
- **Step:** 11c
- **What it does:** Auto-creates a tracked ticket in CRM or ServiceNow, assigned to an underwriter for formal follow-up. Ensures the gap doesn't get forgotten if the dealer doesn't respond to the alert.
- **Example ServiceNow ticket:**
  ```
  Title:    COI Gap — ABC Motors (D001)
  Priority: High
  Assigned: Underwriting Team
  Due Date: 30 Apr 2026
  Status:   Open
  Details:  GL gap $1M. Alert sent to dealer 17 Apr 2026. Awaiting updated COI.
  ```

---

## Layer 5 — Monitoring, Audit & Dashboard Layer (Pink)

### Block: Central Insurance DB — Amazon Aurora RDS
- **What it does:** The persistent, relational SQL database that stores all dealer COI records, gap history, notification logs, and compliance status over time. Source of truth for reporting and audit.
- **Tables:**

  | Table | Contents |
  |---|---|
  | `dealer` | Dealer profile, tier, risk class, loan amount |
  | `coi_record` | Extracted policy fields per submission |
  | `gap_analysis` | Gap decisions, required vs actual limits |
  | `notification_log` | Who was notified, when, which channel |

- **Example query (QuickSight uses this):**
  ```sql
  SELECT dealer_name, gap_type, required_limit, actual_limit, detected_at
  FROM gap_analysis g
  JOIN dealer d ON g.dealer_id = d.dealer_id
  WHERE status = 'GAP'
  ORDER BY detected_at DESC;
  ```

---

### Block: Amazon QuickSight
- **What it does:** BI dashboard that queries Aurora RDS and displays live visual reports for the TFS management team and credit officers.
- **Dashboards shown:**
  - Coverage status heatmap across all dealers
  - Gap trend over last 12 months
  - Expiry calendar (which COIs expire in next 30/60/90 days)
  - Compliance % by dealer tier / region
- **Example:** Management opens QuickSight on Monday morning and sees: 42 dealers active, 8 with gaps, 5 policies expiring in 30 days — all without manually checking any files.

---

### Block: Audit Trail — AWS CloudWatch / CloudTrail
- **What it does:** Automatically captures an immutable log of every event across all layers — AI decisions, file extractions, notifications sent, user logins, API calls. No arrow feeds into it; it listens to all layers passively.
- **Why important:** Regulatory compliance requires proof of *who decided what and when*. If a dealer disputes a gap finding, the audit log shows exactly what the AI extracted, what decision was made, and when the alert was sent.
- **Example log entry (CloudWatch):**
  ```
  2026-04-17T10:32:14Z | dealer_id=D001 | action=GAP_DETECTED |
  coverage=GL | required=2000000 | actual=1000000 |
  bedrock_model=claude-3-sonnet | confidence=0.97
  ```

---

### Block: GenAI — Portfolio Summary (Amazon Bedrock)
- **Dashed arrow** (scheduled async job)
- **What it does:** Every week, a scheduled Lambda triggers Bedrock to read the Aurora database and generate a narrative executive summary report — surfacing top risks, trends, and recommended actions in plain language.
- **Example output:**
  > "Weekly Insurance Portfolio Summary — 17 Apr 2026:
  > Total active dealers: 142 | Compliant: 134 (94%) | With gaps: 8 (6%)
  > Top risk: 3 dealers with expired GL coverage, combined loan exposure $4.2M.
  > Recommended actions: Immediate outreach to ABC Motors, XYZ Auto, Delta Cars.
  > Expiring in 30 days: 12 policies requiring renewal follow-up."

---

## Possible Insurance Gaps

These are the gap types the **GenAI Gap Analysis Agent** detects and flags:

---

### 1. Underinsured — Coverage Limit Too Low
- **What it is:** The dealer has coverage but the limit is below the required threshold based on their loan amount.
- **Example:**
  > ABC Motors loan = $1,200,000 → Required GL = $2,000,000 | Actual GL = $1,000,000
  > **Gap: $1,000,000 underinsured**
- **Flag:** `GAP`
- **Risk:** If a liability claim occurs, TFS is exposed for the uncovered $1M.

---

### 2. Expired Policy
- **What it is:** The COI expiry date has passed. The dealer has no active coverage.
- **Example:**
  > XYZ Auto submitted a COI with expiry date 31 Mar 2026. Today is 17 Apr 2026.
  > **Gap: Policy expired 17 days ago — no active coverage**
- **Flag:** `EXPIRED`
- **Risk:** Any loss during the gap period is fully uninsured. Loan is technically in breach.

---

### 3. Expiring Soon — Pre-Expiry Warning
- **What it is:** The policy is still active but expires within the warning threshold (e.g., 30 days). Not a gap yet but requires proactive follow-up.
- **Example:**
  > Delta Cars COI expires 15 May 2026. Today is 17 Apr 2026 → 28 days remaining.
  > **Warning: Policy expiring in 28 days**
- **Flag:** `EXPIRING_SOON`
- **Risk:** If renewal is delayed, coverage lapses and becomes an `EXPIRED` gap.

---

### 4. Missing Coverage Type
- **What it is:** A required coverage type is completely absent from the submitted COI. The dealer may have one type of insurance but not all required types.
- **Required types (typical):**

  | Coverage Type | Purpose |
  |---|---|
  | General Liability (GL) | Bodily injury / property damage claims |
  | Dealer Open Lot (DOL) | Physical damage to vehicle inventory |
  | Garage Keepers Liability | Customer vehicles in dealer's care |
  | Workers Compensation | Employee injury coverage |
  | Umbrella / Excess Liability | Additional protection above GL limits |

- **Example:**
  > ABC Motors submitted COI with GL and DOL only. Garage Keepers Liability is missing.
  > **Gap: Garage Keepers Liability not found in COI**
- **Flag:** `MISSING`
- **Risk:** If a customer's car is damaged while in the service bay, TFS has no coverage backing.

---

### 5. Wrong Insured Name / TFS Not Listed as Additional Insured
- **What it is:** The COI names the wrong entity, or TFS (Toyota Financial Services) is not listed as an **Additional Insured** or **Loss Payee** — meaning TFS cannot file a claim directly.
- **Example:**
  > COI shows insured as "ABC Motors LLC" but the loan agreement is under "ABC Motors Inc."
  > OR: TFS/TFS CL is not listed as Additional Insured.
  > **Gap: Entity mismatch / TFS not named as Additional Insured**
- **Flag:** `MISSING` (entity) or `GAP` (AI insured)
- **Risk:** In a claim, TFS may have no legal standing to recover losses.

---

### 6. Coverage Amount Below Loan-to-Value Requirement
- **What it is:** The Dealer Open Lot (inventory) coverage is less than the current inventory value or outstanding floorplan balance.
- **Example:**
  > Dealer's lot inventory value = $3,000,000 | DOL coverage = $1,500,000
  > **Gap: DOL covers only 50% of inventory value**
- **Flag:** `GAP`
- **Risk:** A total lot loss (fire, flood, theft) would leave $1.5M unrecovered.

---

### 7. Coverage Effective Date Not Yet Reached
- **What it is:** The dealer submitted a COI for a future policy — it is not yet active on the date of review.
- **Example:**
  > Today = 17 Apr 2026 | Policy effective date = 01 May 2026
  > **Gap: Coverage not yet active — 14 day gap**
- **Flag:** `GAP`
- **Risk:** No coverage is in force during the gap window between old expiry and new effective date.

---

### 8. Duplicate / Stale Submission
- **What it is:** The dealer re-submits a COI that is identical to one already on file (same policy number, same dates). No new information.
- **Example:**
  > COI policy number POL-9982 already exists in the system with identical dates and limits.
  > **Flag: Duplicate submission — no update detected**
- **Flag:** `DUPLICATE`
- **Action:** Alert team that dealer may have submitted the wrong document.

---

### Gap Summary Table

| Gap Type | Flag | Trigger Condition | Action |
|---|---|---|---|
| Underinsured | `GAP` | Actual limit < Required limit | Alert dealer + TFS team |
| Expired Policy | `EXPIRED` | Expiry date < Today | Immediate alert + case created |
| Expiring Soon | `EXPIRING_SOON` | Expiry date within 30 days | Pre-expiry warning to dealer |
| Missing Coverage | `MISSING` | Required coverage type not found | Alert dealer to add coverage |
| Entity Mismatch | `MISSING` | Wrong insured name / TFS not AI | Legal/underwriting review |
| DOL Below Inventory | `GAP` | DOL < floorplan balance | Alert + escalate to credit team |
| Future Effective Date | `GAP` | Effective date > Today | Alert — no current coverage |
| Duplicate Submission | `DUPLICATE` | Same policy already on file | Notify dealer to resubmit |

---

## Connection Types Summary

| Line Style | Meaning | Example |
|---|---|---|
| **Solid arrow** | Synchronous data flow — one step directly feeds the next | S3 → Textract → Bedrock |
| **Dashed arrow** | Async / event-driven — fire and forget | Notification Writer → Dealer Alert |
| **Numbered label** | Step sequence in the end-to-end flow | `1`, `2`, `3` ... `11c` |

---

## AWS Services Used

| Service | Role |
|---|---|
| Amazon S3 | Raw document storage |
| Amazon Textract | OCR and form data extraction |
| Amazon Bedrock (Claude) | LLM extraction, gap analysis, notification writing, portfolio summary |
| Amazon DynamoDB | Fast operational JSON record store |
| Amazon OpenSearch | RAG vector knowledge base |
| AWS Step Functions | Workflow orchestration |
| Amazon EventBridge | Event routing between layers |
| Amazon Aurora RDS | Relational SQL database for reporting |
| Amazon QuickSight | BI dashboards |
| AWS CloudWatch / CloudTrail | Audit logging and monitoring |
