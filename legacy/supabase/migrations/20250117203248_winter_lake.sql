/*
  # Final RLS Policy Configuration
  
  1. Changes
     - Consolidate all RLS policies
     - Ensure proper permissions
     - Maintain data security
  
  2. Security
     - Public read access
     - Authenticated user full access
     - Proper schema permissions
*/

-- First disable RLS
ALTER TABLE medquad DISABLE ROW LEVEL SECURITY;

-- Drop all existing policies
DO $$ 
BEGIN
    DROP POLICY IF EXISTS "allow_read" ON medquad;
    DROP POLICY IF EXISTS "allow_all_authenticated" ON medquad;
EXCEPTION
    WHEN OTHERS THEN NULL;
END $$;

-- Create new simplified policies
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

-- Re-enable RLS
ALTER TABLE medquad ENABLE ROW LEVEL SECURITY;

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON medquad TO anon;
GRANT ALL ON medquad TO authenticated;