# Dubai Property Bot — Brand Identity Guide

## Brand Overview

**Name:** Dubai Property Bot
**Tagline:** AI-Powered Investment Intelligence
**Category:** Real Estate / Fintech / PropTech

---

## Logo Usage

| Asset | File | Usage |
|-------|------|-------|
| Full Logo (Light) | `logo.svg` | Light backgrounds, headers |
| Full Logo (Dark) | `logo-dark.svg` | Dark backgrounds, headers |
| Icon Only | `logo-icon.svg` | Favicons, app icons, small spaces |

### Clear Space
Maintain minimum clear space equal to the height of the "D" in DUBAI around all sides of the logo.

### Minimum Size
- Full logo: 120px width minimum
- Icon only: 24px minimum

---

## Color System

### Primary Palette

| Role | Hex | Usage |
|------|-----|-------|
| Luxury Gold | `#D4AF37` | Primary brand color, CTAs |
| Gold Light | `#E8C84A` | Hover states, highlights |
| Gold Dim | `#B8860B` | Pressed states, depth |
| Rich Black | `#0A0A0A` | Background, exclusivity |

### Neutrals

| Role | Hex | Usage |
|------|-----|-------|
| Rich Black | `#0A0A0A` | Dark mode background |
| Surface | `#1A1A1A` | Cards, panels |
| Muted | `#666666` | Body text |
| Light | `#A0A0A0` | Captions, labels |
| Off White | `#F5F5F5` | Light mode background |

### Semantic

| Role | Hex | Usage |
|------|-----|-------|
| Success/Invest | `#22C55E` | Positive metrics, INVEST badge |
| Warning/Hold | `#EAB308` | Neutral metrics, HOLD badge |
| Danger/Avoid | `#DC2626` | Negative metrics, AVOID badge |

---

## Typography

### Headings — Cinzel
- **Weight:** 400, 500, 600, 700
- **Usage:** Page titles, section headers, hero text
- **CSS:** `font-family: 'Cinzel', serif`

### Body — Josefin Sans
- **Weight:** 300, 400, 500, 600, 700
- **Usage:** Body text, UI labels, data display
- **CSS:** `font-family: 'Josefin Sans', sans-serif`

### Monospace — Geist Mono
- **Usage:** Code, numbers, tabular data
- **CSS:** `font-family: var(--font-geist-mono)`

---

## Design Tokens

### Spacing
```
--space-xs: 4px
--space-sm: 8px
--space-md: 16px
--space-lg: 24px
--space-xl: 32px
--space-2xl: 48px
--space-3xl: 64px
```

### Border Radius
```
--radius-sm: 6px
--radius-md: 8px
--radius-lg: 12px
--radius-xl: 16px
--radius-2xl: 24px
```

### Shadows
```
--shadow-sm: 0 1px 2px rgba(0,0,0,0.05)
--shadow-md: 0 4px 6px rgba(0,0,0,0.1)
--shadow-lg: 0 10px 15px rgba(0,0,0,0.1)
--shadow-xl: 0 20px 25px rgba(0,0,0,0.15)
```

---

## Glassmorphism Effects

### Glass Card
```css
background: rgba(255, 255, 255, 0.7);
backdrop-filter: blur(16px);
border: 1px solid rgba(255, 255, 255, 0.2);
box-shadow: 0 8px 32px rgba(15, 118, 110, 0.08);
```

### Glass Navigation (Dark)
```css
background: rgba(15, 23, 42, 0.95);
backdrop-filter: blur(20px);
border-right: 1px solid rgba(20, 184, 166, 0.1);
```

---

## Icon Set

Custom SVG icons located in `icons/`:

| Icon | File | Usage |
|------|------|-------|
| Building | `building.svg` | Properties, communities |
| Property | `property.svg` | Listings, cards |
| Yield Chart | `yield-chart.svg` | Returns, performance |
| Market Clock | `market-clock.svg` | Trends, timing |
| Layers | `layers.svg` | Scoring, metrics |
| Location Pin | `location-pin.svg` | Map, geography |
| Dashboard | `dashboard.svg` | Overview, home |
| Currency | `currency.svg` | Price, AED |
| User Plus | `user-plus.svg` | Account, signup |
| Trophy | `trophy.svg` | Leaderboard, ranking |

### Icon Guidelines
- Stroke width: 1.5px consistent
- Size: 24x24 default, scale proportionally
- Color: inherit from parent (use `currentColor`)
- Style: outlined/linear

---

## Banner Assets

| Asset | Dimensions | File |
|-------|-----------|------|
| Website Hero | 1920 x 800 | `banner-hero-1920x800.html` |
| Social/OG | 1200 x 630 | `banner-social-1200x630.html` |
| Instagram Story | 1080 x 1920 | `banner-story-1080x1920.html` |

### Banner Design Rules
- Safe zones: critical content in central 70-80%
- One CTA per banner
- Max 2 fonts (Cinzel + Josefin Sans)
- Min 16px body, 32px+ headline
- Teal gradient primary, dark navy background

---

## Anti-Patterns

- Do NOT use emojis as icons
- Do NOT use low-contrast text (< 4.5:1)
- Do NOT skip hover/focus transitions
- Do NOT use random spacing — follow the spacing scale
- Do NOT hardcode colors — use design tokens

---

## Interactive Brand Book

For the complete interactive brand guidelines, open `brand-book.html` in a browser.

The brand book includes:
- Brand Overview, Mission & Values
- Logo System (variants, clear space, minimum sizes)
- Color Palette (primary, neutral, semantic)
- Typography (Cinzel, Josefin Sans, Geist Mono)
- Iconography (10 custom SVG icons)
- Spacing & Design Tokens
- Glassmorphism Effects
- Imagery Guidelines
- Stationery Mockups (business card, letterhead, email signature)
- Digital Applications (website hero, social media)
- Do's & Don'ts
- Voice & Tone
- Data Visualization Standards
- Motion & Animation Guidelines
- Accessibility Requirements
- File Naming Conventions

## File Structure

```
brand/
├── logo.svg              # Full logo (light bg)
├── logo-dark.svg         # Full logo (dark bg)
├── logo-icon.svg         # Icon only
├── BRAND-IDENTITY.md     # This file (markdown)
├── brand-book.html       # Interactive brand book
├── showcase.html         # Brand showcase page
├── icons/                # Custom SVG icon set
│   ├── building.svg
│   ├── currency.svg
│   ├── dashboard.svg
│   ├── layers.svg
│   ├── location-pin.svg
│   ├── market-clock.svg
│   ├── property.svg
│   ├── trophy.svg
│   ├── user-plus.svg
│   └── yield-chart.svg
├── banner-hero-1920x800.html
├── banner-social-1200x630.html
└── banner-story-1080x1920.html
```
