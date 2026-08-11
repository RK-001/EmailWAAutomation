# Bulk Notice Automation

Simple desktop app to generate legal notice PDFs from Excel and Word templates, then send them by Gmail and Meta WhatsApp Business API.

## Run From Source

Install requirements:

```powershell
py -3 -m pip install -r requirements.txt
```

Start the app:

```powershell
py -3 main.py
```

Microsoft Word must be installed for DOCX to PDF generation.

If you move this project to another computer, move only the source folder. Do
not move old `output`, `logs`, `__pycache__`, or build folders. Run the install
command again on the new system.

## First Setup

Open the `Setup` tab and fill:

- `Firm Name`
- `Lawyer Name`
- Gmail sender email and Gmail App Password
- Meta WhatsApp Phone Number ID, Access Token, and approved template name
- Google Drive OAuth or service account credentials and folder ID

Keep Meta WhatsApp and Google Drive mock mode ON while testing.

`config.json` is only a starter config. Enter real credentials on the new
system from the `Setup` tab.

## Gmail App Password

Use a Gmail App Password, not your normal Gmail password.

Steps:

1. Open [Google Account Security](https://myaccount.google.com/security)
2. Enable `2-Step Verification`
3. Open `App Passwords`
4. Create a new app password
5. Paste the 16-character password into the app

Spaces are okay. The app removes spaces automatically.

If Gmail test says authentication failed:

- Check that the sender email is spelled correctly, for example `name@gmail.com`
- Do not use your normal Gmail password
- Create a fresh App Password after enabling 2-Step Verification
- Paste only the 16-character App Password into the app

## Meta WhatsApp Business Setup

**IMPORTANT:** Meta WhatsApp requires pre-approved message templates. You cannot send arbitrary text messages. All messages must use approved templates.

### Prerequisites

1. Meta Business Manager account (business.facebook.com)
2. Verified WhatsApp Business phone number
3. Approved message template with the body variable count your profile expects

### Setup Steps

#### 1. Create WhatsApp Business App

1. Go to [Meta Business Manager](https://business.facebook.com)
2. Navigate to **Business Settings** → **Accounts** → **WhatsApp Accounts**
3. Click **Add** and follow the setup wizard
4. Add and verify your business phone number

#### 2. Get Phone Number ID

1. In WhatsApp Manager, go to **API Setup**
2. Find your phone number and copy the **Phone Number ID**
3. Save this ID — you'll need it in the app

#### 3. Create System User for Permanent Token

1. In Business Settings, go to **Users** → **System Users**
2. Click **Add** and create a new system user
3. Assign the system user to your WhatsApp Business Account with **Admin** role
4. Click **Generate New Token**
5. Select your WhatsApp Business App
6. Grant permissions: `whatsapp_business_messaging`, `whatsapp_business_management`
7. Set token to **Never expire**
8. Copy and save the token securely

**Note:** Temporary tokens expire in 24 hours. Always use a permanent token from a System User.

#### 4. Create and Submit Message Template

1. In WhatsApp Manager, go to **Message Templates**
2. Click **Create Template**
3. Fill template details:
   - **Category:** UTILITY (for transactional messages)
   - **Name:** `legal_notice_v1` (or your choice, lowercase with underscores)
   - **Language:** English

4. Configure template components:

   **HEADER:**
   - Type: **TEXT**
   - Text: `Legal Communication` (or your firm name)

   **BODY:**
   ```
   Dear {{1}}, an important communication regarding your account {{2}} has been shared with you. Please review: {{3}}. For queries: {{4}}.
   ```

   The body can also use fewer placeholders or none at all. Keep the profile's
   `wa_template_params` in the same order and count as the approved Meta
   template.

   **FOOTER (optional):**
   ```
   - [Your Firm Name]
   ```

   **BUTTONS (optional):** You can add a "Call Us" button if needed

5. Click **Submit** and wait for approval (typically 1-48 hours)
6. Once approved, copy the exact template name

### Template Variables

The app sends these values to the template body:

- `{{1}}` = Customer name (from NAME column)
- `{{2}}` = Account number (from ACCOUNTNO column)
- `{{3}}` = Google Drive PDF link (auto-generated after upload)
- `{{4}}` = Officer/contact phone number (from OFFICER_NO column)

The PDF link is sent as clickable text in the message body.
Indian mobile numbers in Excel can be stored as `9876543210`,
`919876543210`, `+919876543210`, or `09876543210`; the app normalizes them
before sending.

### Configure in the App

1. Open the **Setup** tab
2. Under **META WHATSAPP SETTINGS**:
   - Paste **Phone Number ID**
   - Paste **Access Token** (permanent token from System User)
   - Enter **Template Name** (exact name from approved template)
   - Keep **API Version** as `v21.0` (default)
   - Keep **Template Language** as `en` for English templates
   - Keep **Mock Mode** ON for testing

3. Click **Test Meta API** to verify credentials
4. If test passes, turn **Mock Mode OFF** when ready for production

### Troubleshooting

**Error: "Invalid OAuth access token"**
- Token expired (use permanent token from System User, not temporary)
- Token doesn't have required permissions
- Create new permanent token and try again

**Error: "Invalid Phone Number ID"**
- Check Phone Number ID is correct
- Ensure WhatsApp Business account is active

**Error: "Template not found"**
- Template not approved yet (wait for approval)
- Template name doesn't match exactly (check spelling/case)
- Template was rejected (check Meta dashboard for status)

**Error: "Template parameter count mismatch"**
- Your Meta template variable count does not match this profile's `wa_template_params`
- Keep `wa_template_params` in the same order and with the same count as the template body placeholders
- Use an empty `wa_template_params` list when the template body has no variables

If the test says Meta API cannot be reached, check internet/proxy access.
If it mentions SSL/certificate, install requirements again and ensure
`python-certifi-win32` is installed on Windows.

## Google Drive Setup

Personal Gmail / client-owned Drive is now supported through OAuth.

Recommended OAuth steps:

1. Open Google Cloud Console
2. Create or select a project
3. Enable `Google Drive API`
4. Configure OAuth consent for the client/user
5. Create an OAuth Client ID with application type `Desktop app`
6. Download the client JSON and place it in this project folder, usually as
   `oauth_credentials.json`
7. Create a folder in Google Drive for notice PDFs
8. Copy the folder ID from the Google Drive URL into the app
9. In the `Setup` tab, set Drive auth mode to `oauth_user`
10. Select the OAuth client JSON, keep token path as `token.json`, and click
    `Authorize / Test Drive`
11. Turn Google Drive mock mode OFF only after the Drive test passes

The first authorization opens a browser and saves `token.json`. Future uploads
reuse that token. Do not migrate or share `token.json`; authorize again on each
new machine.

Legacy service-account setup is still available by setting Drive auth mode to
`service_account`, selecting the service-account JSON, and sharing the Drive
folder with that service account as `Editor`.

## Amazon S3 Setup (Detailed)

Use this when specific bank profiles must upload PDF to Amazon instead of
Google Drive.

Important behavior:

- Profile `upload_provider = amazon_s3` means no Google upload is attempted.
- The generated outbound link field stays `drive_link` for compatibility.
- For Amazon profiles, `drive_link` contains the S3 URL.

### 1. Create AWS account

1. Open [AWS Signup](https://aws.amazon.com/)
2. Click `Create an AWS Account`
3. Enter account email, password, and AWS account name
4. Verify email with OTP
5. Choose account type (`Personal` or `Business`)
6. Enter billing details (card required by AWS)
7. Verify phone number with OTP
8. Select support plan: `Basic (Free)`
9. Sign in to AWS Console

### 2. Secure root user

1. In AWS Console, open `IAM` -> `Dashboard`
2. Enable MFA for root user
3. You can continue with root user for this setup as requested

### 3. Create S3 bucket

1. Open `S3` service
2. Click `Create bucket`
3. Bucket name: globally unique, lowercase, e.g. `gk-notice-bank-files-2026`
4. Region: choose your required region (example `ap-south-1`)
5. Keep default encryption enabled
6. Click `Create bucket`

### 4. Enable public-read delivery (for permanent clickable URLs)

This app currently sends permanent WhatsApp links.

1. Open your bucket -> `Permissions`
2. In `Block public access`, click `Edit`
3. Uncheck `Block all public access` and confirm
4. Save changes
5. In `Bucket policy`, add policy (replace bucket name):

```json
{
   "Version": "2012-10-17",
   "Statement": [
      {
         "Sid": "PublicReadForNoticeFiles",
         "Effect": "Allow",
         "Principal": "*",
         "Action": "s3:GetObject",
         "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/notices/*"
      }
   ]
}
```

### 5. Add root-level inline policy for S3 access

1. Open account menu (top-right) -> `Security credentials`
2. Scroll to `Root user` security controls
3. Open `Policies` / `Permissions` area for root account
4. Create or attach policy allowing this S3 scope
5. Use JSON policy (replace bucket name):

```json
{
   "Version": "2012-10-17",
   "Statement": [
      {
         "Effect": "Allow",
         "Action": ["s3:ListBucket"],
         "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME"
      },
      {
         "Effect": "Allow",
         "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
         "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/notices/*"
      }
   ]
}
```

1. Save policy

### 6. Create root access key

1. Open account menu (top-right) -> `Security credentials`
2. In `Access keys` (root account), click `Create access key`
3. Confirm warning and create key
4. Copy `Access key ID` and `Secret access key` securely
5. Store in password manager (shown only once)

### 7. Configure app Setup tab

In `Setup` -> `AMAZON S3 SETTINGS`:

1. Bucket Name
2. Region (e.g. `ap-south-1`)
3. Access Key ID
4. Secret Access Key
5. Folder Prefix (default `notices/`)
6. Keep S3 mock mode ON during first tests
7. Click `Test S3`
8. Turn S3 mock mode OFF after successful test

### 8. Enable Amazon only for selected banks

1. Open `Profiles` tab
2. Select bank profile
3. Set `Upload Provider` = `amazon_s3`
4. Save profile

Profiles with `google_drive` continue existing behavior.

### 9. Validate end-to-end behavior

1. Run small batch for one Amazon-enabled profile
2. In Preview tab, check provider label shows `amazon_s3`
3. Send one WhatsApp in mock/live as per your process
4. Confirm WhatsApp link opens S3 PDF
5. Confirm no Google upload warning appears for that batch

Note: Root access keys are high-risk. Rotate regularly and delete immediately if exposed.

Example folder URL:

```text
https://drive.google.com/drive/folders/1ABCxyz1234567890
```

Folder ID:

```text
1ABCxyz1234567890
```

## Create A Profile

Go to the `Profiles` tab.

Steps:

1. Click `New`
2. Enter profile key and display name
3. Select the Word `.docx` template
4. Click `Scan` if variables are not loaded automatically
5. The app reads variables written like `{{ VARIABLE }}`
6. Load a sample Excel file
7. Map each template variable to the correct Excel column
8. Save the profile

Mapping status:

- `Required` fields must be mapped before saving
- `Optional` fields may stay `-- not mapped --`
- Unmapped or blank optional values become `NA` in the generated notice
- If a value is constant, either put it directly in the Word template or add a
  repeated column in Excel and map it

The app fills these automatically if they exist in the Word template:

- `FIRM_NAME`
- `LAWYER_NAME`
- `NOTICE_DATE`

The app also shows these app fields:

- `NAME`
- `EMAILID`
- `MOBILENO`
- `ACCOUNTNO`
- `OFFICER_NO`

`NAME` is required. `EMAILID` is needed for email sending. `MOBILENO` is needed
for WhatsApp sending. `ACCOUNTNO` and `OFFICER_NO` are useful when your
WhatsApp template needs them even if your Word template does not.

## Word Template Rules

Use placeholders like:

```text
{{ NAME }}
{{ ACCOUNTNO }}
{{ AMOUNT }}
{{ NOTICE_DATE }}
```

Any blank mapped Excel value becomes `NA` in the generated notice.

## Daily Usage

Go to the `Workflow` tab.

Steps:

1. Select profile
2. Select Excel file
3. Check preview
4. Click `Generate All`
5. Review generated PDFs
6. Approve rows for sending
7. Send email and WhatsApp

## Build EXE On Another System

After testing from source:

```powershell
cmd /c build.bat
```

The packaged app will be created under:

```text
dist\NoticeAutomation\
```
