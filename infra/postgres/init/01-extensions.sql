-- ══════════════════════════════════════════════════════════════
--  SENTINEL — PostgreSQL ilk kurulum
--  Bu betik YALNIZCA veritabanı ilk oluşturulurken çalışır.
--  Tablo şeması Alembic göçleri ile yönetilir (backend/src/sentinel/db/migrations).
-- ══════════════════════════════════════════════════════════════

-- TimescaleDB: zaman serisi yetenekleri (hypertable, sürekli
-- toplulaştırma, sıkıştırma, saklama politikası)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- UUID üretimi (birincil anahtarlar için)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Kriptografik fonksiyonlar (HMAC, rastgele bayt üretimi)
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Sorgu performans istatistikleri (yavaş sorgu teşhisi)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Kurulum doğrulama çıktısı
DO $$
BEGIN
    RAISE NOTICE 'SENTINEL: eklentiler kuruldu — TimescaleDB %',
        (SELECT extversion FROM pg_extension WHERE extname = 'timescaledb');
END $$;
