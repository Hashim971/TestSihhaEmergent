-- First, disable RLS to allow initial setup
ALTER TABLE medquad DISABLE ROW LEVEL SECURITY;

-- Drop all existing policies
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON medquad;
DROP POLICY IF EXISTS "Allow public read access" ON medquad;
DROP POLICY IF EXISTS "Allow authenticated users to insert medquad data" ON medquad;
DROP POLICY IF EXISTS "Allow authenticated users to update medquad data" ON medquad;
DROP POLICY IF EXISTS "Allow authenticated users to delete medquad data" ON medquad;

-- Create a new policy for authenticated users with full access
CREATE POLICY "authenticated_full_access"
  ON medquad
  AS PERMISSIVE
  FOR ALL
  TO authenticated
  USING (auth.role() = 'authenticated')
  WITH CHECK (auth.role() = 'authenticated');

-- Create a policy for public read access
CREATE POLICY "public_select_access"
  ON medquad
  AS PERMISSIVE
  FOR SELECT
  TO public
  USING (true);

-- Re-enable RLS
ALTER TABLE medquad ENABLE ROW LEVEL SECURITY;

-- Grant necessary permissions
GRANT ALL ON medquad TO authenticated;
GRANT SELECT ON medquad TO anon;

-- Ensure the table owner has all permissions
ALTER TABLE medquad OWNER TO postgres;