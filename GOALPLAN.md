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

#### Current Work-In-Progress (2025-10-14)
**PRIORITY: Membership Approval Toggle Implementation**

**Main Task**: Implement `requires_approval` toggle for community timelines
- ✅ Database column added (`requires_approval BOOLEAN`)
- ✅ Backend endpoint updated to save/load toggle state
- ✅ Frontend Admin Panel Settings tab toggle implemented
- ✅ Toggle saves successfully to database

**Current Sub-Task**: Fix Join Button to Respect Approval Toggle
- **ROOT CAUSE IDENTIFIED**: Frontend was calling wrong endpoint
  - ❌ Was calling: `/api/v1/membership/timelines/{id}/join` (no approval logic)
  - ✅ Now calling: `/api/v1/timelines/{id}/access-requests` (has approval logic)
- **FIXES APPLIED**:
  - ✅ Frontend now calls correct endpoint with approval checking
  - ✅ Removed pre-emptive localStorage write that bypassed backend response
  - ✅ Backend endpoint properly checks `requires_approval` toggle
  - ✅ Backend resets role to 'member' or 'pending' on rejoin (lines 3050-3068)
- **TESTING NEEDED**: Verify both scenarios work correctly:
  - Toggle OFF: User immediately becomes active member
  - Toggle ON: User gets pending status, requires admin approval

#### Future Steps
- [ ] Testing and refinement of Manage Posts workflow
- [ ] Optional: "Under Review" visual indicator on event cards
- [ ] Optional: Media file deletion (Cloudinary) when deleting events
- [ ] Consider audit log table for moderation actions (currently verdict stored in reports table)
- [ ] Implement "Leave Community" button for self-removal

---

## NEW MAJOR GOAL: Community Info Cards (2026-01-12)

### Feature Overview
Community Info Cards allow moderators and admins to create, edit, and delete informational cards within their community timelines. These cards display important information, resources, or curated lists (e.g., memorial lists, Discord links, community guidelines).

### Design Specifications

#### Access Control
- **Who can create/edit/delete**: Moderators and Admins (moderator+ role)
- **Who can view**: All community members and visitors
- **Admin Panel access**: New "Info Cards" tab (moderator+ access, unlike Settings which is admin-only)

#### Display Location
- **Primary**: Community members page (right or left side)
- **Layout**: Members listing reduced to 1/3 width; info cards occupy remaining space
- **Card styling**: Artistic, modern design matching project guidelines (no image uploads)

#### Card Structure
- **Title field**: Short, descriptive heading
- **Description field**: Rich text content (supports hyperlinks, bullet points, formatting)
- **No media uploads**: Text-only cards for simplicity and consistency

#### Functionality
- **CRUD operations**: Create, Read, Update, Delete via Admin Panel
- **Ordering**: Ability to reorder cards (TBD: drag-drop or priority field)
- **Visibility**: Public by default (all users see cards on members page)

### Implementation Tasks

#### Backend
- [ ] Design database schema: `CommunityInfoCard` model with fields (id, timeline_id, title, description, order, created_at, updated_at, created_by)
- [ ] Create migration for info cards table
- [ ] Implement API endpoints:
  - [ ] `GET /api/v1/timelines/{timeline_id}/info-cards` - List all cards for a community
  - [ ] `POST /api/v1/timelines/{timeline_id}/info-cards` - Create new card (moderator+)
  - [ ] `PUT /api/v1/timelines/{timeline_id}/info-cards/{card_id}` - Update card (moderator+)
  - [ ] `DELETE /api/v1/timelines/{timeline_id}/info-cards/{card_id}` - Delete card (moderator+)
  - [ ] `PATCH /api/v1/timelines/{timeline_id}/info-cards/reorder` - Reorder cards (moderator+)
- [ ] Implement permission checks (moderator+ for write operations)

#### Frontend
- [ ] Create Info Cards tab in Admin Panel (`AdminPanel.js`)
- [ ] Implement card management UI (list, create form, edit modal, delete confirmation)
- [ ] Refactor community members page layout (1/3 width for members, 2/3 for cards)
- [ ] Create `CommunityInfoCardsDisplay` component for members page
- [ ] Style cards with artistic modern design (consistent with project guidelines)
- [ ] Implement card reordering UI (drag-drop or priority controls)

#### Testing
- [ ] Verify moderator+ can create/edit/delete cards
- [ ] Verify non-moderators cannot modify cards
- [ ] Test card display on members page with various content
- [ ] Test layout responsiveness (1/3 + 2/3 split)
- [ ] Test card reordering functionality
- [ ] Test rich text rendering (links, formatting, bullet points)


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
