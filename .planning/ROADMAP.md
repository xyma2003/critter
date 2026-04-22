# Roadmap: Critter

## Overview

Four new feature areas are added to the existing 2056-line brownfield `desktop_pet.py`. Each phase delivers one complete, independently verifiable capability. News Bookmarks come first because they establish the `StorageRepository` pattern that all future persistent data should follow. Weather Tab and Mood System are independent of each other and execute in parallel-friendly order. Custom Pet Image completes the milestone by wiring the pet's visual identity across the three display surfaces established by earlier phases.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: News Bookmarks** - Users can save, review, and remove bookmarked news and "read later" items, backed by a StorageRepository layer (completed 2026-04-16)
- [ ] **Phase 2: Weather Tab** - A new Weather tab shows real-time and 3-day forecasts for an unlimited number of user-managed cities
- [ ] **Phase 3: Mood System** - The pet has a living mood value that decays over time, rises from interactions, and visibly influences greetings and the floating emoji
- [ ] **Phase 4: Custom Pet Image** - Users can upload a personal photo that replaces the default emoji in the floating window, chat avatar, and pet tab

## Phase Details

### Phase 1: News Bookmarks
**Goal**: Users can collect news items for later reading and manage those collections from within the News tab
**Depends on**: Nothing (brownfield base; News tab already exists)
**Requirements**: NEWS-01, NEWS-02, NEWS-03, NEWS-04, NEWS-05
**Success Criteria** (what must be TRUE):
  1. User can tap a bookmark icon on any news item and see it appear in a Bookmarks list within the News tab
  2. User can tap a "read later" icon on any news item and see it appear in a separate Read Later list within the News tab
  3. User can switch between the main news feed, Bookmarks list, and Read Later list without leaving the News tab
  4. User can delete any entry from the Bookmarks or Read Later list and the deletion persists after app restart
  5. All bookmark and read-later data survives app restarts (stored via StorageRepository to local JSON)
**Plans**: 2 plans
Plans:
- [x] 01-01-PLAN.md — StorageRepository class + BOOKMARKS_FILE constant + MainPanel wiring
- [x] 01-02-PLAN.md — News tab UI: view-switch toolbar, per-card bookmark/read-later buttons, collection list view with delete
**UI hint**: yes

### Phase 2: Weather Tab
**Goal**: Users can monitor current conditions and short forecasts for any cities they choose, without needing an API key
**Depends on**: Phase 1
**Requirements**: WTHR-01, WTHR-02, WTHR-03, WTHR-04, WTHR-05, WTHR-06
**Success Criteria** (what must be TRUE):
  1. A Weather tab is visible in the main panel tab bar and shows current temperature, weather condition, and "feels like" for the active city
  2. User can type any city name (Chinese or English) and add it to a persistent city list; the weather loads automatically
  3. User can delete a city from the list and it does not reappear after restart
  4. User can see a 3-day forecast (date, condition, high/low temps) for the selected city
  5. A manual Refresh button triggers a new fetch; data is cached for 15 minutes so repeated clicks do not re-fetch
**Plans**: 3 plans
Plans:
- [x] 02-01-PLAN.md — Weather service module (services/weather/__init__.py) + WEATHER_FILE constant + unit tests
- [ ] 02-02-PLAN.md — Weather tab UI: nav registration, city list sidebar, add/delete city, current conditions display
- [ ] 02-03-PLAN.md — 3-day forecast cards + Refresh button with 15-min cache guard + human-verify checkpoint
**UI hint**: yes

### Phase 3: Mood System
**Goal**: The pet feels alive — its mood rises and falls based on time and user attention, and that mood is visible everywhere the pet appears
**Depends on**: Phase 1
**Requirements**: MOOD-01, MOOD-02, MOOD-03, MOOD-04, MOOD-05, MOOD-06, MOOD-07
**Success Criteria** (what must be TRUE):
  1. The pet's mood value (0-100) is saved to settings.json and restored on restart — mood is never reset by a relaunch
  2. After the app runs for an extended period without interaction, the mood value visibly decreases (observable via the pet tab mood bar)
  3. After the user sends a chat message, the mood bar in the pet tab shows a higher value than before the message
  4. The pet tab shows three clickable interaction buttons ("喂食", "玩耍", "抚摸") and clicking any of them increases the mood bar
  5. The welcome greeting on the home tab changes wording based on mood level (happy / neutral / bored), and the floating emoji changes to match the current mood tier
**Plans**: TBD

### Phase 4: Custom Pet Image
**Goal**: Users can give the pet a personal face that appears consistently in every surface the pet occupies
**Depends on**: Phase 3
**Requirements**: PET-01, PET-02, PET-03, PET-04, PET-05, PET-06
**Success Criteria** (what must be TRUE):
  1. User can open a file picker from the pet tab or settings tab, select a local image, and see it immediately appear as the pet's avatar
  2. The uploaded image is stored in the app directory as a circular crop and survives app restart
  3. The floating always-on-top window shows the custom circular image instead of the default emoji (animation continues to work)
  4. Chat message bubbles show the custom circular image as the pet's avatar on the left side
  5. The pet tab displays the custom image at large size in the pet's display area
  6. A "Reset to default" control restores the original emoji in all three locations and removes the stored image file
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. News Bookmarks | 2/2 | Complete   | 2026-04-16 |
| 2. Weather Tab | 1/3 | In Progress|  |
| 3. Mood System | 0/TBD | Not started | - |
| 4. Custom Pet Image | 0/TBD | Not started | - |
