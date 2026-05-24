# Blackboard Feature

## Overview

The Blackboard feature lets the agent work with SUSTech Blackboard in a controlled way. It supports:

- runtime Blackboard account configuration
- reusable Blackboard profiles
- CAS login and connection testing
- course listing and announcement reading
- Blackboard calendar synchronization
- course file tree browsing
- authenticated browser download links for course attachments

The main safety rule is simple: Blackboard credentials are configured by the user, and file access is exposed through server-side authenticated sessions instead of leaking raw cookies to the frontend.

## Current Workflow

### Configure Blackboard

In `Settings > Blackboard`, the user can set:

- `student_id`
- `password`
- `base_url`

Profiles can be saved and applied later. The runtime configuration keeps the current password in backend memory, while saved profiles store account metadata and encrypted password state through the settings service.

### Test Login

The user can test the Blackboard connection from the settings page. The backend:

1. Opens the Blackboard entry URL.
2. Follows the SUSTech CAS redirect when needed.
3. Submits the student ID and CAS password.
4. Reports whether login succeeded.

The agent also has a `blackboard_test_api_available` tool that checks login and probes the Blackboard `users/me` API.

### Read Courses and Announcements

Once configured, the agent can fetch Blackboard courses for the current user. Typical use cases:

- show all current Blackboard courses
- find the internal `course_id` needed by later tools
- read announcements for a selected course
- summarize course notices in chat

The service layer caches course, assignment, and announcement payloads. If Blackboard is temporarily unavailable, cached data can be returned with a warning.

### Sync Blackboard Calendar

Blackboard calendar items can be synced into the local calendar. Synced Blackboard events are marked as read-only in the UI, so the user does not accidentally edit source-owned data.

The user can clone a Blackboard event into a local event when they want to edit it manually.

### Browse and Download Course Files

The file panel can load courses, expand Blackboard content nodes, and display attachments. File downloads are proxied through the backend:

1. The frontend requests a course list.
2. The backend authenticates with Blackboard and caches the provider session.
3. The frontend requests a course or folder tree.
4. The backend loads children and attachments with Blackboard API cookies.
5. The frontend opens a backend download URL for a specific attachment.
6. The backend downloads the upstream file and returns it to the browser.

The agent can also search through a course tree and return browser download URLs for matching files.

## API Endpoints

The main Blackboard settings endpoints are:

- `GET /api/settings/blackboard` - get current runtime Blackboard settings
- `PUT /api/settings/blackboard` - update current runtime Blackboard settings
- `POST /api/settings/blackboard/test` - test CAS login with Blackboard credentials
- `GET /api/settings/blackboard/profiles` - list saved Blackboard profiles
- `PUT /api/settings/blackboard/profiles` - save a Blackboard profile
- `DELETE /api/settings/blackboard/profiles/{name}` - delete a saved profile
- `POST /api/settings/blackboard/profiles/{name}/apply` - apply a saved profile

The main Blackboard data endpoints are:

- `GET /api/blackboard/courses` - fetch Blackboard courses through the service cache wrapper
- `POST /api/calendar/sync/blackboard` - sync Blackboard calendar items into the local calendar
- `POST /api/calendar/events/{event_id}/clone` - clone a read-only Blackboard event into a local event
- `GET /api/blackboard/files/courses` - fetch courses for the file browser
- `GET /api/blackboard/files/tree/{course_id}` - fetch a course or folder content tree
- `GET /api/blackboard/files/download` - download one Blackboard attachment through the backend proxy
- `POST /api/blackboard/files/download-batch` - currently returns a guidance error because folder nodes are not directly downloadable

Example settings payload:

```json
{
  "student_id": "12345678",
  "password": "cas_password",
  "base_url": "https://bb.sustech.edu.cn/learn/api/public/v1",
  "replace_password": true
}
```

Example profile payload:

```json
{
  "name": "sustech-bb",
  "student_id": "12345678",
  "base_url": "https://bb.sustech.edu.cn/learn/api/public/v1",
  "password": "cas_password"
}
```

Example file tree request:

```text
GET /api/blackboard/files/tree/_12345_1?node_id=_67890_1
```

Example attachment download request:

```text
GET /api/blackboard/files/download?course_id=_12345_1&content_id=_67890_1&attachment_id=_99999_1&file_name=lab.pdf
```

## Agent Tools

The Blackboard feature is exposed to the agent through these tools:

- `blackboard_get_all_courses` - fetch all courses available to the current user
- `blackboard_get_course_announcements` - fetch announcements for a specific course
- `blackboard_test_api_available` - test CAS login and Blackboard API availability
- `blackboard_get_calendar_items` - fetch Blackboard calendar items
- `blackboard_download_files` - search a course or folder tree and return browser download URLs
- `calendar_sync_blackboard` - sync Blackboard calendar items into the local calendar
- `calendar_clone_blackboard_event` - clone a Blackboard event into an editable local event

Example file search tool arguments:

```json
{
  "course_id": "_12345_1",
  "query": "lab9",
  "max_files": 20
}
```

## Frontend Entry Points

- `Settings > Blackboard` for runtime configuration, saved profiles, apply, delete, refresh, and connection testing
- chat requests for courses, announcements, calendar items, and file download links
- `CalendarPanel` for Blackboard sync, read-only Blackboard event display, and event cloning
- `FilePanel` for course tree browsing and attachment downloads
- `ChatWindow` course loading actions for quick Blackboard course inspection

## SUSTech Blackboard Example

Use the following default SUSTech Blackboard configuration:

| Field | Example Value |
|------|------|
| `student_id` | `your_student_id` |
| `password` | `your_CAS_password` |
| `base_url` | `https://bb.sustech.edu.cn/learn/api/public/v1` |

### Example Flow

1. Create a profile named `sustech-bb`.
2. Fill in the student ID, CAS password, and Blackboard API base URL.
3. Test the connection.
4. Save and apply the profile.
5. Ask the agent to show Blackboard courses.
6. Use the returned `course_id` to read announcements or search for files.
7. Sync Blackboard calendar items into the calendar panel.
8. Clone any Blackboard event that needs local edits.

## Implementation Notes

- `DemoBlackboardProvider` performs CAS login and uses the authenticated session for Blackboard API calls.
- `BlackboardService` wraps provider calls and adds database cache fallback for courses, assignments, and announcements.
- `BBFileManager` loads Blackboard content trees asynchronously and collects attachments.
- File downloads are proxied by the backend so the browser receives normal download responses without direct Blackboard session handling.
- Runtime settings can auto-apply the first saved Blackboard profile when no active runtime student ID is configured.
- Blackboard calendar events are source-owned and read-only until cloned into local calendar storage.

## Related Files

- `frontend/src/components/SettingsPanel.vue`
- `frontend/src/components/CalendarPanel.vue`
- `frontend/src/components/FilePanel.vue`
- `frontend/src/components/ChatWindow.vue`
- `frontend/src/api/client.js`
- `backend/api/routes.py`
- `backend/api/schemas.py`
- `backend/services/agent_tool_service.py`
- `backend/services/blackboard_service.py`
- `backend/services/blackboard_file_service.py`
- `backend/services/calendar_service.py`
- `backend/services/runtime_settings.py`
- `backend/services/settings_service.py`
- `backend/models/settings.py`
- `tests/test_blackboard.py`
- `tests/test_file_manager.py`
- `tests/test_tool_service.py`
