-- db/schema.sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  phone TEXT,
  default_location TEXT,
  default_location_latitude DOUBLE PRECISION,
  default_location_longitude DOUBLE PRECISION,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One user can have multiple login methods (password, google, ...)
CREATE TABLE auth_identities (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider TEXT NOT NULL CHECK (provider IN ('password', 'google')),
  provider_subject TEXT NOT NULL,
  email TEXT,
  email_verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (provider, provider_subject)
);

-- Password credentials are stored separately from the user profile
CREATE TABLE password_credentials (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  password_hash TEXT NOT NULL,
  password_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Refresh tokens are stored hashed; tokens are rotated on refresh
CREATE TABLE refresh_tokens (
  id BIGSERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  replaced_by_token_hash TEXT,
  user_agent TEXT,
  ip_address TEXT
);

-- We relate time slot preferences with the user via user_id, also days of the week must be between 0 and 6
CREATE TABLE time_slot_preferences (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
  start_time TIME NOT NULL,
  end_time TIME NOT NULL
);

CREATE TABLE groups (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT
);

-- We relate the users with the group_memberships via user_id and the groups via group_id, therefore making a relation between users and groups
CREATE TABLE group_memberships (
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member')),
  PRIMARY KEY (user_id, group_id)
);

CREATE TABLE calendars (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  owner_type TEXT NOT NULL CHECK (owner_type IN ('user', 'group')),
  owner_id INTEGER NOT NULL
);

-- We relate the users with the user_id and calendars with the calendar_id
CREATE TABLE user_calendars (
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  calendar_id INTEGER REFERENCES calendars(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, calendar_id)
);

CREATE TABLE meetings (
  id SERIAL PRIMARY KEY,
  calendar_id INTEGER NOT NULL REFERENCES calendars(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  location TEXT,
  location_raw TEXT,
  location_latitude DOUBLE PRECISION,
  location_longitude DOUBLE PRECISION,
  meeting_type TEXT NOT NULL DEFAULT 'in_person' CHECK (meeting_type IN ('in_person', 'virtual')),
  color TEXT NOT NULL DEFAULT '#3498db',
  start_time TIMESTAMPTZ NOT NULL,
  end_time TIMESTAMPTZ NOT NULL,
  capacity INTEGER,
  setup_minutes INTEGER DEFAULT 0,
  cleanup_minutes INTEGER DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'confirmed' CHECK (status IN ('proposed', 'confirmed', 'cancelled')),
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE location_cache (
  location_key TEXT PRIMARY KEY,
  location_label TEXT NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL,
  provider TEXT NOT NULL DEFAULT 'openrouteservice',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Here we relate the users with the meeting
CREATE TABLE meeting_attendees (
  meeting_id INTEGER REFERENCES meetings(id) ON DELETE CASCADE,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  status TEXT CHECK (status IN ('invited', 'accepted', 'declined', 'maybe')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (meeting_id, user_id)
);

CREATE INDEX idx_time_slot_preferences_user_id ON time_slot_preferences(user_id);
CREATE INDEX idx_group_memberships_group_id ON group_memberships(group_id);
CREATE INDEX idx_user_calendars_user_id ON user_calendars(user_id);
CREATE INDEX idx_meetings_calendar_id ON meetings(calendar_id);
CREATE INDEX idx_meeting_attendees_user_id ON meeting_attendees(user_id);
CREATE INDEX idx_auth_identities_user_id ON auth_identities(user_id);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
