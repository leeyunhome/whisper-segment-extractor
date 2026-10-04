-- ===================================================================
-- EBS 학습 서비스 DB 스키마 (Phase 1)
--
-- Supabase SQL Editor 에 붙여넣고 실행하세요.
-- ===================================================================

-- ===================================================================
-- 1. 회차 메타데이터
-- ===================================================================
CREATE TABLE IF NOT EXISTS episodes (
  id              SERIAL PRIMARY KEY,
  episode_num     INTEGER UNIQUE NOT NULL,
  category        TEXT,
  subtitle        TEXT,
  air_date        DATE,
  duration_sec    REAL,
  script_count    INTEGER DEFAULT 0,
  mp3_path        TEXT NOT NULL,        -- Storage 경로 (예: 'episodes/2707_xxx.mp3')
  mp3_size_kb     INTEGER,
  uploaded_at     TIMESTAMPTZ DEFAULT NOW(),
  last_played_at  TIMESTAMPTZ,          -- 자동 정리 정책에 사용
  metadata        JSONB DEFAULT '{}'    -- 확장용 (원본 URL, 추가 정보 등)
);

-- ===================================================================
-- 200회차 자동 유지 정책 (Phase 5 에서 로직 구현)
-- ===================================================================
-- 1. 새로운 회차 업로드 시 총 개수 확인
-- 2. 200개를 초과할 경우, 'uploaded_at' 또는 'last_played_at' 이 가장 오래된 것부터 삭제
-- 3. CASCADE 에 의해 scripts, play_history 도 자동 삭제됨

CREATE INDEX IF NOT EXISTS idx_episodes_num ON episodes(episode_num DESC);
CREATE INDEX IF NOT EXISTS idx_episodes_category ON episodes(category);
CREATE INDEX IF NOT EXISTS idx_episodes_uploaded ON episodes(uploaded_at DESC);

-- ===================================================================
-- 2. 스크립트 (대화 세그먼트)
-- ===================================================================
CREATE TABLE IF NOT EXISTS scripts (
  id          SERIAL PRIMARY KEY,
  episode_id  INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  seq         INTEGER NOT NULL,        -- 순서 (0부터)
  start_sec   REAL NOT NULL,
  end_sec     REAL NOT NULL,
  text        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scripts_episode ON scripts(episode_id, seq);

-- ===================================================================
-- 3. 사용자 화이트리스트 (Phase 4 에서 사용)
-- ===================================================================
CREATE TABLE IF NOT EXISTS user_whitelist (
  email       TEXT PRIMARY KEY,
  invited_by  TEXT,
  invited_at  TIMESTAMPTZ DEFAULT NOW(),
  is_admin    BOOLEAN DEFAULT FALSE
);

-- ===================================================================
-- 4. 학습 기록 (Phase 5 에서 사용)
-- ===================================================================
CREATE TABLE IF NOT EXISTS play_history (
  id           SERIAL PRIMARY KEY,
  user_id      UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  episode_id   INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  played_at    TIMESTAMPTZ DEFAULT NOW(),
  duration_sec REAL,
  completed    BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_play_user ON play_history(user_id, played_at DESC);
CREATE INDEX IF NOT EXISTS idx_play_episode ON play_history(episode_id);

-- ===================================================================
-- 5. RLS (Row Level Security) - Phase 4 에서 활성화
-- ===================================================================

-- episodes/scripts 는 인증된 화이트리스트 사용자만 읽기 가능
-- (Phase 4 에서 활성화)
-- ALTER TABLE episodes ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scripts ENABLE ROW LEVEL SECURITY;

-- play_history 는 본인 것만
-- ALTER TABLE play_history ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Users see own history"
--   ON play_history FOR SELECT
--   USING (auth.uid() = user_id);
-- CREATE POLICY "Users insert own history"
--   ON play_history FOR INSERT
--   WITH CHECK (auth.uid() = user_id);
