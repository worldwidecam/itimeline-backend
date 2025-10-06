# iTimeline User Community Timeline Implementation - Goal Plan

## Executive Summary (2025-09-23)
- **Main Goal**: Community timeline implementation
- **Child Goals (completed)**: Member page
- **Current Child Goal**: Admin page implementation
- **Grandchild Goals (completed)**: Manage Members tab
  - a) Active Members tab working
  - b) Blocked Members tab working
- **Current Grandchild Goal**: Manage Posts tab
  - a) Reporting system — in place
  - b) Remove from community — COMPLETED (chips cross out; event unshared from target community only; persists across views)
  - c) DELETE post — PENDING
  - d) SAFEGUARD post — PENDING



### Current Context
- [ ] DELETE POST button implementation (Manage Posts tab)
 - [ ] plan of action
 - [ ] considerations
 - [ ] associations
 - [ ] limitations 
 - [ ] possible deletion of related media if relevant

#### Next Steps
- [ ] safeguard post button/feature implementation (plan of action)
- [ ] UNDER REVIEW icon implementation


#### APPENDIX: NOTES
- Passport endpoints now use `utils/db_helper.get_db_engine()` to avoid Flask-SQLAlchemy app-context coupling.
- Report removal does not mutate schema and relies on `timeline_block_list` (created if missing by backend safety checks).
- DELETE Post feature progress (paused pending product spec):
  - Backend support added in `routes/reports.py#resolve_report()` for `action: "delete"`.
  - Deletes are defensive: checks table existence (`to_regclass`) before deleting from `event_timeline_association`, `event_tags`/`event_tag`, `timeline_block_list`, and finally `event`.
  - Response includes delete metrics: `deleted_event`, `deleted_assoc_count`, `deleted_tags_count`, `deleted_blocklist_count`.
  - No schema changes were introduced; entirely runtime-safe.
  - README updated with Manage Posts flow; delete marked as “paused for product design”.
 
 - DELETE Button — Current Implementation Assessment (2025-09-23)
   - Behavior (in `routes/reports.py#resolve_report()` when `action: "delete"`):
     - Marks the report as `resolved` with `resolution = 'delete'` and requires a non-empty `verdict` string.
     - Performs best‑effort, global deletion of the underlying event and related rows:
       - Deletes from `event_timeline_association` (all timelines for that event).
       - Deletes tag links from either `event_tags` or `event_tag` (whichever table exists).
       - Deletes any `timeline_block_list` entries for the event.
       - Deletes the `event` row itself.
     - All deletions are guarded via `to_regclass` checks to avoid transaction aborts if a table is absent.
     - Access control enforced: moderator+ only via `check_timeline_access(..., required_role='moderator')`.
   - Response fields (delete action):
     - `deleted_event` (boolean), `deleted_assoc_count`, `deleted_tags_count`, `deleted_blocklist_count`.
     - `report_id`, `timeline_id`, `action`, `verdict`, `new_status`, `resolved_at`, `event_id`.
     - `full_delete_required` is always `false` for delete (not applicable; full delete is the action itself).
   - Considerations:
     - This is a global deletion (removes the event from all timelines), unlike `remove` which only unshares from the current timeline.
     - Product policy decision is required before enabling UI: criteria for when a global delete is permitted vs. a per‑timeline remove or safeguard.
     - Auditability: `verdict` is stored on the `reports` row; no separate audit log table is used.
     - Concurrency: guarded with best‑effort checks; no explicit locks beyond transaction scope.
   - Limitations / Not implemented:
     - No media file deletion is performed (e.g., Cloudinary or local uploads) — only database rows are deleted.
     - No soft‑delete/archival path; deletion is destructive at the DB row level.
     - No cross‑timeline notification or cascade beyond DB row removals.
     - No UI wiring by design yet (DELETE remains gated/paused pending product approval).

### Completed Tasks

#### Backend
- ✅ Created `UserPassport` model in `models.py`
- ✅ Created migration script `create_user_passport_table.py` to set up the database table
- ✅ Implemented API endpoints in `routes/passport.py`:
  - ✅ `GET /api/v1/user/passport`: Fetch the user's passport
  - ✅ `POST /api/v1/user/passport/sync`: Sync the passport with latest membership data
- ✅ Registered the passport blueprint in `app.py`

#### Frontend
- ✅ Added new API utility functions in `utils/api.js`:
  - ✅ `fetchUserPassport`: Fetches user passport from backend and caches it
  - ✅ `syncUserPassport`: Syncs passport with backend after membership changes
- ✅ Updated `checkMembershipFromUserData` to use the passport system
- ✅ Updated `requestTimelineAccess` to sync the passport after joining a community
- ✅ Updated `AuthContext.js` to:
  - ✅ Use passport system during login, session validation, and token refresh
  - ✅ Clear passport data during logout
  - ✅ Import the new passport functions

#### Testing
- ✅ Created `test_user_passport.py` to test the passport system end-to-end
- ✅ Created `check_user_passport.py` to inspect the passport database table
- ✅ Updated README with new terminology and understanding

## Terminology

- **UserPassport**: A server-side, user-specific collection of membership data that persists across devices and sessions
- **Membership Persistence**: The ability to maintain consistent membership status regardless of device or session
- **User-Specific Caching**: Storing data in localStorage with keys that include the user ID to prevent cross-user data leakage
- **Passport Sync**: The process of updating the server-side passport with the latest membership data
- **Implicit Membership**: Automatic membership granted to timeline creators and site owners without requiring explicit join actions
