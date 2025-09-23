# iTimeline User Passport Implementation - Goal Plan

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

## Concise Status (2025-09-03)
- **What we're working on**: Community admin actions (Remove/Kick, Block, Unblock) and User Passport stability
- **Finished**: UserPassport model/table; community blueprint registered in `app.py`; admin/member routes active; duplicate passport routes removed from `app.py` (single source in `routes/passport.py`)
- **Newly finished (2025-09-23)**: Report resolve → Remove now works end-to-end via `timeline_block_list` (unshares from a single community timeline; chips cross out across views; event remains visible elsewhere). Legacy single-timeline guard removed; relaxed "exists elsewhere" rule enforced safely.
- **Current focus/problems**:
  - Block foundation implemented: Blocked state persists after refresh/sessions when client calls `POST /api/v1/user/passport/sync`.
  - 403 on `GET /api/v1/timelines/{id}/blocked-members` for non-privileged users is expected per `check_timeline_access()`.
  - Behavior alignment: `DELETE` currently behaves like block; needs split into Kick vs Block.
- **Where we left off**: E2E tests show persistence after refresh for the block-like flow. Further polish and alignment needed.
- **Immediate plan**: Chronicle progress; add subgoals; tighten logging. No schema changes.

### Progress Today (Postgres alignment)
- **Backend**: Removed sqlite in passport routes; now use `db.engine.begin()` + `text()` with Postgres, `ON CONFLICT` upsert for `user_passport`
- **Runtime**: Backend runs against local Postgres via `DATABASE_URL`; frontend Vite dev server running and hitting backend

### Progress Today (2025-09-23)
- **Backend**: Stabilized `routes/reports.py` resolve/remove to avoid transaction aborts (removed DO $$ blocks during requests; added table-existence checks; per-name timeline matching). Implemented `timeline_block_list` usage for removal without schema changes.
- **Frontend**: Ensured `removedTimelineIds` is passed to `TagList` across event cards so removed chips cross out consistently.

### Next Step
- [ ] DELETE POST button implementation (Manage Posts tab)
- [ ] Add log lines in DELETE/BLOCK/UNBLOCK handlers to capture actor/target and decision
- [ ] Verify `GET /api/v1/timelines/{id}/members` excludes `is_blocked = TRUE`
- [ ] Verify `GET /api/v1/timelines/{id}/blocked-members` lists only `is_blocked = TRUE`
- [ ] E2E: remove → sync → refresh; block → sync → refresh; unblock → sync → refresh

### Block Feature Foundation Progress (2025-09-03)
- **What works now**:
  - Blocking semantics are functionally achievable via current DELETE path (temporary behavior) and persist after refresh when followed by `POST /api/v1/user/passport/sync`.
  - Database fields `timeline_member.is_blocked` and `is_active_member` audited and present.
  - AdminPanel UX reflects changes after passport sync and reload.
- **Not done yet**:
  - Dedicated Block and Unblock endpoints (separate from Kick/Remove).
  - Rank-based enforcement unified across Remove/Block/Unblock.
  - Consistent response payloads and client messaging.
  - Server-side logging for actor/target, decisions, and outcomes.

#### Subgoals (do not mark complete yet)
- [ ] Implement explicit `POST /api/v1/timelines/{id}/members/{userId}/block`
- [ ] Implement explicit `POST /api/v1/timelines/{id}/members/{userId}/unblock`
- [ ] Adjust `DELETE /api/v1/timelines/{id}/members/{userId}` to be Kick only (`is_active_member = FALSE`, `is_blocked = FALSE`)
- [ ] Enforce rank/role rules uniformly (no self-actions; higher rank required; equal rank blocked)
- [ ] Add structured logs for DELETE/BLOCK/UNBLOCK (actor_id, target_id, timeline_id, action, prev_state → new_state)
- [ ] Update README and API docs with final semantics once aligned

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
