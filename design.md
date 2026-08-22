# Niko The Great - SYNTH NOW — Mobile Interface Design

## Product intent

Synth Now is a mobile production-intelligence companion for musicians, beat makers, and producers. It helps a person move from a song or audio clip to evidence-backed information about instruments, synthesizers, VSTs, presets, gear history, and comparable recorded uses. The interface must make uncertainty visible: an audio similarity result is not presented as a documented recording credit.

## Mobile design principles

The app is designed for **portrait 9:16 use** and one-handed browsing. The principal action—identifying a sound—remains within reach at the bottom of the home screen. Screens use native iOS-style navigation, bottom sheets for short actions, large tap targets, system typography, visible loading states, and clear labels rather than dense producer jargon.

## Screen list

| Screen | Primary content and functionality |
| --- | --- |
| **Today / Discover** | A prominent “Analyze sound” action, recent analyses, trending verified gear, saved items, and short education on evidence labels. |
| **Analyze Audio Sheet** | Upload an authorized clip or select a local stem; show consent, input type, analysis progress, and a cancellation action. |
| **Recognition Result** | Distinct sections for recording match, audio similarity, source-bleed warnings, confidence dimensions, and evidence-backed production claims. |
| **Gear Search** | Search/filter synths, VSTs, presets, drum machines, keys, horns, and effects by maker, era, category, and documented use. |
| **Gear Detail** | Manufacturer/developer link, historical timeline, feature/specification summary, official preset links, verified song uses, non-recording associations, and related gear. |
| **Preset Detail** | Canonical preset metadata, compatible product/version, official acquisition link, rights/access status, sonic tags, and clearly labeled similarity results. |
| **Song / Recording Detail** | Recording version, credits/evidence, verified instruments/gear, confidence, source list, and connected artists. |
| **Library** | Saved gear, presets, analyses, and collections; all sync only after signed-in cloud features are enabled. |
| **Subscription / Account** | Entitlements, restore purchase, manage subscription, privacy choices, authentication status, and email preferences. |

## Primary user flows

### Analyze a sound

1. The user taps **Analyze sound** from Today.
2. The user uploads an authorized clip or stem and confirms its input type.
3. The app creates a private analysis job and shows progress without claiming a result before completion.
4. The result screen separates exact compatible-reference matches from **similarity candidates**.
5. When a separated stem has source bleed, an artifact banner and confidence limit are visible before the user opens detailed matches.
6. The user saves a gear item, opens a documented song use, or follows an official manufacturer/developer link.

### Explore gear and preset history

1. The user searches by sound, product, maker, era, or artist.
2. The search results indicate **verified recording use**, **artist association**, or **similarity** with distinct labels.
3. The user opens Gear Detail to read official history, inspect sources, discover compatible official presets, and browse only source-backed recording uses by default.
4. The user may save the item to a Library collection.

### Subscribe and recover entitlement

1. The user encounters a premium capability only after viewing its scope and price in the native subscription screen.
2. iOS and Android purchase flows use the platform-native subscription implementation.
3. Web subscription checkout can use Stripe through a secure backend endpoint; raw Stripe secrets never reach the mobile app.
4. The subscription confirmation refreshes server-backed entitlement state and emails are sent by the backend through Resend.

## Color choices

The visual system references a dark professional studio rather than a generic SaaS dashboard. The principal background is **Midnight Console `#07111F`**, surfaces are **Slate Booth `#10233B`**, the active audio action is **Signal Cyan `#3CC6FF`**, evidence/verified information is **Reference Green `#4CD3A7`**, historical/curated highlights use **Violet Tape `#A78BFA`**, and uncertainty/source-bleed warnings use **Amber Monitor `#F6B64A`**. Critical error states use **Red Clip `#FF6B7D`**.

## Interaction and accessibility

The app respects dynamic type, high contrast, VoiceOver labels, and reduced motion. Tappable controls are at least 44 points. Result status is conveyed with text plus shape/color, never color alone. Audio analysis must provide a plain-language explanation of why a result is limited, for example: “This is a separated stem with audible source bleed; only similarity candidates are shown.”

## Architecture constraints represented in the UI

The mobile client talks only to a secure API layer. Neon PostgreSQL remains authoritative for claims, entitlements, and metadata. Cloudflare R2 stores authorized private audio uploads and approved artifacts. Cloudflare Workers host the public API/edge path and issue signed R2 upload URLs; Workers do not run heavy Python audio analysis. Stripe and Resend operations run server-side. The old AWS/Kubernetes/Terraform package remains an archival resilience reference and is not the default cost-effective mobile production path.
