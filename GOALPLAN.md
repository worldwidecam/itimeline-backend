# iTimeline User Passport Implementation - Goal Plan

## Concise Status (2025-08-31)
- **What we're working on**: Community timeline admin actions and User Passport stability
- **Finished**: UserPassport model/table; community blueprint registered in `app.py`; admin/member routes active; duplicate passport routes removed from `app.py` (single source in `routes/passport.py`)
- **Current focus/problems**:
  - 403 on `GET /api/v1/timelines/5/blocked-members` for non-privileged users is expected per `check_timeline_access()` rules.
  - Finalize E2E verification that member removal persists across refresh/sessions after `POST /api/v1/user/passport/sync`.
- **Where we left off**: Identity confirmed; blueprint routes active; proceed with removal → sync → reload validation.
- **Immediate plan**: Verify E2E removal persistence and tighten logs. No schema changes.

### Progress Today (Postgres alignment)
- **Backend**: Removed sqlite in passport routes; now use `db.engine.begin()` + `text()` with Postgres, `ON CONFLICT` upsert for `user_passport`
- **Runtime**: Backend runs against local Postgres via `DATABASE_URL`; frontend Vite dev server running and hitting backend

### Next Step — Remove/Block Intent vs Current Behavior
1) **DELETE route under `/api/v1` is active**
   - `community_bp` is registered in `app.py` with `url_prefix='/api/v1'`, so `DELETE /api/v1/timelines/<timeline_id>/members/<user_id>` is live.
   - Current behavior: sets `is_active_member = FALSE` AND `is_blocked = TRUE` (acts like a block/ban, not a kick).
2) **On successful DELETE**: Client should trigger `POST /api/v1/user/passport/sync` to persist membership changes.

Mini-roadmap for alignment:
- [ ] Add log lines in DELETE/BLOCK/UNBLOCK handlers to capture actor/target and decision
- [ ] Verify `GET /api/v1/timelines/{id}/members` excludes `is_blocked = TRUE`
- [ ] Verify `GET /api/v1/timelines/{id}/blocked-members` lists only `is_blocked = TRUE`
- [ ] E2E: remove → sync → refresh; block → sync → refresh; unblock → sync → refresh

---

## Community Admin — Intent & Findings (Updated)

### Confirmed Intent (2025-09-02)
- Remove (kick): set `is_active_member = FALSE`, `is_blocked = FALSE`. User must re-Join to return.
- Block (ban): set `is_blocked = TRUE`, `is_active_member = FALSE`. User appears in blocked list.
- Unblock: set `is_blocked = FALSE`, `is_active_member = TRUE` (restore active standing).
- Permissions (all actions): actor rank > target rank (SiteOwner > Creator/Admin > Moderator > Member). No self-actions. Equal rank cannot act on equal rank.

### Frontend call path
- **Frontend call path**: `src/components/timeline-v3/community/AdminPanel.js` → `handleRemoveMember()` → `removeMember(timelineId, userId)` in `src/utils/api.js`.
- **DELETE endpoint used by frontend**: `/api/v1/timelines/{timelineId}/members/{userId}`.
- **Backend implementation location**: `routes/community.py` defines `@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>', methods=['DELETE'])`.
- **Current result**: DELETE behaves like block (`is_blocked = TRUE`). This will be changed to "kick" per intent.
- **Blueprint registration**: `community_bp` is imported and registered in `app.py` with `url_prefix='/api/v1'`; route is active.
- **Post-action**: Client should call `POST /api/v1/user/passport/sync`.

### Decision Point

- Decision: Align DELETE to be kick-only; keep BLOCK/UNBLOCK semantics; apply rank-based permission checks across actions; passport sync remains client-triggered post-action.

### E2E Verification Checklist

- [ ] Remove member via `DELETE /api/v1/timelines/<timeline_id>/members/<user_id>` (as admin/mod).
- [ ] Immediately call `POST /api/v1/user/passport/sync`; confirm 200 and updated `last_updated`.
- [ ] `GET /api/v1/membership/timelines/{id}/members` excludes inactive member.
- [ ] Refresh frontend; removed member does not reappear in AdminPanel or MemberList.
- [ ] Repeat in second browser/profile to confirm persistence across sessions.

## Detailed history (archive)

## Current Status (July 6, 2025)

We have successfully implemented the initial version of the UserPassport system for membership persistence across devices and sessions. This system addresses the issue of membership data leakage between users and devices by storing membership data server-side in a user-specific passport.

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

## Next Steps

### Testing and Validation
- [ ] Run the backend server and test the passport system with `test_user_passport.py`
- [ ] Verify that passports are correctly synced after membership changes
- [ ] Test membership persistence across multiple devices and sessions
- [ ] Check that the "Join Community" button and membership UI correctly reflect the passport state

### Frontend Enhancements
- [ ] Add loading indicators during passport fetch/sync operations
- [ ] Implement error handling for passport fetch/sync failures
- [ ] Add automatic passport refresh after certain time period
- [ ] Update any remaining components that use the old membership system

### Backend Improvements
- [ ] Add more comprehensive error handling in passport endpoints
- [ ] Optimize passport sync operation for large numbers of memberships
- [ ] Add logging for passport operations to track usage and diagnose issues
- [ ] Consider adding a batch operation to update multiple user passports at once

### Documentation
- [ ] Create API documentation for the new passport endpoints
- [ ] Document the passport system architecture and data flow
- [ ] Update frontend documentation with passport usage guidelines

## Technical Debt and Future Considerations
- [ ] Consider migrating legacy membership endpoints to use the passport system
- [ ] Evaluate performance impact of passport system on high-traffic operations
- [ ] Plan for potential future features like membership expiration or tiered access
- [ ] Consider adding a passport version field for future schema migrations

## Backlog

- [ ] Members listing pagination — buffered infinite scroll
  - Fixed window shows ~10; fetch 30 per page; prefetch at ~70% scroll depth
  - Stable sort; de-dupe on merge; subtle shimmer loader; no “Load more” button
  - Backend later: `limit/offset` + `hasMore/nextOffset` response; stable ordering

## Terminology

- **UserPassport**: A server-side, user-specific collection of membership data that persists across devices and sessions
- **Membership Persistence**: The ability to maintain consistent membership status regardless of device or session
- **User-Specific Caching**: Storing data in localStorage with keys that include the user ID to prevent cross-user data leakage
- **Passport Sync**: The process of updating the server-side passport with the latest membership data
- **Implicit Membership**: Automatic membership granted to timeline creators and site owners without requiring explicit join actions
