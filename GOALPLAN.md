# iTimeline User Passport Implementation - Goal Plan

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
