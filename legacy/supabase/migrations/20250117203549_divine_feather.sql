/*
  # Fix MedQuAD table structure

  1. Changes
    - Add content column for full-text search using existing columns
    - Update RLS policies
    - Grant necessary permissions

  2. Security
    - Enable RLS
    - Create policies for public read and authenticated write access
*/

-- First disable RLS
ALTER TABLE medquad DISABLE ROW LEVEL SECURITY;

-- Add content column if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'medquad' AND column_name = 'content'
    ) THEN
        -- Add content column with generated tsvector using existing columns
        ALTER TABLE medquad 
        ADD COLUMN content tsvector GENERATED ALWAYS AS (
            to_tsvector('english', 
                coalesce(question, '') || ' ' || 
                coalesce(answer, '') || ' ' || 
                coalesce(source, '') || ' ' || 
                coalesce(focus_area, '')
            )
        ) STORED;

        -- Create GIN index on content column
        CREATE INDEX IF NOT EXISTS medquad_content_idx ON medquad USING gin(content);
    END IF;
END $$;

-- Re-enable RLS
ALTER TABLE medquad ENABLE ROW LEVEL SECURITY;

-- Recreate policies
DO $$ 
BEGIN
    DROP POLICY IF EXISTS "allow_read" ON medquad;
    DROP POLICY IF EXISTS "allow_all_authenticated" ON medquad;
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

CREATE POLICY "allow_read"
    ON medquad
    FOR SELECT
    TO public
    USING (true);

CREATE POLICY "allow_all_authenticated"
    ON medquad
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true);

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON medquad TO anon;
GRANT ALL ON medquad TO authenticated;