# M365 Copilot JS Bundle Reverse Engineering

## Architecture Overview

M365 Copilot is a React + Rspack application loaded from `m365.cloud.microsoft`.
The main bundle (`main.*.js`) contains all core logic, MSAL configuration, authentication flows,
and WebSocket/SignalR communication code.

### Key JS Bundles

| File | Size | Purpose |
|------|------|---------|
| `main.*.js` | ~1MB | Core app: MSAL config, token providers, WebSocket, UI |
| `runtime.*.js` | ~270KB | Rspack runtime, lazy loading |
| `sydney-utils.vendors.*.chunk.js` | ~30KB | Sydney/ChatHub utilities: endpoints, localStorage cache |
| `relay.vendors.*.chunk.js` | ~240KB | GraphQL/Relay client |

## Authentication

### MSAL Configuration

The app uses MSAL.js for OAuth 2.0 + PKCE flow. Key configuration (from module 642122):

```javascript
const authConfig = {
  aadAppId: "4765445b-32c6-49b0-83e6-1d93765276ca",
  aadAuthorityUrl: "https://login.microsoftonline.com/common/",
  officeHomeTokenScope: "https://www.office.com/v2/OfficeHome.All",
  spaRedirectUrlPath: "/spalanding"
};
```

### Client IDs

Two client IDs are used for different scenarios (module 207645):

- **SPA (Single-Page Application)**: `4765445b-32c6-49b0-83e6-1d93765276ca`
  Used for browser-based authentication with PKCE.
  Refresh token lifetime: ~24 hours.
  Requires `response_mode=fragment` with redirect to `https://m365.cloud.microsoft`.

- **Desktop/Native**: `c0ab8ce9-e9a0-42e7-b064-33d422df41f1`
  Used for desktop client applications.
  Refresh token lifetime: ~90 days.
  Uses `https://outlook.office.com/` as registered redirect URI.

### Token Provider System

The app has a factory system (`R` function) that lazily creates token providers
for various Microsoft services. Each provider is identified by a service name:

```javascript
tokenProviders = {
  sydney:        fn() -> accessToken  // M365 Copilot/Sydney
  substrate:     fn() -> accessToken  // Substrate search
  graph:         fn() -> accessToken  // Microsoft Graph
  loki:          fn() -> accessToken  // Delve/Loki
  spo:           fn() -> accessToken  // SharePoint/OneDrive
  powerPlatform: fn() -> accessToken  // Power Platform
  // ... 30+ additional services
};
```

### Token Acquisition Flow

1. App initializes MSAL `PublicClientApplication`
2. For silent renewals, uses `acquireTokenSilent()` via iframes
3. If silent fails, falls back to popup (`MsalTokenPopupView`) or redirect
4. Tokens are stored in `localStorage` under the `msal.` prefix
5. Refresh tokens are persisted in `localStorage` and rotated automatically

## WebSocket / SignalR Protocol

### ChatHub Endpoints

The app connects to ChatHub WebSocket endpoints. Multiple environments are configured:

```javascript
chatHubEndpoints = {
  production:  "wss://substrate.office.com/m365Copilot/Chathub",
  sdf:         "wss://sdf-s01-800-*.substrate.cosmic-ppe.office.net/m365Copilot/Chathub",
  msit:        "wss://msit-s01-001-*.substrate-msit.cosmic.office.net/m365Copilot/Chathub",
  gcch:        "wss://substrate.office365.us/m365Copilot/ChatHub",
  dod:         "wss://substrate-dod.office365.us/m365Copilot/ChatHub"
};
```

The default production endpoint: `wss://substrate.office.com/m365Copilot/Chathub`

### WebSocket URL Format

```
wss://substrate.office.com/m365Copilot/Chathub/{oid}@{tenant}
  ?access_token={token}
  &ConnectionId={uuid}
  &ConversationId={hex}
  &X-Session-Id={uuid}
```

### SignalR Messages

The connection uses the JSON SignalR protocol (`{"protocol":"json","version":1}`):

| Type | Name | Purpose |
|------|------|---------|
| 1 | `update` | Streaming response updates |
| 2 | (StreamItem) | Final stream item with metadata |
| 3 | (Completion) | Stream completion signal |
| 4 | `chat` | Send chat message (invocation) |
| 6 | `keepAlive` | Connection keep-alive ping |

### Content Origin

The app sends a `contentOrigin` header identifying the client type:

```javascript
contentOriginMap = {
  "BCBv2Windows":     "WindowsCopilot",
  "BCBv2Edge":        "Edge",
  "BCBv2CopilotApp":  "CopilotApp",
  "BCBv2CopilotHub":  "CopilotHub",
  "BCBv2Chat":        "Bing",
  "officeweb":        "Office",
  "teamshub":         "Teams",
  "Monarch":          "MonarchHub",
  // etc.
};
```

## Data Persistence

### localStorage Schema

The app stores conversation data in `localStorage`:

```
msal.<client_id>.<account_id>  -> MSAL token cache
copilot.referenceIds           -> Set of conversation reference IDs
copilot.sessionState           -> Current session state
```

Reference IDs are stored as serialized Sets: `JSON.stringify(Array.from(set))`.

## Key Findings for API Integration

1. **No negotiate endpoint required**: The SignalR WebSocket connects directly to ChatHub
2. **Access token goes in URL query**: Not in headers or subprotocol
3. **StreamingMode**: The API uses `"ConciseWithPadding"` for efficient streaming
4. **ConversationId**: Can use any hex string; M365 creates or continues conversations
5. **`response_mode=fragment`** is used by SPA; native clients use `response_mode=query`
6. **PKCE is required**: OAuth 2.0 authorization code with Proof Key for Code Exchange
