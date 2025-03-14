# Hashtag System Fix

This directory contains scripts to fix issues with the hashtag system in the Timeline Forum application.

## Issue Description

The hashtag system had the following issues:
1. Timeline names created from hashtags had a '#' prefix, causing matching problems
2. Case sensitivity issues between hashtags and timeline names
3. Events weren't properly associated with timelines through tags
4. Delete functionality for timelines wasn't working correctly

## Fix Implementation

The following changes have been made:
1. Updated `create_timeline_v3_event` to not add '#' prefix to timeline names
2. Made hashtag and timeline name matching case-insensitive
3. Standardized on capitalized timeline names and lowercase tag storage
4. Fixed the timeline deletion functionality
5. Improved event-to-timeline association through tags

## Fix Scripts

Two scripts have been provided to fix existing data:

### 1. Fix Hashtag Timelines

This script fixes timelines with '#' prefix by creating new timelines without the prefix and migrating all associated events and tags.

```bash
python fix_hashtag_timelines.py
```

### 2. Standardize Timeline Case

This script standardizes the case of all timelines (capitalize) and tags (lowercase) for consistent matching.

```bash
python standardize_timeline_case.py
```

## Running the Fix

1. Make sure the application is not running
2. Run the fix scripts in the following order:
   ```bash
   python fix_hashtag_timelines.py
   python standardize_timeline_case.py
   ```
3. Restart the application

## Verification

After running the fix:
1. Existing timelines with '#' prefix should be replaced with properly named timelines
2. All events should appear on the correct timelines
3. The delete functionality for timelines should work correctly
4. New events with hashtags should be properly associated with timelines
