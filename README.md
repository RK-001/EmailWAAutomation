# Bulk Notice Automation

Simple desktop app to generate legal notice PDFs from Excel and Word templates, then send them by Gmail and AiSensy WhatsApp.

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
- AiSensy API key and approved template name
- Google Drive service account JSON path and folder ID

Keep AiSensy and Google Drive mock mode ON while testing.

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

## AiSensy Setup

Steps:

1. Log in to AiSensy
2. Open `Manage > API Keys`
3. Copy the live API key into the app
4. Open `Manage > Template Messages`
5. Create a Utility template and submit it for approval
6. Copy the exact approved template name into the app
7. Turn mock mode OFF only when you are ready to send real WhatsApp messages

Suggested WhatsApp template body:

```text
Dear {{1}}, an important communication regarding your account {{2}} has been shared with you. Please review: {{3}}. For queries: {{4}}.
```

The app sends:

- `{{1}}` = customer name
- `{{2}}` = account number
- `{{3}}` = Google Drive PDF link
- `{{4}}` = officer/contact number

If the test says AiSensy cannot be reached, first check internet/proxy access.
If it mentions SSL/certificate, install requirements again and make sure
`python-certifi-win32` is installed on Windows.

## Google Drive Setup

Steps:

1. Open Google Cloud Console
2. Create or select a project
3. Enable `Google Drive API`
4. Create a Service Account
5. Create a JSON key for that service account
6. Put the JSON file in this project folder, usually as `drive_credentials.json`
7. Create a folder in Google Drive for notice PDFs
8. Share that folder with the service account email as `Editor`
9. Copy the folder ID from the Google Drive URL into the app
10. Turn Google Drive mock mode OFF only after the folder is shared correctly

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
