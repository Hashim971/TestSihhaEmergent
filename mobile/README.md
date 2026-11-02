# Sihha AI — iPhone & Android apps

These are native shells (Capacitor) around the Sihha web app, so every feature, hospital branding and
language setting works exactly as on the web. Updates to the web app reach the phone apps instantly.

## 1. Test today (no store, no accounts)
- **Any phone:** open the app address in Safari (iPhone) or Chrome (Android) → Share / menu → *Add to Home Screen*.
  It opens full-screen like a native app.

## 2. Android test file (.apk)
1. In the chat input use **Save to GitHub** to push this project.
2. On GitHub: **Actions → Mobile test builds → Run workflow**, enter your app address (https://…).
3. When it finishes (~8 min), download **sihha-android-test-apk** and open it on an Android phone
   (allow "install unknown apps" once).

## 3. iPhone test build
- The same workflow produces **sihha-ios-simulator-build** (runs in the Xcode simulator on a Mac).
- To install on a real iPhone, Apple requires a signed build: join the Apple Developer Program ($99/yr),
  open `ios/App/App.xcworkspace` in Xcode on a Mac (`npm install && npm run ios`), pick your team,
  then **Product → Archive → Distribute → TestFlight**. Testers install it with the TestFlight app.

## 4. Store submission
| | Google Play | Apple App Store |
|---|---|---|
| Account | Play Console ($25 once) | Apple Developer ($99/yr) |
| Build | `cd android && ./gradlew bundleRelease` (signed .aab) | Xcode Archive |
| Listing text | `store/listing.md` | `store/listing.md` |
| Icon | `../frontend/public/icon-512.png` | same (1024px source in design assets) |
| Privacy | Health data: declare in Data safety form | App Privacy "Health & Fitness" |

Note: Apple reviews apps that only wrap a website more strictly (guideline 4.2). Sihha's offline screen,
installable icon and native shell help; adding push notifications or camera access natively is the
usual next step if review asks for more native functionality.
