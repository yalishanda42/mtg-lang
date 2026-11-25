# Showcase index page — short design

Date: 2026-11-26. Approved by the user in chat.

**Intent.** The gallery's landing page becomes a showcase of the Bulgarian sample: every card in
`data/bg-sample.txt` in three columns — original scan, MTG-Lang card, old-spelling Bulgarian card.

**Design.** Title + one-line intro; three pinned column headers (Original · MTG-Lang · Bulgarian (old spelling));
one row per sample card with the three existing card views (no new drawing), the card name and a link to its
set page; on narrow screens the three cards stack with their labels. The set coverage table and the English
match rate (ability lines matching Oracle) move to a small footer. Set pages and the Legend are unchanged.

**Approaches.** One sensible way: reuse the set pages' card-view markup through template macros. A separate
page or client-side cloning of the set pages' cards was set aside (duplicated markup / slower first paint).

**Plan.** (1) Test: index has one row per sample card with three `<figure>`s, the headers and the footer
numbers. (2) Template macros for the original / overlay figures, used by both the set pages and the index.
(3) `render_site` passes the sample rows and the eval summary. (4) CSS grid + sticky headers + narrow-screen
stacking. (5) README line. Commit and push; merge on the user's word.
