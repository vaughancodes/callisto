# Callisto Frontend

React + TypeScript + Vite dashboard for the Callisto telephony intelligence platform.

## Tech Stack

- **React 19** with TypeScript
- **Vite** (dev server on port 5308)
- **Tailwind CSS v4** with custom theme tokens
- **React Router** for client-side routing
- **TanStack React Query** for data fetching and caching
- **Recharts** for analytics charts
- **Lucide React** for icons

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on port 5308 with API proxy to `localhost:5309`.

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/login` | LoginPage | Animated logo + Google OAuth sign-in |
| `/auth/callback` | AuthCallbackPage | Handles OAuth redirect, stores JWT |
| `/` | DashboardPage | Recent calls list + live insights feed via WebSocket |
| `/calls/:callId` | CallDetailPage | Transcript, insights, summary, notes |
| `/contacts` | ContactsPage | Contact list, search, CSV import, Google sync |
| `/contacts/:contactId` | ContactDetailPage | Contact calls, sentiment breakdown, topics, notes |
| `/templates` | TemplatesPage | Insight template CRUD |
| `/analytics` | AnalyticsPage | Insight trends chart over time |
| `/admin` | AdminPage | Superadmin: tenant/user management |

## Project Structure

```
frontend/
├── public/
│   ├── callisto-icon-animated.svg
│   ├── callisto-icon-static.svg        # favicon
│   ├── callisto-logo-animated-dark.svg  # login page (dark bg)
│   ├── callisto-logo-animated-light.svg # login page (light bg)
│   ├── callisto-logo-dark.svg
│   ├── callisto-logo-light.svg
│   ├── callisto-logo-rect.svg
│   ├── callisto-wordmark-dark.svg       # sidebar
│   └── callisto-wordmark-light.svg
├── src/
│   ├── main.tsx                # App entry point (providers: Router, Query, Auth, Theme)
│   ├── App.tsx                 # Route definitions
│   ├── index.css               # Tailwind + theme tokens
│   ├── contexts/
│   │   ├── AuthContext.tsx      # JWT auth state, Google login/logout
│   │   └── ThemeContext.tsx     # Light/dark mode toggle, persists to localStorage
│   ├── hooks/
│   │   └── useWebSocket.ts     # Real-time insight stream from broadcaster
│   ├── lib/
│   │   ├── api.ts              # Fetch wrapper with JWT auth
│   │   └── format.ts           # Date/time, status, sentiment formatters
│   ├── components/
│   │   ├── CallListItem.tsx    # Expandable call row (summary, notes, topics)
│   │   ├── LinkedContact.tsx   # PhoneLink (tel:) and EmailLink (mailto:)
│   │   └── ProtectedRoute.tsx  # Auth guard
│   ├── layouts/
│   │   └── DashboardLayout.tsx # Sidebar + main content
│   └── pages/
│       ├── LoginPage.tsx
│       ├── AuthCallbackPage.tsx
│       ├── DashboardPage.tsx
│       ├── CallDetailPage.tsx
│       ├── ContactsPage.tsx
│       ├── ContactDetailPage.tsx
│       ├── TemplatesPage.tsx
│       ├── AnalyticsPage.tsx
│       └── AdminPage.tsx
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Color Palette

The Callisto brand palette is defined as CSS custom properties in `src/index.css` and available as Tailwind classes.

### Accent Colors (same in both modes)

Used sparingly for interactive elements, status indicators, and the brand mark. Never for body text.

| Name | Hex | Tailwind Class | Usage |
|------|-----|----------------|-------|
| Sky Blue | `#0ea5e9` | `text-brand-sky` / `bg-brand-sky` | Primary buttons, links, active states |
| Indigo | `#6366f1` | `text-brand-indigo` / `bg-brand-indigo` | Hover states, secondary accents |
| Light Sky | `#38bdf8` | `text-accent-light` / `bg-accent-light` | Notification badges, active indicators |
| Periwinkle | `#818cf8` | `text-accent-periwinkle` / `bg-accent-periwinkle` | Selected states, focus rings |
| Lavender | `#a78bfa` | `text-accent-lavender` / `bg-accent-lavender` | Tertiary accents, tags |

