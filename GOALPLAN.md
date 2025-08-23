# iTimeline User Passport Implementation - Goal Plan

## Concise Status (2025-08-22)
- **What we're working on**: Backend support for Community timelines via the Passport system
- **Finished**: UserPassport model, table, and endpoints
  - `GET /api/v1/user/passport`, `POST /api/v1/user/passport/sync` registered in `app.py`
- **Where we left off**: Harden logging/error handling and verify sync after membership changes
- **Today's frontend-driven task**: Support AdminPanel "Remove from community" by ensuring backend responses and passport sync behave as expected

---

## Community Admin "Remove from community" — Findings (Quarantine Mode)

- **Frontend call path**: `src/components/timeline-v3/community/AdminPanel.js` → `handleRemoveMember()` → `removeMember(timelineId, userId)` in `src/utils/api.js`.
- **DELETE endpoint used by frontend**: `/api/v1/timelines/{timelineId}/members/{userId}`.
- **Backend implementation location**: `routes/community.py` defines `@community_bp.route('/timelines/<int:timeline_id>/members/<int:user_id>', methods=['DELETE'])` which performs a soft delete (`is_active_member = False`) with permission checks.
- **Critical issue**: `community_bp` is currently NOT registered in `app.py`:
  - Import commented: `# from routes.community import community_bp`
  - Registration commented: `# app.register_blueprint(community_bp, url_prefix='/api/v1')`
- **Resulting mismatch**:
  - Member listing uses active routes in `app.py`: `GET /api/v1/membership/timelines/{id}/members` (works).
  - Removal uses unregistered blueprint route under `/api/v1/timelines/...` (likely 404/401), so the button appears to work in UI (optimistic state + cache clears) but does not persist server-side.
- **Caching/state notes**: After DELETE attempt, UI filters member locally and clears `timeline_*` and `user_passport_*` keys, but a full reload restores the member since backend didn’t persist removal.

### Decision Point (Next Step after Restart)

- **Action**: Review these findings and decide one path:
  1) Keep current button flow and enable/fix backend endpoint registration for `community_bp` under `/api/v1` to activate DELETE/role/blocked routes.
  2) Redesign button to target the already-active "new clean" membership routes (align remove with `/api/v1/membership/...`) and deprecate old `/api/v1/timelines/...` paths.
- We will not implement changes until the decision is made; this GOALPLAN serves as the guide for that review.

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

## Terminology

- **UserPassport**: A server-side, user-specific collection of membership data that persists across devices and sessions
- **Membership Persistence**: The ability to maintain consistent membership status regardless of device or session
- **User-Specific Caching**: Storing data in localStorage with keys that include the user ID to prevent cross-user data leakage
- **Passport Sync**: The process of updating the server-side passport with the latest membership data
- **Implicit Membership**: Automatic membership granted to timeline creators and site owners without requiring explicit join actions
