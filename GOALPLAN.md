# iTimeline User Community Timeline Implementation - Goal Plan

## Executive Summary (2025-10-10)
- **Main Goal**: Community timeline implementation
- **Child Goals (completed)**: Member page
- **Current Child Goal**: Admin page implementation
- **Grandchild Goals (completed)**: 
  - a) Manage Members tab - COMPLETE
    - Active Members tab working
    - Blocked Members tab working
  - b) Manage Posts tab - COMPLETE
    - Reporting system - COMPLETE
    - Remove from community - COMPLETE (timeline-specific blocklist removal)
    - DELETE post - COMPLETE (global deletion from all timelines)
    - SAFEGUARD post - COMPLETE (marks as reviewed/safe)



### Current Context
- ✅ **Manage Posts Tab - COMPLETE** (2025-10-10)
  - All three resolution actions fully implemented and working:
    - **Remove from Community** - Timeline-specific removal via blocklist
    - **DELETE Post** - Global deletion (removes event from ALL timelines + DB rows)
    - **SAFEGUARD Post** - Marks report as resolved/safe
  - Status workflow: pending → reviewing → resolved
  - Verdict requirement enforced for all actions
  - Real-time list updates after actions

#### Next Steps
- [ ] Testing and refinement of Manage Posts workflow
- [ ] Optional: "Under Review" visual indicator on event cards
- [ ] Optional: Media file deletion (Cloudinary) when deleting events
- [ ] Consider audit log table for moderation actions (currently verdict stored in reports table)


#### APPENDIX: NOTES

**Reporting System Implementation (COMPLETE - 2025-10-10)**

- All three resolution actions fully implemented in `routes/reports.py#resolve_report()`:

  1. **REMOVE** (Timeline-specific removal):
     - Adds event to `timeline_block_list` for the current timeline
     - Removes association from `event_timeline_association`
     - Enforces "exists elsewhere" rule: can only remove if event exists on other timelines or has multiple tags
     - Returns `full_delete_required` flag if event is now blocked on all timelines
     - Does NOT delete the event itself

  2. **DELETE** (Global deletion):
     - Permanently removes event from ALL timelines
     - Deletes from: `event_timeline_association`, `event_tags`/`event_tag`, `timeline_block_list`, and `event` table
     - All deletions guarded via `to_regclass` checks for table existence
     - Returns deletion metrics: `deleted_event`, `deleted_assoc_count`, `deleted_tags_count`, `deleted_blocklist_count`
     - **Limitation**: Does NOT delete media files (Cloudinary/local uploads) - only DB rows

  3. **SAFEGUARD** (Mark as safe):
     - Marks report as `resolved` with `resolution = 'safeguard'`
     - Event remains visible on timeline
     - Report dismissed

- **Common features across all actions**:
  - Verdict requirement enforced (mandatory text field)
  - Access control: moderator+ only via `check_timeline_access(..., required_role='moderator')`
  - Auditability: verdict stored in `reports` table
  - Status workflow: pending → reviewing → resolved
  - No schema changes required; uses existing tables + runtime-safe table creation

- **Technical notes**:
  - Passport endpoints use `utils/db_helper.get_db_engine()` to avoid Flask-SQLAlchemy app-context coupling
  - `timeline_block_list` created if missing by backend safety checks
  - All table operations guarded with `to_regclass` checks to prevent transaction aborts
  - Concurrency: best-effort checks within transaction scope

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
