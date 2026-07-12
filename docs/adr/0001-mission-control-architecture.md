# ADR-0001: Mission Control Dashboard Architecture

## Status
Accepted

## Context
We are building a Mission Control Dashboard that provides a unified interface for monitoring and managing the AOS (Agentic Operating System) engine. The dashboard needs to display real-time data from various AOS components (pipeline, approvals, memory, sales, health) while maintaining security and separation of concerns.

## Decision

### 1. Odysseus as the Sole Gateway
Odysseus serves as the single gateway between the browser and the AOS engine. This provides:
- **Security**: Single entry point for authentication and authorization
- **Simplified client-side**: Browser only needs to know Odysseus URL
- **Future RBAC**: Easier to implement role-based access control at one layer
- **CORS simplification**: Only Odysseus needs CORS configuration

### 2. AOS Remains the Execution Backend
AOS is not merged into Odysseus because:
- **Separation of concerns**: AOS handles execution, Odysseus handles presentation
- **Independent scaling**: AOS can scale based on execution load
- **Reusability**: AOS API can be consumed by other services (CLI, other dashboards)
- **Testing**: Each component can be tested independently

### 3. WebSocket Proxy Through Odysseus
WebSocket connections are proxied through Odysseus for:
- **Single origin**: Browser connects to one origin, avoiding mixed-content issues
- **Auth-ready**: Token validation happens at Odysseus layer
- **Reverse-proxy compatible**: Works behind corporate firewalls and load balancers
- **Connection pooling**: Odysseus can manage connection lifecycle

### 4. API Ownership Boundaries
- **AOS owns /api/***: All business logic and data aggregation endpoints
- **Odysseus owns UI + proxy**: Frontend serving and WebSocket proxying
- Clear contract: AOS exposes REST/WS APIs, Odysseus consumes them

### 5. Future RBAC Assumptions
Design for multi-user, ship for solo:
- **Current**: Single user with AOS_API_TOKEN authentication
- **Future**: Odysseus will add JWT/OAuth validation before proxying
- **Design**: All endpoints accept optional Authorization header
- **Migration path**: Add user context to AOS requests when RBAC is implemented

### 6. Future Multi-Service Compatibility
AOS is one service, Odysseus can proxy others:
- **Plugin architecture**: Odysseus routes can be registered dynamically
- **Service discovery**: Future services can register with Odysseus
- **Unified dashboard**: Multiple backends visible from one interface

## Consequences

### Positive
- Clear security boundary at Odysseus
- Independent deployment and scaling
- Easy to add new services behind Odysseus
- Browser only deals with one origin

### Negative
- Extra network hop for WebSocket connections
- Odysseus needs to handle WebSocket proxying correctly
- Debugging requires tracing through two layers

### Mitigations
- Use httpx for efficient HTTP proxying
- Implement proper error propagation
- Add comprehensive logging at both layers
