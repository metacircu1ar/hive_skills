---
name: ios-prelaunch-checklist
description: Audit an iOS app before App Store submission across assets, technical setup, legal requirements, and account readiness. Use when preparing TestFlight or App Store release candidates, checking metadata, privacy policy, terms, SDKs, signing, bundle IDs, screenshots, icons, support contacts, or rejection-prone launch gotchas.
---

# iOS Prelaunch Checklist

Verify that an iOS release candidate has the required App Store artifacts, technical setup, legal links, and account state before submission.

## Scope

This skill is a readiness checklist for required artifacts and common launch blockers. For detailed App Store rejection-rule scanning, reference the complementary `app-store-preflight-skills` project by Truong Duy: https://github.com/truongduy2611/app-store-preflight-skills. Use that project for guideline-specific metadata, privacy, subscription, design, and entitlement rules; use this skill to confirm the broader release package is complete.

## Workflow

1. Identify release context:
   - App name, bundle ID, target platforms, build number/version, App Store Connect app, TestFlight status, target countries, age category, and whether the app uses subscriptions, IAP, kids content, health data, finance, crypto, VPN, UGC, or AI features.
2. Verify App Store assets:
   - 1024 x 1024 app icon exists and has no transparency.
   - Screenshots exist for required device sizes.
   - App description is under 4000 characters.
   - Privacy policy URL is live.
   - Support email or support URL works.
3. Verify technical setup:
   - API keys and secrets are in environment/config systems, not committed to code.
   - Error tracking is configured, such as Sentry or Bugsnag.
   - TestFlight was tested on real devices, not only simulators.
   - Third-party SDK versions are current enough for Apple's current requirements.
   - Obvious memory leaks, startup crashes, and production-only config failures have been checked.
4. Verify legal readiness:
   - Privacy policy and terms of service URLs are live.
   - COPPA/kids compliance is addressed if targeting children.
   - App privacy declarations match actual SDK usage and data collection.
   - Age rating matches content and features.
5. Verify account and signing readiness:
   - Apple Developer membership is active.
   - Bundle IDs match across Xcode, App Store Connect, server config, push notifications, and code.
   - Signing certificates and provisioning profiles are not expired.
   - App groups, associated domains, push, IAP, Sign in with Apple, and other capabilities match the app's entitlements.

## Historical Gotchas To Surface

Always call out these risks if evidence is missing:

- Missing support email or support URL can cause immediate rejection.
- Wrong or unreachable privacy policy can delay review.
- Expired certificates or profiles can break release builds at the worst moment.
- Simulator-only testing can miss device-only crashes.
- Data collection declarations often drift from actual SDK behavior.

## Useful Searches

Search for release-readiness terms such as `PRODUCT_BUNDLE_IDENTIFIER`, `MARKETING_VERSION`, `CURRENT_PROJECT_VERSION`, `PrivacyInfo.xcprivacy`, `Info.plist`, `CFBundle`, `Sentry`, `Bugsnag`, `API_KEY`, `SECRET`, `entitlements`, `aps-environment`, `associated-domains`, and `StoreKit`.

## Output

Produce a prelaunch report with four sections:

- App Store assets.
- Technical setup.
- Legal.
- Accounts and signing.

For each item, mark `pass`, `fail`, or `unknown`. Every `fail` or `unknown` must include evidence path or inspected source, impact, and the next concrete action. If an item cannot be verified from the repository alone, state exactly what external artifact is needed.
