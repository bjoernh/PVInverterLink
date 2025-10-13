# Deye Hard - System Requirements Document

**Version**: 1.0
**Date**: January 2025
**Status**: Beta Phase
**Maintained by**: WTF Kooperative eG

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Background & Security Context](#background--security-context)
3. [Project Team & Partners](#project-team--partners)
4. [Project Goals](#project-goals)
5. [System Architecture](#system-architecture)
6. [Functional Requirements](#functional-requirements)
7. [Non-Functional Requirements](#non-functional-requirements)
8. [Hardware Compatibility](#hardware-compatibility)
9. [Data Requirements](#data-requirements)
10. [User Requirements](#user-requirements)
11. [Deployment & Operations](#deployment--operations)
12. [Compliance & Legal](#compliance--legal)
13. [Technical Debt & Known Issues](#technical-debt--known-issues)
14. [Development Roadmap](#development-roadmap)
15. [Out of Scope](#out-of-scope)
16. [Success Criteria](#success-criteria)
17. [References & Resources](#references--resources)
18. [Glossary](#glossary)

---

## Executive Summary

### Mission Statement

Deye Hard provides a privacy-safe, GDPR-compliant alternative to the manufacturer cloud for Deye solar inverters and compatible devices. The system replaces the insecure Solarman cloud infrastructure with an open-source, EU-hosted monitoring platform that respects user privacy and prevents unauthorized remote access to inverters.

### The Problem

In September 2023, a security analysis revealed critical vulnerabilities in the Deye/Solarman cloud infrastructure:

- Unencrypted back channel allowing remote control of inverters
- Remote password extraction (WiFi credentials, web interface)
- Geolocation tracking via BSSID scanning
- Remote inverter manipulation (power limiting, forced shutdown)
- Potential to disable safety features (island protection)
- Data transmission to servers in China without user consent or transparency

These vulnerabilities affect Deye inverters and their rebrands (Bosswerk, revolt), as well as other manufacturers using IGEN Tech/Solarman data loggers (Omnik, Ginlong/Solis, Sofar).

### The Solution

A two-component system:

1. **Backend/WebApp**: User and inverter registration, multi-tenant data management, web dashboard
2. **Collector**: High-performance Rust-based TCP server for real-time telemetry collection

**Key Principles**:
- **Privacy First**: EU-hosted (Germany), GDPR-compliant, transparent data handling
- **No Control**: Never send control signals to user inverters
- **Open Source**: AGPL-3.0 licensed, community-driven development
- **User Friendly**: Simple setup requiring only parameter changes (no firmware modification)
- **Free Access**: No subscription fees, optional donations to cover server costs

### Target Scale

- **Users**: 100 concurrent users (initial phase)
- **Inverters**: ~500 total devices
- **User Profile**: Private homeowners with 1-2 inverters per household
- **Business Model**: Free community service, self-funded by WTF Kooperative eG

### Project Status

Currently in beta testing phase. Core functionality implemented and operational. Seeking testers via https://solar.wtf.coop.

---

## Background & Security Context

### BSI Security Analysis (September 2023)

A comprehensive security analysis documented in `collector-rust/bsi-bericht.tex` identified the following vulnerabilities in the Deye/Solarman ecosystem:

#### Data Logger Vulnerabilities (Remote Access)

The Solarman cloud has unrestricted access to data logger AT+ commands without authentication:

| Command | Capability | Risk Level |
|---------|-----------|-----------|
| `AT+WSKEY` | Read/write WiFi passwords | Critical |
| `AT+WEBU` | Read/write web interface credentials | Critical |
| `AT+WSCAN` | Scan surrounding WiFi networks (SSID, BSSID) | High |
| `AT+WSLK` | Read connected network details | High |
| `AT+WAP` | Modify internal access point settings | High |
| `AT+WAKEY` | Read/write access point password | High |
| `AT+WALK` | List connected client MAC addresses | Medium |
| `AT+WANN` | Read network configuration (IP, gateway, DNS) | Medium |
| `AT+KEY` | Read/modify authentication key | High |
| `AT+WMODE` | Enable/disable access point | Medium |

#### Inverter Control Vulnerabilities (Modbus)

Critical inverter registers accessible via Modbus over cloud connection:

| Register | Function | Manipulation Possible |
|----------|----------|----------------------|
| 40 | Power Regulation | Limit output 1-100% |
| 43 | Enable/Disable | Force shutdown |
| 46 | Island Protection | Disable safety feature |
| 49 | Load Reduction | Disable grid stabilization |

**Verified Attack**: Successful remote shutdown demonstrated on SUN300G3-EU-230 inverter with measured power reduction.

#### Privacy & Data Protection Issues

- Unencrypted TCP connection to Solarman servers in China
- No user consent for data transmission
- No transparency on data retention, access, or sharing
- BSSID scanning enables geolocation of private homes
- Potential for database of georeferenced WiFi credentials
- GDPR compliance highly questionable

#### Affected Hardware

- **Primary**: Deye micro-inverters and rebrands (Bosswerk, revolt)
- **Data Loggers**: IGEN Tech/Solarman V5 protocol devices
- **Other Manufacturers**: Omnik, Ginlong (Solis), Sofar (use same data loggers)

### Project Genesis

The Deye Hard project originated from a collaboration between WTF Kooperative eG and Mittelstand-Digital Zentrum Schleswig-Holstein (MDZ-SH) to investigate data transmission behavior of Deye micro-inverters. The reverse-engineering of the proprietary Solarman V5 protocol led to the development of a replacement monitoring solution.

Current beta testing is self-funded by WTF Kooperative eG.

---

## Project Team & Partners

### Core Team

**WTF Kooperative eG** - Werkkooperative der Technikfreund*innen

A cooperative dedicated to economically supporting its members through collaborative technology projects.

**Active Members**:
- **brain**: Security analysis, protocol reverse-engineering, PoC Collector 
- **gnibeil**: Website, Support
- **bj0ern**: Backend development, PO

Team composition: Balcony solar enthusiasts, physicists, computer scientists, coders, hobbyists.

### Historical Context

- **Initial Development**: Partnership with Mittelstand-Digital Zentrum Schleswig-Holstein (MDZ-SH)
- **Current Phase**: Self-funded beta testing by WTF Kooperative eG

### Planned Partners

- **Regional NGOs**: Collaboration with organizations like Balkon Solar e.V.

---

## Project Goals

### Primary Objectives

1. **Make Deye Inverters Privacy-Safe**
   - Eliminate unauthorized data transmission to manufacturer cloud
   - Prevent remote access and control by third parties
   - Ensure GDPR-compliant data handling
   - Provide transparency on data collection and usage

2. **Provide User-Friendly Solution**
   - Simple setup process for non-technical users
   - No firmware modifications required
   - Clear documentation and guidance
   - Reliable, maintenance-free operation

3. **Ensure Transparency**
   - Open-source codebase (AGPL-3.0)
   - Public documentation of security measures
   - Clear privacy policy and terms of service
   - Community-driven development

4. **Prevent Inverter Control**
   - Never send control signals to user inverters
   - Read-only monitoring architecture
   - No Modbus write operations
   - User maintains full ownership and control

5. **Remain Accessible**
   - Free service for all users
   - Optional donations to support server costs
   - No subscription fees or paywalls
   - Community support model

### Success Metrics

- Users can monitor inverters without manufacturer cloud
- No BSI-identified vulnerabilities present in system
- GDPR compliance verified
- Positive user feedback from beta testers
- Active community participation

---

## System Architecture

### Overview

Deye Hard consists of three main components working together to provide secure, multi-tenant solar monitoring:

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Inverter  │────────▶│ Data Logger  │────────▶│  Collector  │
│  (Deye/etc) │ Serial  │  (Solarman)  │   TCP   │   (Rust)    │
└─────────────┘         └──────────────┘  10000  └─────────────┘
                                                         │
                                                         ▼
                                                   ┌─────────────┐
                     ┌──────────────────────────▶ │  InfluxDB   │
                     │                             │  (Per-User  │
┌─────────────┐     │ Auth/Config                 │   Buckets)  │
│    User     │────▶│                             └─────────────┘
│  (Browser)  │     │
└─────────────┘     ▼
              ┌─────────────┐      ┌──────────────┐
              │   Backend   │─────▶│  PostgreSQL  │
              │  (FastAPI)  │      │ (User/Meta)  │
              └─────────────┘      └──────────────┘
```

### Component 1: Backend/WebApp

**Technology**: FastAPI (Python 3.13+), HTMX, Jinja2
**Purpose**: User management, inverter registration, InfluxDB orchestration, web dashboard

**Key Features**:
- User registration with email verification
- Multi-tenant InfluxDB organization management
- Inverter CRUD operations with automatic bucket provisioning
- SQLAdmin interface for system administration
- RESTful API endpoints for collector authentication
- CSRF protection and rate limiting
- Structured logging (structlog)

**Databases**:
- PostgreSQL: User accounts, inverter metadata, relationships
- InfluxDB: Per-user organizations, per-inverter buckets

**Hosting**: Germany (EU)

### Component 2: Collector (solarman-collector)

**Technology**: Rust (Tokio async runtime)
**Purpose**: High-performance TCP server for real-time telemetry ingestion

**Key Features**:
- Solarman V5 protocol decoder
- JWT-based authentication with backend
- Per-logger credential caching (reduces backend load)
- Automatic token refresh (30-second buffer before expiration)
- Direct InfluxDB writes using per-user credentials
- Concurrent connection handling (Tokio)
- Structured logging (tracing)

**Protocol Support**:
- Solarman V5 (current)
- OpenDTU (planned)
- MQTT (planned)

**Port**: 10000/tcp (configurable)

### Component 3: Data Storage

#### PostgreSQL (Relational Database)

**Models**:
- **User**: Authentication, profile, InfluxDB credentials
- **Inverter**: Serial number, bucket ID, metadata (rated power, MPPT count)

**Relationships**:
- One user → many inverters
- Cascade deletion for data integrity

**Migrations**: Alembic for version control

#### InfluxDB 2.x (Time-Series Database)

**Multi-Tenant Architecture**:
- One organization per user (named by email)
- One bucket per inverter (within user's organization)
- User-specific authorization tokens (bucket read/write only)
- Strict data isolation (no cross-user queries possible)

**Measurements**:
| Measurement | Fields | Tags | Update Frequency |
|-------------|--------|------|------------------|
| `uptime` | power_on_time, total_working_time, offset_time | logger_serial | 60s |
| `yield` | daily, total | inverter_serial | 60s |
| `grid` | voltage (3-phase), current (3-phase), power (3-phase), frequency, total_output_power | inverter_serial | 60s |
| `string_production` | voltage, current | logger_serial, inverter_serial, string | 60s |
| `string_yield` | daily, total | logger_serial, inverter_serial, string | 60s |

**Data Retention**: 2 years (configurable per bucket)

---

## Functional Requirements

Status Legend:
- ✅ **Implemented**: Currently operational in production
- 🔄 **In Progress**: Partially implemented or under active development
- 📋 **Planned**: Committed to roadmap
- 💡 **Future**: Long-term vision, not yet committed

### ✅ User Management (Implemented)

#### REQ-UM-001: User Registration
**Priority**: Critical
**Status**: ✅ Implemented

Users shall be able to register accounts by providing:
- First name (required, max 32 characters)
- Last name (required, max 32 characters)
- Email address (required, unique, valid format)
- Password (required, validation rules applied)

**Acceptance Criteria**:
- Duplicate email addresses rejected with clear error message
- Invalid email addresses rejected (SMTP validation)
- Password validation enforced (see REQ-SEC-002)
- Verification email sent automatically upon successful registration

**Implementation**: `api/signup.py:43-80`

#### REQ-UM-002: Email Verification
**Priority**: Critical
**Status**: ✅ Implemented

Users shall verify email addresses before accessing full functionality.

**Process**:
1. User receives verification email with JWT token link
2. User clicks link, token validated
3. User marked as verified in database
4. InfluxDB organization, user, and token created automatically
5. User automatically logged in (cookie set)

**Security**:
- Encrypted temporary password stored during registration
- Decrypted only during verification process
- Immediately deleted after InfluxDB setup (encrypt-then-delete pattern)

**Acceptance Criteria**:
- Verified users can add inverters
- Unverified users blocked from inverter registration
- Invalid/expired tokens handled gracefully
- InfluxDB setup failures logged, user still marked verified

**Implementation**: `api/signup.py:82-99`, `users.py:59-99`

#### REQ-UM-003: User Authentication
**Priority**: Critical
**Status**: ✅ Implemented

Users shall authenticate via email and password.

**Authentication Methods**:
1. **Cookie-based** (web UI): Session management with secure cookies
2. **Bearer token** (API): JWT in Authorization header

**JWT Configuration**:
- Algorithm: HS256
- Secret: `AUTH_SECRET` environment variable
- Lifetime: 2 days (172,800 seconds)
- Claims: user_id, email, is_active, is_verified, is_superuser

**Rate Limiting**:
- Login attempts: 5 per minute per IP
- Failed logins logged for security monitoring

**Acceptance Criteria**:
- Valid credentials grant access with appropriate token
- Invalid credentials return clear error message
- Rate limiting prevents brute force attacks
- Logout clears authentication tokens

**Implementation**: `api/login.py:31-65`, `users.py:118-143`

#### REQ-UM-004: Password Reset
**Priority**: High
**Status**: ✅ Implemented

Users shall reset forgotten passwords via email.

**Process**:
1. User requests password reset (email address required)
2. JWT token generated and emailed
3. User clicks link, enters new password (twice for confirmation)
4. Password validated and updated

**Rate Limiting**: 5 requests per hour per IP

**Acceptance Criteria**:
- Reset email sent to registered address only
- Token expires after reasonable time
- New password meets validation requirements
- Invalid tokens handled gracefully

**Implementation**: `api/login.py:68-111`

#### REQ-UM-005: Account Management
**Priority**: High
**Status**: ✅ Implemented

Users shall manage their account settings.

**Capabilities**:
1. **Change Email**: Update email address (requires re-verification)
2. **Change Password**: Update password (requires current password, updates both PostgreSQL and InfluxDB)
3. **Delete Account**: Permanently delete account and all associated data

**Rate Limiting**:
- Email change: 5 per hour per IP
- Password change: 5 per hour per IP
- Account deletion: 3 per hour per IP

**Acceptance Criteria**:
- Email changes require verification of new address
- Password changes require current password confirmation
- Account deletion requires password confirmation
- Deletion removes all user data (PostgreSQL + InfluxDB buckets + organization)

**Implementation**: `api/account.py`

### ✅ Inverter Management (Implemented)

#### REQ-INV-001: Inverter Registration
**Priority**: Critical
**Status**: ✅ Implemented

Verified users shall register inverters by providing:
- Inverter name (user-friendly label)
- Serial logger number (unique identifier from data logger)

**Authorization**: Unverified users blocked from registration

**Process**:
1. Validate user is verified and has InfluxDB credentials
2. Create inverter record in PostgreSQL
3. Validate serial number uniqueness (database constraint)
4. Create dedicated InfluxDB bucket in user's organization
5. Store bucket ID in inverter record

**Rollback Strategy**: If InfluxDB bucket creation fails, inverter record deleted from PostgreSQL (maintain consistency)

**Acceptance Criteria**:
- Serial numbers globally unique across all users
- Each inverter gets dedicated InfluxDB bucket
- Unverified users receive clear error message
- Failed bucket creation rolls back database changes

**Implementation**: `api/inverter.py:60-152`

#### REQ-INV-002: Inverter Dashboard
**Priority**: High
**Status**: ✅ Implemented

Users shall view list of registered inverters with current status.

**Displayed Information**:
- Inverter name
- Serial logger number
- Current power output (watts)
- Last update timestamp (relative format, e.g., "vor 5 Minuten")

**Data Source**: Latest InfluxDB measurement from grid.total_output_power field

**Query Details**:
- Time range: Last 24 hours
- Aggregation: 5-minute moving average over 10-minute period
- Measurement: `grid`
- Field: `total_output_power`

**Acceptance Criteria**:
- Dashboard loads in < 2 seconds
- "No current values" message if no data in 24 hours
- Timestamps in German locale (humanized)
- Current power displayed as integer watts or "-"

**Implementation**: `api/start.py:22-35`, `inverter.py:27-37`

#### REQ-INV-003: Inverter Deletion
**Priority**: Medium
**Status**: ✅ Implemented

Users shall delete registered inverters.

**Process**:
1. Delete inverter record from PostgreSQL
2. Delete InfluxDB bucket
3. Commit transaction

**Error Handling**: PostgreSQL deletion proceeds even if InfluxDB cleanup fails (orphaned buckets cleaned manually)

**Acceptance Criteria**:
- Inverter removed from user's dashboard
- All telemetry data in bucket deleted
- InfluxDB failures logged but don't block deletion

**Implementation**: `api/inverter.py:155-188`

#### REQ-INV-004: External Inverter Authentication
**Priority**: Critical
**Status**: ✅ Implemented

External data loggers shall authenticate and retrieve InfluxDB credentials.

**Endpoint**: `GET /influx_token?serial={logger_serial}`
**Authentication**: Bearer token (superuser only)
**Purpose**: Collector service authenticates to retrieve per-inverter credentials

**Response**:
```json
{
  "serial": "string",
  "token": "string",
  "bucket_id": "string",
  "bucket_name": "string",
  "org_id": "string",
  "is_metadata_complete": boolean
}
```

**Acceptance Criteria**:
- Only superuser accounts can access endpoint
- Returns 404 if serial number not found
- Credentials valid for writing to InfluxDB bucket

**Implementation**: `api/inverter.py:191-221`

### ✅ Data Collection (Implemented)

#### REQ-DC-001: Solarman V5 Protocol Support
**Priority**: Critical
**Status**: ✅ Implemented

System shall decode and process Solarman V5 protocol packets.

**Supported Message Types**:
- Hello Message: Brand, firmware version
- Hello End Message: Connection establishment completion
- Heartbeat: Keep-alive signal
- Primary Update: Inverter telemetry (main data)
- Secondary Update: Logger telemetry

**Protocol Details**:
- Control codes implemented: `control_codes.rs`
- Packet validation and decoding: `protocol/packet.rs`
- High-level decoders: `protocol/decoder.rs`
- Deye-specific (0x5408) format: `protocol/decoder_5408.rs`

**Acceptance Criteria**:
- Valid packets decoded successfully
- Invalid packets logged and rejected
- All message types handled appropriately

**Implementation**: `collector-rust/src/protocol/`

#### REQ-DC-002: Real-Time Data Ingestion
**Priority**: Critical
**Status**: ✅ Implemented

System shall collect telemetry data every 60 seconds.

**Data Flow**:
1. Data logger connects to collector TCP server (port 10000)
2. Collector validates serial number with backend API
3. Backend returns user's InfluxDB credentials
4. Collector caches credentials (reduce backend load)
5. Collector writes telemetry to user's InfluxDB bucket
6. Process repeats every 60 seconds

**Collected Metrics** (per 60-second interval):
- Uptime counters (power-on time, working time, offset)
- Energy yield (daily and total, per inverter)
- Grid parameters (voltage, current, power per phase; frequency)
- String production (voltage, current per string)
- String yield (daily and total per string)

**Acceptance Criteria**:
- Data collected every 60 seconds (±5 seconds tolerance)
- No data loss during normal operation
- Failed writes logged and retried
- Credentials cached for performance

**Implementation**: `collector-rust/src/server/`, `storage/influx.rs`

#### REQ-DC-003: Backend Authentication
**Priority**: Critical
**Status**: ✅ Implemented

Collector shall authenticate with backend to retrieve inverter credentials.

**Authentication Flow**:
1. Collector obtains JWT token from backend (`/auth/jwt/login`)
2. Token cached and reused until expiration
3. Token automatically refreshed 30 seconds before expiration
4. Token used to authenticate `/influx_token` requests

**JWT Configuration**:
- Username: `BACKEND_USER` environment variable
- Password: `BACKEND_PASSWORD` environment variable
- Token lifetime: 2 days
- Refresh buffer: 30 seconds

**Acceptance Criteria**:
- Collector starts without manual token provisioning
- Token refresh transparent to data collection
- Authentication failures logged clearly

**Implementation**: `collector-rust/src/backend/auth.rs`

#### REQ-DC-004: Credential Caching
**Priority**: High
**Status**: ✅ Implemented

Collector shall cache inverter credentials to reduce backend load.

**Cache Strategy**:
- Logger info cached after first successful retrieval
- Cache invalidated on authentication errors (e.g., bucket deleted)
- No expiration time (credentials rarely change)

**Acceptance Criteria**:
- Backend only queried once per logger (after initial connection)
- Cache hit rate > 99% for established connections
- Stale credentials detected and refreshed

**Implementation**: `collector-rust/src/backend/cache.rs`

### ✅ Administration (Implemented)

#### REQ-ADM-001: Admin Interface
**Priority**: High
**Status**: ✅ Implemented

Superusers shall access admin interface for system management.

**Access**: `/admin` (requires superuser flag)

**Features**:
- User management (view, search, sort)
- Inverter management (view, search, sort, create)
- Custom authentication (JWT with 8-hour session)

**User Admin View**:
- Columns: ID, Email, Last Name
- Searchable: Email, Last Name
- Sortable: ID, Email
- Hidden: hashed_password

**Inverter Admin View**:
- Columns: ID, Name
- Searchable: Name
- Sortable: ID, Name
- Auto-creates InfluxDB bucket on creation

**Acceptance Criteria**:
- Only superusers can access interface
- Sessions expire after 8 hours
- Inverter creation via admin creates buckets automatically

**Implementation**: `app.py:66`, `utils/admin_auth.py`, `users.py:144-151`, `inverter.py:41-54`

### ✅ Security (Implemented)

#### REQ-SEC-001: Multi-Tenant Data Isolation
**Priority**: Critical
**Status**: ✅ Implemented

System shall ensure strict data isolation between users.

**Implementation**:
- Each user has dedicated InfluxDB organization
- Each inverter has dedicated bucket within user's organization
- User-specific authorization tokens (no cross-org access)
- PostgreSQL foreign keys enforce user-inverter relationships

**Acceptance Criteria**:
- Users cannot access other users' data
- InfluxDB queries scoped to user's organization
- Token permissions limited to user's buckets
- Database constraints prevent unauthorized associations

**Implementation**: `db.py`, `inverter.py:15-25`, `users.py:59-99`

#### REQ-SEC-002: Password Security
**Priority**: Critical
**Status**: ✅ Implemented

System shall enforce strong password requirements.

**Validation Rules**:
- Minimum 8 characters
- At least 1 digit
- At least 1 uppercase letter
- Not in common password list (password, 123456, 12345678, qwerty)

**Storage**:
- PostgreSQL: bcrypt hashed (via fastapi-users)
- InfluxDB: Native InfluxDB password storage
- Temporary: Fernet encrypted in `tmp_pass` field (encrypt-then-delete)

**Acceptance Criteria**:
- Weak passwords rejected with clear reason
- Passwords never stored in plaintext
- Temporary passwords deleted after verification

**Implementation**: `users.py:33-52`

#### REQ-SEC-003: Rate Limiting
**Priority**: High
**Status**: ✅ Implemented

System shall rate limit requests to prevent abuse.

**Limits**:
| Endpoint | Limit | Scope |
|----------|-------|-------|
| POST /signup | 3/hour | Per IP |
| POST /login | 5/minute | Per IP |
| POST /request_reset_passwort | 5/hour | Per IP |
| POST /account/change-email | 5/hour | Per IP |
| POST /account/change-password | 5/hour | Per IP |
| POST /account/delete | 3/hour | Per IP |

**Response**: 429 Too Many Requests with retry-after header

**Acceptance Criteria**:
- Limits enforced per IP address
- Legitimate users not impacted by normal usage
- Brute force attacks mitigated

**Implementation**: `limiter.py`, `@limiter.limit()` decorators

#### REQ-SEC-004: CSRF Protection
**Priority**: High
**Status**: ✅ Implemented

System shall protect against Cross-Site Request Forgery attacks.

**Implementation**:
- Token in `HX-CSRF-Token` header (HTMX integration)
- Secret: `AUTH_SECRET` environment variable
- All POST/PUT/PATCH/DELETE endpoints protected
- Exception handler returns 403 on validation failure

**Acceptance Criteria**:
- CSRF tokens required for state-changing operations
- Invalid tokens rejected with clear error
- HTMX automatically includes tokens

**Implementation**: `app.py:46-59`

#### REQ-SEC-005: No Inverter Control
**Priority**: Critical
**Status**: ✅ Implemented (by design)

System shall NEVER send control signals to user inverters.

**Implementation**:
- Collector is read-only (no Modbus write operations)
- No protocol support for AT+ commands
- No control endpoints in API
- Architecture explicitly prevents write operations

**Acceptance Criteria**:
- Codebase review confirms no control signal code
- Protocol decoder only reads data
- Users maintain full control of their devices

**Implementation**: Architectural design principle

#### REQ-INV-005: Inverter Metadata Management
**Priority**: Medium
**Status**: ✅ Implemented

Collector (superuser) shall update inverter metadata after reading it from telemetry.

**Metadata Fields**:
- Rated power (watts)
- Number of MPPTs (Maximum Power Point Trackers)

**Authentication**: Superuser (bearer token) only

**Endpoint**: `POST /inverter_metadata/{serial_logger}`

**Process**:
1. Collector reads metadata from inverter telemetry
2. Calls endpoint with serial_logger and metadata
3. System finds inverter by serial_logger
4. Updates rated_power and number_of_mppts fields
5. Returns updated inverter data

**Acceptance Criteria**:
- ✅ Metadata editable after registration
- ✅ Data loggers can submit metadata automatically via API
- ✅ Only superusers (collector) can update metadata
- ✅ Returns 404 if inverter not found
- ✅ Updates can be applied multiple times (overwrite)
- ✅ Implementation tested (8 passing tests)

**Implementation**: `api/inverter.py:224-288`
**Tests**: `tests/test_inverter_metadata.py`

#### REQ-DATA-001: InfluxDB Retention Policy
**Priority**: High
**Status**: ✅ Implemented

System shall implement 2-year data retention policy.

**Requirements**:
- Automatically delete data older than 2 years
- Configurable per bucket
- No manual cleanup required

**Implementation**:
- Default retention: 63,072,000 seconds (730 days / 2 years)
- Applied automatically to all new buckets
- Configurable via `retention_seconds` parameter
- Method added: `update_bucket_retention()` for existing buckets

**Acceptance Criteria**:
- ✅ Buckets created with 2-year retention by default
- ✅ Retention period configurable per bucket
- ✅ InfluxDB automatically purges data older than retention period
- ✅ Implementation tested (5 passing unit tests)

**Implementation**: `utils/influx.py:66-87` (create_bucket), `utils/influx.py:89-108` (update_bucket_retention)
**Tests**: `tests/test_influx_retention.py`

### 🔄 In Progress

*No requirements currently in progress.*

### 📋 Planned (Phase 2-3)

#### REQ-DASH-001: Real-Time Power Dashboard
**Priority**: High
**Status**: 📋 Planned (Phase 2)

Users shall view real-time power graphs.

**Features**:
- Live updating power graph (30-second refresh)
- Time range selector (1 hour, 6 hours, 24 hours, 7 days, 30 days)
- Multi-inverter comparison view
- Zoom and pan controls

**Data Source**: InfluxDB aggregated queries

**Acceptance Criteria**:
- Graph updates without full page reload
- Smooth rendering of time-series data
- Responsive design (mobile-friendly)

**Implementation**: New dashboard component

#### REQ-DASH-002: Energy Production Overview
**Priority**: High
**Status**: 📋 Planned (Phase 2)

Users shall view energy production statistics.

**Displays**:
- Daily yield (today, yesterday, comparison)
- Monthly yield (current month, historical months)
- Yearly yield (year-to-date, historical years)
- Total lifetime yield
- Best production day/month/year

**Visualizations**:
- Bar charts (daily/monthly/yearly comparison)
- Trend lines
- Summary statistics

**Acceptance Criteria**:
- Statistics accurate to within 1% of raw data
- Historical data loads quickly (< 1 second)

**Implementation**: New overview page

#### REQ-EXPORT-001: CSV/Excel Data Export
**Priority**: High
**Status**: 📋 Planned (Phase 2)

Users shall export telemetry data for analysis.

**Export Options**:
- Date range selector
- Inverter selector (single or all)
- Format: CSV or Excel (XLSX)
- Aggregation: Raw (60s), hourly, daily

**Use Cases**:
- GDPR Article 15 compliance (right to access)
- External analysis (spreadsheets)
- Data backup

**Acceptance Criteria**:
- Exports complete within 30 seconds for 1 year of data
- Files include metadata (inverter name, serial, date range)
- CSV follows RFC 4180 standard

**Implementation**: New export endpoint

#### REQ-ALERT-001: Email Alerting
**Priority**: High
**Status**: 📋 Planned (Phase 2)

Users shall receive email alerts for system events.

**Alert Types**:
| Alert | Trigger | Frequency |
|-------|---------|-----------|
| Inverter Offline | No data received for 10 minutes | Once, then every 24h |
| Low Production | Output < 20% of rated power during daylight | Once per day |
| Production Resumed | First data after offline period | Once |
| Daily Summary | End of day statistics | Daily at 23:00 |
| Weekly Summary | Week statistics | Weekly on Sunday |

**Configuration**:
- Enable/disable per alert type
- Configure thresholds (e.g., low production percentage)
- Set quiet hours (no alerts during night)

**Acceptance Criteria**:
- Alerts sent within 5 minutes of trigger
- No duplicate alerts for same event
- Users can unsubscribe per alert type

**Implementation**: New alerting service

#### REQ-ANALYTICS-001: Performance Analytics
**Priority**: Medium
**Status**: 📋 Planned (Phase 2)

Users shall view performance analytics.

**Features**:
- Production vs. historical average
- Weather correlation (if weather data available)
- Efficiency trends over time
- String comparison (identify underperforming strings)

**Visualizations**:
- Trend charts
- Heatmaps (production by hour/day)
- Anomaly detection

**Acceptance Criteria**:
- Analytics based on at least 30 days of data
- Trends recalculated daily

**Implementation**: New analytics module

#### REQ-API-001: Third-Party API
**Priority**: High
**Status**: 📋 Planned (Phase 3)

System shall provide API for home automation and energy management integration.

**Use Cases**:
- Home Assistant integration
- OpenHAB integration
- Energy management systems
- Custom dashboards

**Endpoints**:
- `GET /api/v1/inverters` - List user's inverters
- `GET /api/v1/inverters/{id}/current` - Current power output
- `GET /api/v1/inverters/{id}/yield` - Yield statistics
- `GET /api/v1/inverters/{id}/telemetry` - Time-series data query

**Authentication**: Bearer token (API keys)

**Rate Limiting**: 100 requests per minute per user

**Documentation**: OpenAPI/Swagger specification

**Acceptance Criteria**:
- API follows REST conventions
- Complete documentation with examples
- Versioned endpoints (backwards compatibility)
- Rate limits enforced

**Implementation**: New API module

#### REQ-I18N-001: English Language Support
**Priority**: Medium
**Status**: 📋 Planned (Phase 3)

System shall support English language.

**Scope**:
- User interface (all pages)
- Email templates
- API error messages
- Documentation

**Implementation**:
- i18n framework (Flask-Babel or similar)
- Translation files (JSON or PO)
- Language selector in user preferences

**Acceptance Criteria**:
- Complete translation (no German fallbacks)
- Language preference persisted per user
- Browser language auto-detected for new users

**Implementation**: i18n integration

### 💡 Future (Phase 4+)

#### REQ-HW-001: OpenDTU Integration
**Priority**: Medium
**Status**: 💡 Future (Phase 4)

System shall support Hoymiles inverters via OpenDTU.

**Protocol**: OpenDTU HTTP API or MQTT

**Implementation**:
- New protocol decoder in collector
- Backend configuration for protocol type per inverter
- Data model mapping (OpenDTU → InfluxDB schema)

**Acceptance Criteria**:
- Hoymiles inverters register like Deye inverters
- Data collected at same frequency (60 seconds)
- Same dashboard functionality available

**Implementation**: `collector-rust/src/protocol/opendtu.rs` (new)

#### REQ-HW-002: MQTT Protocol Support
**Priority**: Medium
**Status**: 💡 Future (Phase 4)

System shall support MQTT-capable devices.

**Use Cases**:
- OpenDTU (MQTT mode)
- Custom inverter integrations
- IoT devices publishing telemetry

**Implementation**:
- MQTT broker or client mode
- Topic structure: `deye-hard/{user_id}/{inverter_id}/{metric}`
- Message format: JSON

**Acceptance Criteria**:
- MQTT devices authenticate with credentials
- Data mapped to InfluxDB schema
- Same dashboard functionality available

**Implementation**: New MQTT service

#### REQ-SOCIAL-001: Multi-User Collaboration
**Priority**: Low
**Status**: 💡 Future (Phase 5)

Users shall share inverter access with others.

**Use Cases**:
- Family members viewing same inverter
- Installers monitoring client systems
- Temporary guest access

**Roles**:
- Owner: Full control (edit, delete)
- Viewer: Read-only access
- Guest: Temporary access with expiration

**Acceptance Criteria**:
- Owners can invite users via email
- Shared inverters visible in invitee's dashboard
- Permissions enforced at API level

**Implementation**: New sharing model

#### REQ-MOBILE-001: Progressive Web App
**Priority**: Low
**Status**: 💡 Future (Phase 5)

Web interface shall function as mobile app.

**Features**:
- Add to home screen (iOS/Android)
- Offline mode (cached dashboard)
- Push notifications (via service worker)

**Implementation**:
- Service worker for caching
- Web manifest file
- Responsive design optimization

**Acceptance Criteria**:
- Installable on mobile devices
- Works offline (view cached data)
- Mobile-optimized interface

**Implementation**: PWA enhancements

#### REQ-DATA-002: Long-Term Archiving
**Priority**: Low
**Status**: 💡 Future

Users shall archive data beyond 2-year retention.

**Features**:
- Manual archive trigger
- Automatic archive on retention expiration
- Archive storage (S3-compatible)
- Restore from archive

**Acceptance Criteria**:
- Archived data accessible for export
- Archive storage costs transparent
- Restore completes within 24 hours

**Implementation**: Archive service

---

## Non-Functional Requirements

### Performance

#### REQ-PERF-001: User Capacity
**Target**: 100 concurrent users
**Scalability**: Architecture supports future growth to 1,000+ users

**Metrics**:
- Concurrent sessions: 100
- Total registered users: 500
- Requests per second: 50 (peak)

#### REQ-PERF-002: Inverter Capacity
**Target**: 500 inverters total
**Average**: 1-2 inverters per user
**Scalability**: Architecture supports 5,000+ inverters

**Metrics**:
- Data points per second: 500 inverters × 20 fields / 60s = ~166 points/s
- InfluxDB buckets: 500 (one per inverter)
- InfluxDB organizations: 100 (one per user)

#### REQ-PERF-003: Data Collection Latency
**Target**: 60-second intervals (±5 seconds)
**Acceptance**: 95% of data points within 65 seconds of generation

**Metrics**:
- Median latency: < 3 seconds
- 95th percentile: < 10 seconds
- 99th percentile: < 30 seconds

#### REQ-PERF-004: Dashboard Response Time
**Target**: < 2 seconds for initial load
**Target**: < 500ms for subsequent interactions

**Metrics**:
- Time to first byte: < 200ms
- Full page render: < 2 seconds
- HTMX partial updates: < 500ms

#### REQ-PERF-005: API Response Time
**Target**: < 200ms for read operations
**Target**: < 500ms for write operations

**Metrics**:
- GET requests: < 200ms (95th percentile)
- POST requests: < 500ms (95th percentile)
- InfluxDB queries: < 1 second (95th percentile)

### Reliability

#### REQ-REL-001: Uptime
**Target**: Best effort (no SLA)
**Expected**: > 99% uptime during beta

**Exclusions**:
- Planned maintenance (announced 24h in advance)
- Force majeure events
- Third-party service outages

#### REQ-REL-002: Data Durability
**Target**: No data loss during normal operation
**Backup**: Daily backups protect against system failures

**Metrics**:
- RPO (Recovery Point Objective): 24 hours
- RTO (Recovery Time Objective): 48 hours

#### REQ-REL-003: Backup Schedule
**Daily Backups**:
- Frequency: Every 24 hours at 02:00 CET
- Retention: 2 days
- Scope: PostgreSQL (all data), InfluxDB metadata (users, orgs, buckets)

**Weekly Backups**:
- Frequency: Every Sunday at 03:00 CET
- Retention: 4 weeks
- Scope: Full system backup (PostgreSQL, InfluxDB data)

**Acceptance Criteria**:
- Backups complete within 2 hours
- Backup integrity verified automatically
- Restore procedure tested quarterly

#### REQ-REL-004: Failure Recovery
**Automatic Recovery**:
- Service restarts on crash (systemd or Docker restart policy)
- Database connection retry (exponential backoff)
- JWT token auto-refresh (30-second buffer)

**Manual Recovery**:
- PostgreSQL restore from backup
- InfluxDB restore from backup
- Configuration rollback

### Scalability

#### REQ-SCALE-001: Horizontal Scaling
**Collector**: Stateless design supports multiple instances behind load balancer
**Backend**: Stateless design supports multiple instances behind load balancer
**Database**: PostgreSQL replication, InfluxDB clustering (future)

#### REQ-SCALE-002: Vertical Scaling
**Current Resources**:
- Backend: 2 CPU, 2GB RAM
- Collector: 2 CPU, 2GB RAM
- PostgreSQL: 2 CPU, 4GB RAM
- InfluxDB: 4 CPU, 8GB RAM

**Growth Path**: Resources can be increased without code changes

### Security

#### REQ-SEC-006: GDPR Compliance
**Status**: ✅ Compliant

**Requirements**:
- ✅ User consent (registration implies consent)
- ✅ Right to access (data export planned)
- ✅ Right to deletion (full cleanup implemented)
- ✅ Data minimization (only essential data collected)
- ✅ EU-only storage (Germany)
- 📋 Privacy policy (required before public launch)
- 📋 Terms of service (required before public launch)

#### REQ-SEC-007: Data Encryption
**In Transit**:
- HTTPS enforced for all web traffic (TLS 1.2+)
- PostgreSQL connections encrypted (TLS)
- InfluxDB connections encrypted (TLS)

**At Rest**:
- PostgreSQL: Encrypted storage volume (LUKS)
- InfluxDB: Encrypted storage volume (LUKS)
- Backups: Encrypted archives (GPG)

#### REQ-SEC-008: Authentication Security
**JWT**:
- Secure secret (min 32 bytes, random generation)
- Expiration enforced (2 days)
- Algorithm: HS256
- Claims validated (issuer, expiration, signature)

**Cookies**:
- Secure flag (HTTPS only)
- HttpOnly flag (no JavaScript access)
- SameSite: Strict
- Expiration matches JWT lifetime

#### REQ-SEC-009: Logging & Monitoring
**Security Events Logged**:
- User registration
- Login attempts (success and failure)
- Password changes
- Account deletions
- Admin access
- Rate limit violations
- CSRF violations
- InfluxDB credential access

**Log Format**: Structured JSON (structlog)
**Log Storage**: Persistent logs for 90 days
**Log Access**: Restricted to administrators

### Usability

#### REQ-USE-001: Setup Simplicity
**Target**: Non-technical users can complete setup in < 30 minutes

**Requirements**:
- Clear documentation with screenshots
- No firmware modifications required
- Parameter changes only (data logger reconfiguration)
- Guided setup wizard (planned)

#### REQ-USE-002: Language
**Current**: German
**Planned**: English (Phase 3)

**Scope**:
- User interface
- Email templates
- Error messages
- Documentation

#### REQ-USE-003: Accessibility
**Target**: WCAG 2.1 Level AA compliance (planned)

**Requirements**:
- Keyboard navigation
- Screen reader compatibility
- Color contrast ratios
- Alt text for images

### Maintainability

#### REQ-MAINT-001: Code Quality
**Standards**:
- Python: PEP 8 style guide
- Rust: Rustfmt formatting
- Type hints (Python)
- Documentation comments

**Testing**:
- Unit tests for critical functions
- Integration tests for API endpoints
- Test coverage > 70% (goal)

#### REQ-MAINT-002: Documentation
**Required Documentation**:
- ✅ Technical specification (SPEC.md)
- ✅ Requirements document (REQUIREMENTS.md)
- ✅ Development guide (CLAUDE.md)
- ✅ Setup guide (README.md)
- 📋 User manual
- 📋 API documentation (OpenAPI)

#### REQ-MAINT-003: Version Control
**Git Workflow**:
- Main branch: `master` (production-ready)
- Feature branches: Short-lived, merged via PR
- Commit messages: Conventional Commits format
- Tags: Semantic versioning (v1.0.0)

#### REQ-MAINT-004: Deployment
**Current**: Manual deployment
**Process**:
1. Test changes locally
2. Commit and push to repository
3. SSH to server
4. Pull changes
5. Restart services
6. Verify health

**Future**: CI/CD pipeline (GitHub Actions or similar)

---

## Hardware Compatibility

### ✅ Currently Supported

#### Inverters
- **Deye**: SUN300G3-EU-230 (tested), SUN600G3-EU-230, SUN800G3-EU-230, other micro-inverters
- **Bosswerk**: MI300, MI600, MI800 (Deye rebrands)
- **revolt**: PV modules (Deye rebrands)
- **Other**: Any inverter using Solarman V5 data loggers

**Tested Configuration**:
- Model: SUN300G3-EU-230
- Firmware: MW3_16U_5406_1.57
- Data Logger: IGEN Tech/Solarman

#### Data Loggers
- **IGEN Tech/Solarman**: V5 protocol loggers
- **Ports**: 80/tcp (web), 8899/tcp (Solarman), 48899/udp (AT+)
- **Communication**: TCP to collector, serial to inverter

#### Other Manufacturers (Solarman Loggers)
- **Omnik**: Inverters with Solarman loggers
- **Ginlong (Solis)**: Inverters with Solarman loggers
- **Sofar**: Inverters with Solarman loggers

### 📋 Planned Support

#### Hoymiles Inverters (Phase 4)
- **Protocol**: OpenDTU (HTTP API or MQTT)
- **Models**: HM-300, HM-600, HM-800, HM-1200, HM-1500
- **Data Collection**: Via OpenDTU gateway

#### MQTT Devices (Phase 4)
- **Protocol**: MQTT 3.1.1 or 5.0
- **Use Cases**: Custom integrations, IoT devices
- **Authentication**: Username/password or TLS certificates

### Hardware Requirements

#### Data Logger Reconfiguration
**Method**: Web interface (hidden page: `config_hide.html`)

**Parameters to Change**:
- Server IP/hostname: Collector IP address
- Server port: 10000 (or configured port)
- Upload interval: 60 seconds (default)

**No Changes Required**:
- Firmware version (no modifications)
- Inverter settings (no Modbus writes)
- WiFi credentials (user controls)

---

## Data Requirements

### Data Collection

#### Collection Frequency
**Interval**: 60 seconds (±5 seconds)
**Source**: Data logger initiates connection
**Protocol**: Solarman V5

#### Measurements Collected

**Uptime** (per logger):
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| power_on_time | Integer | Seconds | Time since logger powered on |
| total_working_time | Integer | Seconds | Cumulative working time |
| offset_time | Integer | Seconds | Time offset correction |

**Yield** (per inverter):
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| daily | Float | kWh | Energy produced today |
| total | Float | kWh | Total energy produced (lifetime) |

**Grid** (per inverter):
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| voltage_phase_1 | Float | Volts | Phase 1 voltage |
| voltage_phase_2 | Float | Volts | Phase 2 voltage |
| voltage_phase_3 | Float | Volts | Phase 3 voltage |
| current_phase_1 | Float | Amperes | Phase 1 current |
| current_phase_2 | Float | Amperes | Phase 2 current |
| current_phase_3 | Float | Amperes | Phase 3 current |
| power_phase_1 | Float | Watts | Phase 1 power (V×I) |
| power_phase_2 | Float | Watts | Phase 2 power (V×I) |
| power_phase_3 | Float | Watts | Phase 3 power (V×I) |
| frequency | Float | Hertz | Grid frequency |
| total_output_power | Integer | Watts | Total AC output power |

**String Production** (per string):
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| voltage | Float | Volts | String DC voltage |
| current | Float | Amperes | String DC current |

**String Yield** (per string):
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| daily | Float | kWh | Energy produced today by string |
| total | Float | kWh | Total energy produced by string |

#### Tags Applied
- `logger_serial`: Logger serial number (all measurements)
- `inverter_serial`: Inverter serial number (inverter-specific measurements)
- `string`: String identifier (string-specific measurements)

### Data Retention

#### Active Data
**Storage**: InfluxDB buckets (per inverter)
**Duration**: 2 years
**Implementation**: Bucket-level retention policy
**Status**: 🔄 Retention policy implementation in progress

#### Archived Data
**Storage**: Optional long-term archive (planned)
**Duration**: Indefinite (user-controlled)
**Format**: InfluxDB line protocol or CSV
**Status**: 💡 Future feature

### Data Backup

#### Daily Backups
**Frequency**: Every 24 hours at 02:00 CET
**Retention**: 2 days
**Scope**:
- PostgreSQL: Full database dump
- InfluxDB: Metadata only (users, organizations, buckets)

**Storage**: Encrypted backup volume
**Verification**: Automatic integrity check after backup

#### Weekly Backups
**Frequency**: Every Sunday at 03:00 CET
**Retention**: 4 weeks
**Scope**:
- PostgreSQL: Full database dump
- InfluxDB: Full data export (all buckets)

**Storage**: Encrypted backup volume + off-site copy
**Verification**: Automatic integrity check after backup

### Data Export

#### GDPR Article 15 (Right to Access)
**Scope**: All user data
- User profile (name, email)
- Inverter metadata (name, serial, registration date)
- Telemetry data (all measurements, configurable date range)

**Format**: CSV or Excel (XLSX)
**Delivery**: Download link via email
**Status**: 📋 Planned (Phase 2)

#### On-Demand Export
**Scope**: Telemetry data (user-selected inverters and date ranges)
**Format**: CSV or Excel (XLSX)
**Aggregation**: Raw (60s), hourly, daily
**Status**: 📋 Planned (Phase 2)

### Data Deletion

#### Account Deletion
**Scope**: Complete data removal
1. All inverter records (PostgreSQL)
2. All InfluxDB buckets (telemetry data)
3. User's InfluxDB organization
4. User account (PostgreSQL)

**Timing**: Immediate (synchronous operation)
**Status**: ✅ Implemented (`api/account.py:170-252`)

#### Automatic Deletion
**Scope**: Data older than retention policy (2 years)
**Timing**: Continuous (InfluxDB automatic)
**Status**: 🔄 Pending retention policy implementation

---

## User Requirements

### Primary Users

#### Private Homeowners
**Profile**:
- Own 1-2 solar inverters (balcony solar or rooftop installation)
- Privacy-conscious (concerned about data to China)
- Non-technical (prefer simple solutions)
- German-speaking (currently)

**Needs**:
- Monitor energy production
- Verify inverters are working correctly
- Track historical performance
- No manufacturer cloud connection

**User Journey**:
1. Read about Deye security issues (BSI report, solar.wtf.coop)
2. Sign up for Deye Hard beta
3. Follow setup guide (reconfigure data logger)
4. Register inverter(s) by serial number
5. View dashboard daily to monitor production

### Secondary Users

#### Solar Installation Companies
**Profile**:
- Install solar systems for customers
- Need to monitor customer installations
- Concerned about manufacturer cloud privacy
- Regional (Germany initially)

**Needs**:
- Offer privacy-safe monitoring to customers
- Troubleshoot installations remotely
- Demonstrate commitment to data protection
- Differentiate from competitors

**Use Cases**:
- Recommend Deye Hard during sales
- Configure data loggers during installation
- Monitor systems during warranty period

**Status**: Partner program planned (Phase 5)

#### Regional NGOs
**Profile**:
- Advocate for renewable energy (e.g., Balkon Solar e.V.)
- Educate public about solar power
- Support community solar initiatives
- Promote privacy and open-source

**Needs**:
- Recommend trusted solutions to members
- Provide technical support resources
- Collaborate on educational materials
- Build community around privacy-safe solar

**Use Cases**:
- List Deye Hard as recommended solution
- Host workshops on data logger reconfiguration
- Contribute to documentation
- Provide user support in forums

**Status**: Partner collaboration planned

### User Language & Localization

**Current**:
- German interface (all pages, emails, documentation)
- German error messages
- German locale (date/time formatting, number formatting)

**Planned**:
- English interface (Phase 3)
- Multi-language support framework
- User-selectable language preference
- Browser language auto-detection

---

## Deployment & Operations

### Hosting Environment

#### Location
**Country**: Germany
**Region**: EU (European Union)
**Rationale**: GDPR compliance, data sovereignty, latency

#### Infrastructure
**Platform**: Docker Compose (current), Kubernetes (future)
**Services**:
- Backend (FastAPI + Uvicorn)
- Collector (Rust binary)
- PostgreSQL (relational database)
- InfluxDB (time-series database)
- Nginx (reverse proxy, TLS termination)

#### Resources (Current)
| Service | CPU | RAM | Storage |
|---------|-----|-----|---------|
| Backend | 2 cores | 2 GB | 10 GB |
| Collector | 2 cores | 2 GB | 5 GB |
| PostgreSQL | 2 cores | 4 GB | 50 GB |
| InfluxDB | 4 cores | 8 GB | 500 GB |
| **Total** | **10 cores** | **16 GB** | **565 GB** |

### Deployment Process

#### Current Process (Manual)
**Status**: ✅ Operational

**Steps**:
1. **Development**: Local testing with test.env configuration
2. **Commit**: Git commit with descriptive message
3. **Push**: Push to GitHub repository
4. **Server Access**: SSH to production server
5. **Pull**: `git pull origin master`
6. **Dependencies**: `uv sync` (if dependencies changed)
7. **Migrations**: `uv run alembic upgrade head` (if schema changed)
8. **Restart**: `docker-compose restart backend collector`
9. **Verify**: `curl https://solar.wtf.coop/healthcheck`

**Downtime**: < 30 seconds (during restart)
**Rollback**: `git checkout <previous-commit> && docker-compose restart`

#### Planned Process (CI/CD)
**Status**: 💡 Future

**Pipeline**:
1. **Trigger**: Git push to `master` or `staging` branch
2. **Build**: Run tests, build Docker images
3. **Test**: Integration tests against staging environment
4. **Deploy**: Automated deployment to staging/production
5. **Verify**: Smoke tests, health checks
6. **Notify**: Success/failure notification to team

**Benefits**: Faster deployments, fewer errors, consistent process

### Monitoring & Logging

#### Health Monitoring
**Endpoint**: `GET /healthcheck`
**Response**: `{"FastAPI": "OK"}`
**Status**: ✅ Basic implementation

**Planned Enhancements** (Priority 2):
- PostgreSQL connectivity check
- InfluxDB connectivity check
- Disk space check
- Service status (collector running)

#### Application Logging
**Framework**: structlog (structured logging)
**Format**: JSON (production), console (development)
**Level**: INFO (production), DEBUG (development)

**Logged Events**:
- User registration, login, logout
- Inverter registration, deletion
- Email sent (verification, password reset)
- InfluxDB operations (user/org/bucket creation)
- Authentication failures
- Rate limit violations
- Errors and exceptions

**Storage**: Persistent logs for 90 days
**Access**: SSH to server, `docker-compose logs -f backend collector`

#### System Monitoring
**Current**: Manual monitoring
**Planned**: Prometheus + Grafana (future)

**Metrics to Track**:
- Request rate (requests per second)
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx responses)
- Database query time
- InfluxDB write rate
- Disk usage, memory usage, CPU usage

### Backup & Recovery

#### Backup Storage
**Location**: Encrypted volume on separate disk
**Off-Site**: Weekly backups copied to remote location
**Encryption**: GPG with 4096-bit RSA key

#### Backup Verification
**Frequency**: After each backup
**Method**: Checksum validation, test restore (weekly backups only)

#### Recovery Procedures

**Scenario 1: Service Crash**
- **Detection**: Health check failure, systemd restart
- **Recovery**: Automatic restart via Docker restart policy
- **RTO**: < 5 minutes

**Scenario 2: Database Corruption**
- **Detection**: Query failures, consistency errors
- **Recovery**: Restore from most recent daily backup
- **RTO**: 2-4 hours (manual process)

**Scenario 3: Complete Server Failure**
- **Detection**: Server unresponsive, data center notification
- **Recovery**: Provision new server, restore from weekly backup, update DNS
- **RTO**: 24-48 hours (manual process)

### Maintenance Windows

#### Scheduled Maintenance
**Frequency**: As needed (approximately monthly)
**Duration**: 1-2 hours
**Notification**: 24 hours advance notice via email

**Activities**:
- Security updates (OS, packages)
- Database maintenance (VACUUM, REINDEX)
- InfluxDB compaction
- Backup testing

#### Emergency Maintenance
**Trigger**: Critical security vulnerability, data integrity issue
**Notification**: Best effort (may be immediate)
**Documentation**: Post-mortem published after incident

---

## Compliance & Legal

### GDPR Compliance

#### Lawful Basis
**Article 6(1)(a)**: Consent
**Implementation**: User consent obtained during registration

#### Data Subject Rights

**Right to Access (Article 15)**:
- ✅ User can view account information
- 📋 Data export functionality planned (Phase 2)

**Right to Rectification (Article 16)**:
- ✅ User can change email address
- ✅ User can update inverter names

**Right to Erasure (Article 17)**:
- ✅ User can delete account
- ✅ All data deleted from PostgreSQL and InfluxDB

**Right to Data Portability (Article 20)**:
- 📋 CSV/Excel export planned (Phase 2)

#### Data Processing Record

**Data Controller**: WTF Kooperative eG
**Data Processor**: Same (self-hosted)

**Personal Data Collected**:
- Name (first, last)
- Email address
- Hashed password
- IP address (logs only, 90-day retention)

**Technical Data Collected**:
- Inverter serial numbers
- Energy production data
- Network metadata (collector IP, last connection time)

**Purpose**: Provide solar monitoring service
**Legal Basis**: Consent (Article 6(1)(a))
**Retention**: Account lifetime + 2 years (telemetry), 90 days (logs)
**Storage Location**: Germany (EU)

#### Required Documents
- 📋 Privacy Policy (before public launch)
- 📋 Terms of Service (before public launch)
- 📋 Data Processing Agreement (if third-party processors added)
- 📋 Cookie Policy (if non-essential cookies used)

### Open Source License

**License**: AGPL-3.0-only
**Source**: `collector-rust/Cargo.toml:6`

**Implications**:
- Source code must be publicly available
- Modifications must be released under AGPL-3.0
- Network use triggers copyleft (must provide source to users)
- Commercial use permitted

**Repository**: Planned publication after beta testing

### Financial Model

**Service Fee**: Free (no subscription)
**Donations**: Optional via PayPal
**Tax Status**: Donations not tax-deductible (no Spendenquittung)

**Transparency**:
- Donation usage: Server costs (hosting, domain, backups)
- Financial reports: Planned publication (annual)

**Sustainability**:
- Current: Self-funded by WTF Kooperative eG
- Long-term: Community donations, potential grants

### Liability & Warranties

**Disclaimer**: Beta service provided "as-is" without warranties

**Limitations**:
- No uptime guarantee (best effort)
- No liability for data loss (users should backup)
- No warranty for accuracy of monitoring data
- No liability for inverter malfunction

**User Responsibilities**:
- Maintain inverter safety and compliance
- Follow electrical codes and regulations
- Ensure proper installation (qualified electrician)
- Register inverters with grid operator (as required by law)

---

## Technical Debt & Known Issues

Status Legend:
- ❗ **Priority 1**: Blocks core functionality or causes data loss
- ⚠️ **Priority 2**: Impacts user experience or system reliability
- ℹ️ **Priority 3**: Minor issue, technical debt, future improvement

### ❗ Priority 1 (Must Fix)

*No Priority 1 issues remaining.*

### ✅ Resolved Priority 1 Issues

#### ~~ISSUE-001: Incomplete Inverter Metadata Endpoint~~
**Status**: ✅ Resolved
**Location**: `api/inverter.py:224-288`

**Problem**: SELECT query not implemented, endpoint non-functional

**Impact**: Data loggers cannot submit metadata (rated power, MPPT count), metadata display missing from dashboard

**Resolution**:
1. ✅ Implemented complete SELECT query using `scalar_one_or_none()`
2. ✅ Added proper error handling (404 for not found)
3. ✅ Added structured logging for metadata updates
4. ✅ Comprehensive documentation with docstring
5. ✅ Full test coverage (8 passing tests):
   - Success case
   - Not found case
   - Authorization checks (superuser only, no auth)
   - Multiple updates
   - Invalid data validation
   - Edge cases (zero values)
   - Typical Deye inverter values (300W, 600W, 800W, 1200W)

**Completed**: January 2025
**Actual Effort**: 2 hours
**Tests**: `tests/test_inverter_metadata.py`

### ⚠️ Priority 2 (Should Fix)

#### ~~ISSUE-002: InfluxDB Bucket Retention Policy~~
**Status**: ✅ Resolved
**Location**: `utils/influx.py:66-108`

**Problem**: No retention policy configured, data kept indefinitely

**Impact**: Storage costs increase over time, GDPR retention requirement not enforced

**Resolution**:
1. ✅ Updated `create_bucket()` to set 2-year retention policy (63,072,000 seconds) by default
2. ✅ Added `update_bucket_retention()` method for existing buckets (not needed - system not public yet)
3. ✅ Implemented comprehensive unit tests (5 passing tests)
4. ✅ Documented in REQ-DATA-001

**Completed**: January 2025
**Actual Effort**: 2 hours

#### ISSUE-003: Health Check Coverage
**Status**: 📋 Planned
**Location**: `api/healthcheck.py:8-10`

**Problem**: Only checks FastAPI is running, doesn't verify dependencies

**Impact**: False positives (service appears healthy but databases unreachable)

**Fix Required**:
1. Add PostgreSQL connectivity check (simple query)
2. Add InfluxDB connectivity check (ping or metadata query)
3. Return detailed status per component
4. Return 503 if any critical component fails

**Estimated Effort**: 2 hours
**Target**: Phase 2

#### ISSUE-004: Production Logging Configuration
**Status**: 📋 Planned
**Location**: `app.py:29`

**Problem**: Only dev console renderer configured, no production JSON output

**Impact**: Logs difficult to parse programmatically, no log rotation

**Fix Required**:
1. Detect environment (dev vs. production)
2. Use JSON renderer in production
3. Configure log rotation (size or time-based)
4. Integrate with log aggregation (optional)

**Estimated Effort**: 3 hours
**Target**: Phase 2

### ℹ️ Priority 3 (Nice to Have)

#### ISSUE-005: Cycle Import
**Status**: Known limitation
**Location**: `utils/influx.py:6`

**Problem**: Cannot import User model due to circular dependency

**Impact**: Type hints missing, IDE autocomplete limited

**Fix Required**:
1. Refactor to move shared models to separate module
2. Use `TYPE_CHECKING` guard for type hints
3. Consider dependency injection pattern

**Estimated Effort**: 6 hours
**Target**: Phase 3 (refactoring phase)

#### ISSUE-006: Pydantic 2.12+ Compatibility
**Status**: Known limitation
**Location**: `pyproject.toml:20`

**Problem**: Pydantic constrained to `<2.12` due to fastapi-mail bug

**Impact**: Cannot use latest Pydantic features, security updates delayed

**Upstream Issue**: https://github.com/sabuhish/fastapi-mail/issues/236
**Pending Fix**: PR #237 (not yet merged)

**Resolution**:
1. Wait for fastapi-mail 1.6.0 release
2. Remove Pydantic version constraint
3. Test email functionality thoroughly
4. Update dependencies

**Estimated Effort**: 1 hour (after upstream fix)
**Target**: When fastapi-mail 1.6.0 released

#### ISSUE-007: Admin Audit Logging
**Status**: Not implemented
**Location**: N/A

**Problem**: Admin actions not logged (create/delete users, modify inverters)

**Impact**: No audit trail for administrative changes

**Fix Required**:
1. Log all admin actions with user, timestamp, action
2. Store audit log in PostgreSQL (new table)
3. Display audit log in admin interface

**Estimated Effort**: 8 hours
**Target**: Phase 3 (security enhancements)

---

## Development Roadmap

### Phase 1: Core Stability (Current - Q1 2025)

**Goal**: Stable, production-ready core functionality

**Status**: 🔄 In Progress (95% complete)

**Deliverables**:
- ✅ User registration and verification
- ✅ Inverter management (add, view, delete)
- ✅ Data collection (Solarman V5, 60-second intervals)
- ✅ Multi-tenant InfluxDB isolation
- ✅ Admin interface
- ✅ Basic security (authentication, rate limiting, CSRF)
- 🔄 Fix metadata endpoint (ISSUE-001)
- 🔄 Implement retention policy (ISSUE-002)
- 📋 Beta testing with initial users (10-20 users)
- 📋 Privacy policy and terms of service
- 📋 User documentation (setup guide, troubleshooting)

**Success Criteria**:
- No critical bugs (Priority 1 issues resolved)
- 10 active beta testers
- Positive user feedback
- No data loss incidents

### Phase 2: Enhanced Monitoring (Q2 2025)

**Goal**: Improved user experience with rich monitoring features

**Status**: 📋 Planned

**Deliverables**:
- Real-time power dashboard with graphs (REQ-DASH-001)
- Energy production overview (REQ-DASH-002)
- CSV/Excel data export (REQ-EXPORT-001)
- Email alerting (REQ-ALERT-001)
  - Inverter offline notifications
  - Low production warnings
  - Daily/weekly summaries
- Performance analytics (REQ-ANALYTICS-001)
- Health check improvements (ISSUE-003)
- Production logging configuration (ISSUE-004)

**Success Criteria**:
- Dashboard loads in < 2 seconds
- Alerts sent within 5 minutes of trigger
- Export generates within 30 seconds for 1 year of data
- 50+ active users

### Phase 3: Integration & Expansion (Q3 2025)

**Goal**: API access for third-party integrations, international expansion

**Status**: 📋 Planned

**Deliverables**:
- RESTful API for home automation (REQ-API-001)
  - Home Assistant integration
  - OpenHAB integration
  - Energy management systems
- API documentation (OpenAPI/Swagger)
- English language support (REQ-I18N-001)
- Performance analytics
- Code refactoring (ISSUE-005)
- Open-source repository publication

**Success Criteria**:
- API documented with examples
- 5+ third-party integrations demonstrated
- English interface complete
- Community contributions (GitHub issues, PRs)
- 100+ active users

### Phase 4: Extended Hardware Support (Q4 2025)

**Goal**: Support additional inverter manufacturers and protocols

**Status**: 📋 Planned

**Deliverables**:
- OpenDTU integration (Hoymiles inverters) (REQ-HW-001)
- MQTT protocol support (REQ-HW-002)
- Additional protocol decoders (community-driven)
- Collector refactoring (plugin architecture)

**Success Criteria**:
- Hoymiles inverters operational
- MQTT devices operational
- Protocol documentation published
- 200+ active users

### Phase 5: Community & Growth (2026+)

**Goal**: Sustainable community-driven project

**Status**: 💡 Future

**Deliverables**:
- Multi-user collaboration (REQ-SOCIAL-001)
- Installer partner program
- NGO partnerships (Balkon Solar e.V., etc.)
- Community forum
- Progressive web app (REQ-MOBILE-001)
- Long-term archiving (REQ-DATA-002)
- Automated CI/CD pipeline
- Kubernetes deployment

**Success Criteria**:
- Self-sustaining community (donations cover costs)
- Active forum with peer support
- Partner network established
- 500+ active users

---

## Out of Scope

**Explicitly Not Planned**:

### Technical
- ❌ Native mobile apps (iOS/Android) - Web-responsive sufficient
- ❌ Push notifications (mobile OS-level) - Email notifications sufficient
- ❌ Real-time websocket updates - Periodic refresh sufficient
- ❌ Blockchain integration - No use case
- ❌ AI/ML predictions - Complexity not justified
- ❌ Cryptocurrency payments - PayPal sufficient

### Features
- ❌ Billing/tariff calculations - Out of scope (too complex, region-specific)
- ❌ Smart home control - Read-only monitoring by design
- ❌ Inverter configuration - User maintains control
- ❌ Firmware updates - User maintains control
- ❌ Weather data integration - May reconsider for analytics
- ❌ Social media integration - Privacy-focused

### Business
- ❌ Commercial SLA guarantees - Community project, best effort
- ❌ Paid support contracts - Community support model
- ❌ Reseller program - NGO partnerships only
- ❌ Hardware sales - Software-only project

### Security (Not Required for Beta)
- ❌ Two-factor authentication (2FA) - May add later
- ❌ Password rotation policies - Complexity not justified
- ❌ Session timeout (idle) - Current timeout sufficient
- ❌ Intrusion detection/prevention - Infrastructure-level solution
- ❌ DDoS mitigation - Infrastructure-level solution

---

## Success Criteria

### Technical Success

#### Security
- ✅ No BSI-identified vulnerabilities present in system
- ✅ GDPR-compliant data handling verified
- ✅ Multi-tenant data isolation tested and verified
- ✅ No control signals sent to inverters (architecture review)
- ✅ All passwords hashed (bcrypt)
- ✅ All sensitive data encrypted in transit (TLS)

#### Performance
- ✅ Support 100 concurrent users without degradation
- ✅ Handle 500 inverters with 60-second data collection
- ✅ Dashboard loads in < 2 seconds
- ✅ No data loss during normal operation
- ✅ Uptime > 99% (excluding planned maintenance)

#### Functionality
- ✅ Users can register and verify accounts
- ✅ Users can add and delete inverters
- ✅ Telemetry data collected every 60 seconds
- ✅ Dashboard displays current power and status
- ✅ Admin interface functional

### User Success

#### Adoption
- 🔄 10 active beta testers (Phase 1)
- 📋 50 active users (Phase 2)
- 📋 100 active users (Phase 3)
- 📋 200 active users (Phase 4)
- 💡 500 active users (Phase 5)

#### Satisfaction
- 📋 Positive user feedback from beta testers
- 📋 < 5% churn rate (users deleting accounts)
- 📋 Setup completion rate > 80% (users who start setup complete it)
- 📋 Average session duration > 2 minutes (engaged users)

#### Support
- 📋 < 10% users require support (self-service documentation sufficient)
- 📋 Average support response time < 24 hours
- 📋 User-contributed documentation and guides

### Community Success

#### Open Source
- 📋 Repository published on GitHub
- 📋 5+ community contributors (code, documentation, translations)
- 📋 10+ GitHub stars
- 📋 Active issue discussions

#### Partnerships
- 📋 Partnership with Balkon Solar e.V. established
- 📋 3+ regional NGOs recommending Deye Hard
- 📋 5+ installer companies using Deye Hard

#### Sustainability
- 📋 Donations cover 50% of server costs
- 📋 Monthly active maintainers > 3
- 📋 Codebase health (test coverage > 70%, low technical debt)

---

## References & Resources

### Documentation

**Project Documentation**:
- Landing page: https://solar.wtf.coop
- Technical specification: [SPEC.md](./SPEC.md)
- Development guide: [CLAUDE.md](./CLAUDE.md)
- Setup guide: [README.md](./README.md)
- Requirements document: [REQUIREMENTS.md](./REQUIREMENTS.md) (this document)

**Security Analysis**:
- BSI report: [collector-rust/bsi-bericht.tex](./collector-rust/bsi-bericht.tex)
- Title: "Zugriff und Beeinflussung über die Monitoring-Cloud bei Mikrowechselrichtern von Deye"
- Author: Andreas Brain
- Date: September 26, 2023

### External Resources

**Protocols**:
- Solarman V5 protocol: https://pysolarmanv5.readthedocs.io/en/stable/solarmanv5_protocol.html
- AT+ commands reference: https://github.com/Hypfer/deye-microinverter-cloud-free#at-commands
- Modbus protocol: https://modbus.org/specs.php

**Community**:
- Balkon Solar e.V.: https://balkon.solar/
- Photovoltaikforum: https://www.photovoltaikforum.com/
- Heise article (access point bug): https://heise.de/-7494024
- Heise article (external relay): https://heise.de/-9291891

**Standards**:
- GDPR (EU 2016/679): https://gdpr-info.eu/
- JWT (RFC 7519): https://tools.ietf.org/html/rfc7519
- CSV (RFC 4180): https://tools.ietf.org/html/rfc4180
- WCAG 2.1: https://www.w3.org/WAI/WCAG21/quickref/

### Technical Stack

**Backend**:
- FastAPI: https://fastapi.tiangolo.com/
- SQLAlchemy 2.x: https://docs.sqlalchemy.org/en/20/
- Alembic: https://alembic.sqlalchemy.org/
- fastapi-users: https://fastapi-users.github.io/fastapi-users/
- Jinja2: https://jinja.palletsprojects.com/
- HTMX: https://htmx.org/

**Collector**:
- Tokio (Rust async): https://tokio.rs/
- reqwest (HTTP client): https://docs.rs/reqwest/
- influxdb2 (client): https://docs.rs/influxdb2/
- tracing (logging): https://docs.rs/tracing/

**Databases**:
- PostgreSQL: https://www.postgresql.org/docs/
- InfluxDB 2.x: https://docs.influxdata.com/influxdb/v2/

---

## Glossary

### Hardware Terms

**Inverter / Wechselrichter**: Device that converts DC power from solar panels to AC power for grid connection. Micro-inverters operate at panel level (typically 300-800W per inverter).

**Data Logger**: Monitoring device that collects telemetry from inverter(s) and transmits to cloud service. Manufactured by IGEN Tech for Solarman platform.

**Serial Logger**: Unique identifier for data logger hardware (typically 10-digit number). Used to authenticate and route telemetry data.

**MPPT (Maximum Power Point Tracker)**: Circuit that optimizes solar panel power output by adjusting voltage/current operating point. Inverters may have 2-4 MPPTs for multiple panel strings.

**String**: Group of solar panels connected in series. Each string has independent voltage/current monitoring.

**Grid / Netz**: AC electrical grid (230V/400V in EU). Inverters synchronize with grid frequency (50 Hz in EU).

**Island Protection / Inselbetrieb**: Safety feature that prevents inverter from energizing disconnected grid (e.g., during power outage). Protects utility workers.

### Software Terms

**Solarman V5 Protocol**: Proprietary binary protocol used by IGEN Tech data loggers to communicate with cloud service. Encapsulates Modbus frames and control messages.

**Modbus**: Industrial protocol for reading/writing device registers. Used by data logger to communicate with inverter over serial connection.

**AT+ Commands**: Text-based command set for configuring data logger settings (similar to Hayes modem commands).

**Bucket**: InfluxDB time-series data container. Each inverter has dedicated bucket within user's organization.

**Organization (Org)**: InfluxDB tenant isolation unit. Each user has dedicated organization for multi-tenant data separation.

**Measurement**: InfluxDB data series with common tags and fields (e.g., "grid" measurement has voltage/current/power fields).

**Tag**: InfluxDB indexed metadata (e.g., inverter_serial). Used for filtering and grouping queries.

**Field**: InfluxDB measured value (e.g., voltage, current). Stored as time-series data points.

**JWT (JSON Web Token)**: Compact, URL-safe authentication token containing JSON claims. Used for stateless authentication.

**CSRF (Cross-Site Request Forgery)**: Attack where malicious site tricks user's browser into making unauthorized requests. Mitigated with CSRF tokens.

**Multi-Tenant**: Architecture where single system serves multiple independent customers with data isolation.

### Security Terms

**BSI (Bundesamt für Sicherheit in der Informationstechnik)**: German Federal Office for Information Security. Government agency responsible for IT security.

**GDPR (General Data Protection Regulation)**: EU regulation (2016/679) governing personal data protection and privacy. Applies to all EU data processing.

**Encrypt-then-Delete**: Security pattern where sensitive data is encrypted for temporary storage, then permanently deleted after use. Prevents plaintext persistence.

**BSSID (Basic Service Set Identifier)**: Unique identifier for WiFi access point (MAC address). Can be used for geolocation via database lookup.

**Bcrypt**: Password hashing algorithm with built-in salt and work factor. Industry standard for secure password storage.

**Fernet**: Symmetric encryption algorithm (AES-128-CBC + HMAC-SHA256). Used for temporary password encryption.

**TLS (Transport Layer Security)**: Cryptographic protocol for secure network communication. Successor to SSL.

**Rate Limiting**: Technique to prevent abuse by limiting request frequency per IP address or user.

### Organization Terms

**WTF Kooperative eG**: Werkkooperative der Technikfreund*innen (cooperative of technology enthusiasts). German cooperative (eG = eingetragene Genossenschaft).

**MDZ-SH (Mittelstand-Digital Zentrum Schleswig-Holstein)**: Government-funded digital center supporting small/medium businesses in Schleswig-Holstein. Provided initial project funding (no longer active partner).

**Balkon Solar e.V.**: German non-profit association (eingetragener Verein) advocating for balcony solar installations. Educational and policy focus.

**NGO (Non-Governmental Organization)**: Non-profit, voluntary organization independent of government. Examples: Balkon Solar e.V., community solar groups.

### Project Terms

**Beta Testing**: Pre-release testing phase with limited users to identify bugs and gather feedback before public launch.

**Technical Debt**: Accumulated code quality issues, shortcuts, or incomplete implementations requiring future refactoring.

**Open Source**: Software with source code publicly available under license allowing use, modification, and distribution.

**AGPL-3.0 (GNU Affero General Public License 3.0)**: Strong copyleft open-source license requiring source disclosure for network use (not just distribution).

**CI/CD (Continuous Integration / Continuous Deployment)**: Automated pipeline for testing and deploying code changes.

**RTO (Recovery Time Objective)**: Maximum acceptable time to restore service after incident.

**RPO (Recovery Point Objective)**: Maximum acceptable data loss (time between backup and incident).

---

**Document Version**: 1.0
**Last Updated**: January 2025
**Next Review**: March 2025 (after Phase 1 completion)
**Maintained by**: WTF Kooperative eG
**Contact**: See https://solar.wtf.coop for current contact information
	