**Brand gradient:** `linear-gradient(135deg, #0ea5e9, #6366f1)` — used on the login page background and hero elements.

### Semantic Colors (same in both modes)

| Name | Hex | Tailwind Class | Usage |
|------|-----|----------------|-------|
| Success | `#4ade80` | `text-success` / `bg-success` | Positive indicators, completed |
| Warning | `#fbbf24` | `text-warning` / `bg-warning` | Caution, pending |
| Danger | `#f87171` | `text-danger` / `bg-danger` | Errors, critical insights |
| Info | `#38bdf8` | `text-info` / `bg-info` | Informational badges |

### Dark Mode

| Token | Hex | Tailwind Class | Usage |
|-------|-----|----------------|-------|
| Background primary | `#0c0e13` | `bg-page-bg` | Page background |
| Background secondary | `#13161d` | `bg-page-bg-secondary` / `bg-card-bg` | Cards, elevated surfaces |
| Background tertiary | `#1a1e28` | `bg-page-bg-tertiary` | Inputs, dropdowns |
| Border | `#252a36` | `border-card-border` / `border-page-divider` | Borders, dividers |
| Border hover | `#333338` | `border-card-border-hover` | Borders on hover |
| Text primary | `#c9d1d9` | `text-page-text` | Headings, body text |
| Text secondary | `#94a3b8` | `text-page-text-secondary` | Subtitles, labels |
| Text muted | `#64748b` | `text-page-text-muted` | Placeholders, timestamps |

### Light Mode

| Token | Hex | Tailwind Class | Usage |
|-------|-----|----------------|-------|
| Background primary | `#ffffff` | `bg-page-bg` | Page background |
| Background secondary | `#f8fafc` | `bg-page-bg-secondary` / `bg-card-bg` | Cards, elevated surfaces |
| Background tertiary | `#f1f5f9` | `bg-page-bg-tertiary` | Inputs, dropdowns |
| Border | `#e2e8f0` | `border-card-border` / `border-page-divider` | Borders, dividers |
| Border hover | `#cbd5e1` | `border-card-border-hover` | Borders on hover |
| Text primary | `#0f172a` | `text-page-text` | Headings, body text |
| Text secondary | `#475569` | `text-page-text-secondary` | Subtitles, labels |
| Text muted | `#94a3b8` | `text-page-text-muted` | Placeholders, timestamps |

### Sidebar (always dark)

The sidebar uses dark palette colors directly (not theme tokens) so it stays dark in both modes:

- Background: `#0c0e13` (light mode) / `#13161d` (dark mode)
- Borders: `#252a36`
- Inactive nav text: `#94a3b8` → `#e2e8f0` on hover
- Active nav: `#38bdf8` (accent-light)
- User name: `#e2e8f0`
- Muted text: `#64748b`

### Theme Toggle

Light/dark mode is toggled via the sun/moon icon in the sidebar footer. The preference is persisted to `localStorage` and defaults to the OS preference on first visit. The toggle adds/removes the `dark` class on `<html>`, which swaps the CSS custom properties defined in `index.css`.

## Authentication

The frontend uses JWT tokens stored in `localStorage`:

1. User clicks "Sign in with Google" → redirects to `/auth/google/login`
2. Google OAuth flow → backend issues JWT → redirects to `/auth/callback?token=...`
3. `AuthCallbackPage` stores the token and redirects to `/`
4. All API calls include `Authorization: Bearer <token>` via the `apiFetch` wrapper
5. On 401 response, token is cleared and user is redirected to `/login`

The Google access token is also stored (for Google Contacts sync).

## Real-time Updates

The `useInsightStream` hook connects to the broadcaster WebSocket at `/ws/calls/live` (or `/ws/calls/:id/live` for a specific call). Insights arrive as JSON messages and are displayed in the live feed on the dashboard and as "Live" badges on the call detail page.

The call list on the dashboard auto-refreshes every 10 seconds via React Query.
