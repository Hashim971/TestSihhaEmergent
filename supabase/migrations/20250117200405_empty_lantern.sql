/*
  # Final RLS Policy Fix for MedQuAD Table
  
  1. Changes
     - Simplify RLS policies
     - Set correct permissions
     - Enable public read access
     - Allow authenticated users full access
  
  2. Security
     - Maintains data security
     - Ensures proper access control
*/

-- First disable RLS
ALTER TABLE medquad DISABLE ROW LEVEL SECURITY;

-- Drop all existing policies
DO $$ 
BEGIN
    -- Drop policies if they exist
    DROP POLICY IF EXISTS "public_read_access" ON medquad;
    DROP POLICY IF EXISTS "authenticated_full_access" ON medquad;
    DROP POLICY IF EXISTS "allow_public_read" ON medquad;
    DROP POLICY IF EXISTS "allow_authenticated_write" ON medquad;
    DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON medquad;
    DROP POLICY IF EXISTS "Allow public read access" ON medquad;
    DROP POLICY IF EXISTS "Allow authenticated users to insert medquad data" ON medquad;
    DROP POLICY IF EXISTS "Allow authenticated users to update medquad data" ON medquad;
    DROP POLICY IF EXISTS "Allow authenticated users to delete medquad data" ON medquad;
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