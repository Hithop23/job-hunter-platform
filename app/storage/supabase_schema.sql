-- ==============================================================================
-- JOB-HUNTER PRODUCTION SCHEMA (Supabase PostgreSQL + Multi-Tenant RLS)
-- ==============================================================================

-- 1. EXTENSIONS
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. PUBLIC PROFILES (1:1 with auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    phone TEXT,
    city TEXT DEFAULT 'Valledupar',
    department TEXT DEFAULT 'Cesar',
    country TEXT DEFAULT 'Colombia',
    
    -- Professional Targeting
    target_role TEXT DEFAULT 'Soporte Técnico / Help Desk TI',
    headline TEXT DEFAULT 'Técnico en Sistemas Teleinformáticos | Soporte TI | Help Desk Bilingüe B2',
    summary TEXT,
    english_level TEXT DEFAULT 'B2',
    salary_min_cop INT DEFAULT 2500000,
    salary_max_cop INT DEFAULT 4000000,
    
    -- Work preferences & infrastructure
    remote_only BOOLEAN DEFAULT TRUE,
    has_computer BOOLEAN DEFAULT TRUE,
    has_internet BOOLEAN DEFAULT TRUE,
    immediate_availability BOOLEAN DEFAULT TRUE,
    
    -- Rich Profile Data (Used by Dynamic ATS CV Generator)
    technical_skills JSONB DEFAULT '{}'::jsonb,
    experience JSONB DEFAULT '[]'::jsonb,
    education JSONB DEFAULT '[]'::jsonb,
    certifications JSONB DEFAULT '[]'::jsonb,
    languages JSONB DEFAULT '[]'::jsonb,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. PORTAL CREDENTIALS (Encrypted credentials & isolated sessions per user)
CREATE TABLE IF NOT EXISTS public.portal_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    portal_name TEXT NOT NULL, -- 'computrabajo', 'linkedin', 'magneto', 'elempleo'
    username TEXT NOT NULL,
    password_encrypted TEXT NOT NULL,
    session_cookies_encrypted TEXT, -- Serialized Playwright storage_state (cookies + localStorage)
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, portal_name)
);

-- 4. GLOBAL JOBS REPOSITORY (Shared job discovery to avoid redundant scraping)
CREATE TABLE IF NOT EXISTS public.jobs (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    url TEXT NOT NULL,
    description TEXT,
    requirements TEXT,
    salary TEXT,
    employment_type TEXT,
    publication_date TEXT,
    closing_date TEXT,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    deduplication_hash TEXT UNIQUE NOT NULL
);

-- 5. USER APPLICATIONS (Isolated per tenant)
CREATE TABLE IF NOT EXISTS public.applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id TEXT NOT NULL REFERENCES public.jobs(id) ON DELETE CASCADE,
    company TEXT NOT NULL,
    position TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DISCOVERED',
    
    -- Match Evaluation
    match_score FLOAT DEFAULT 0.0,
    match_reasons TEXT,
    
    -- Tailored CV & Cover Letter for this application
    cv_url TEXT,
    cover_letter TEXT,
    keywords_used TEXT,
    
    notes TEXT,
    submitted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, job_id)
);

-- 6. ROW LEVEL SECURITY (RLS) POLICIES
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portal_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;

-- Profiles Policy: Users can only see and edit their own profile
CREATE POLICY "Users can manage own profile"
    ON public.profiles FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Portal Credentials Policy: Strictly isolated
CREATE POLICY "Users can manage own credentials"
    ON public.portal_credentials FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Applications Policy: Completely private applications
CREATE POLICY "Users can manage own applications"
    ON public.applications FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Jobs Policy: Anyone authenticated can view jobs (read-only)
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Authenticated users can view jobs"
    ON public.jobs FOR SELECT
    TO authenticated
    USING (true);

-- 7. TRIGGER: Auto-create profile on Supabase user registration
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (user_id, email, full_name)
    VALUES (
        new.id,
        new.email,
        COALESCE(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1))
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
