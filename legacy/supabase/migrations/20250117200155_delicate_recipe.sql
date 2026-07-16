-- Temporarily disable RLS to allow initial import
ALTER TABLE medquad DISABLE ROW LEVEL SECURITY;

-- Drop all existing policies to start fresh
DROP POLICY IF EXISTS "Allow public read access to medquad" ON medquad;
DROP POLICY IF EXISTS "Allow authenticated users to insert medquad data" ON medquad;
DROP POLICY IF EXISTS "Allow authenticated users to update medquad data" ON medquad;
DROP POLICY IF EXISTS "Allow authenticated users to delete medquad data" ON medquad;

-- Create a single policy that allows all operations for authenticated users
CREATE POLICY "Allow all operations for authenticated users"
  ON medquad
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Create a separate policy for public read access
CREATE POLICY "Allow public read access"
  ON medquad
  FOR SELECT
  TO public
  USING (true);

-- Re-enable RLS with the new policies
ALTER TABLE medquad ENABLE ROW LEVEL SECURITY;