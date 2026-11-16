# Lead profile: <offer name>

*Read by `review-lead-finder`. Copy this file anywhere, one per offer, fill every
section and pass its path as `--profile`; the skill stops if a section is missing.
Relative paths are relative to this file.*

## Offer

- **What you sell, in one line:**
- **Proof link to put in the email:**

## Fit evidence

*What must be true of a company before the pain matters, and how to prove it from a
public page.*

- **Must be true:** (for example: "the iOS app is built with <framework>")
- **Evidence that counts:** the kinds of page that prove it, such as the company's own
  job posts or engineering blog, a vendor's customer stories, award lists, agency case
  studies.
- **Where to look first:** URLs or searches.
- **Doesn't count:** for example, a search snippet whose page you didn't open.

## Pain

- **Pattern file:** path to a file with one regex per line (presets in
  the skill's `presets/` folder).
- **App Store countries:** for example `us`.
- **Recency:** only flag reviews from the last N days.
- **Maximum rating:** only flag reviews at or below this many stars.
- **Keep a candidate with no complaint?** yes or no, and when.

## Filters

- **Team size:** for example 2 to 50 people.
- **Regions allowed:**
- **Excluded:** regions, markets or company types to skip.
- **Already contacted:** the target list below is checked for duplicates.

## Contact rules

- **Who to reach:** roles, in order of preference.
- **Allowed routes:** for example a personal public profile, or an address or form
  published on the company's own site. Never guessed addresses.
- **Per-country rules:** for example countries where cold email needs prior consent,
  and the route to use there instead.

## Hook

- **Tone and rules for the first line:**
- **One good example:**

## Output

- **Target file:** absolute path of the list to append to.
- **Section heading for new leads:** for example `### Added <date> by review-lead-finder`.
- **Fields per lead:** the bullet labels, in order.
- **Tracker:** the tracker table to add rows to, its columns, and how priority is set.
