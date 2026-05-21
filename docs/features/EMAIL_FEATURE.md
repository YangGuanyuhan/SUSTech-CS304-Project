# Email Feature

## Overview

The email feature lets the agent work with email in a controlled way. It supports:

- runtime email configuration
- reusable email profiles
- SMTP connection testing
- IMAP inbox reading
- approval-based email sending

The main safety rule is simple: the agent can prepare an email, but the user confirms before it is sent.

## Current Workflow

### Configure Email

In `Settings > Email`, the user can set:

- `smtp_host`
- `smtp_port`
- `smtp_user`
- `smtp_encryption`
- `imap_host`
- `imap_port`
- `password`

Profiles can be saved and applied later. In the current implementation, SMTP and IMAP use the same account credentials.

### Read Recent Emails

Once configured, the agent can read recent inbox messages and summarize them. Typical use cases:

- check the latest emails
- summarize course-related messages
- extract deadlines or meeting information

### Send Emails

The send flow is:

1. The user asks the agent to prepare an email.
2. The agent generates the message.
3. The frontend shows an approval card.
4. The user confirms.
5. The system sends the email through SMTP.

## API Endpoints

The main API endpoints are:

- `PUT /api/settings/email` - update current email settings
- `POST /api/settings/email/test` - test SMTP connectivity
- `GET /api/settings/email/profiles` - list saved profiles
- `PUT /api/settings/email/profiles` - save a profile
- `POST /api/settings/email/profiles/{name}/apply` - apply a saved profile
- `POST /api/email/draft` - create an email draft
- `POST /api/email/confirm/{draft_id}` - confirm and send a draft

Example draft payload:

```json
{
  "to": "teacher@example.com",
  "subject": "Request for extension",
  "body_instruction": "Explain the situation and ask for a two-day extension."
}
```

## Frontend Entry Points

- `Settings > Email` for configuration, save, apply, and test
- chat requests for reading or sending emails
- approval card for final confirmation before send

## SUSTech Email Example

Here are the instructions to set up your SUSTech email account (which uses Tencent Exmail) to work with the agent.

### Obtaining the Password and Enabling Services

1. Log into your SUSTech web email.
2. Click on the settings (设置) page and choose "邮箱绑定" (Email Binding).
3. Enable "安全登录" (Secure Login) and generate a client password. Record this 16-character password—you will use it instead of your normal account password.
4. Go to the receive/send settings (收发信设置) and enable both **IMAP/SMTP** and **POP/SMTP** services.

### Configuration Settings

Use the following Exmail server configurations:

| Field | Example Value |
|------|------|
| `smtp_host` | `smtp.exmail.qq.com` |
| `smtp_port` | `465` |
| `smtp_user` | `your_email@mail.sustech.edu.cn` |
| `smtp_encryption` | `SSL` |
| `imap_host` | `imap.exmail.qq.com` |
| `imap_port` | `993` |
| `password` | `16_character_client_password` |

### Example Flow

1. Create a profile named `sustech-mail`.
2. Fill in the verified SMTP and IMAP settings mentioned above.
3. Test the connection.
4. Save and apply the profile.
5. Ask the agent to read recent emails.
6. Ask the agent to prepare a message.
7. Confirm before sending.

## Related Files

- `frontend/src/components/SettingsPanel.vue`
- `frontend/src/components/EmailConfirm.vue`
- `backend/api/routes.py`
- `backend/services/agent_tool_service.py`
- `backend/services/email_service.py`
