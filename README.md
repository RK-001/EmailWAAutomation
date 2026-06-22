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
3. Approved message template with TEXT header and 4 body variables

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
- Your template has different number of variables than expected
- Ensure template body has exactly 4 variables: {{1}}, {{2}}, {{3}}, {{4}}

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

`NAME` is required. `EMAILID` is needed for email sending. `MOBILENO` is needed
for WhatsApp sending.

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
