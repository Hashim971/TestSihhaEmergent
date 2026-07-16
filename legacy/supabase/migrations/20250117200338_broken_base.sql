/*
  # Fix RLS policies for MedQuAD table
  
  1. Changes
     - Reset and simplify RLS policies
     - Enable public read access
     - Allow authenticated users full access
  
  2. Security
     - Maintains data security while allowing necessary access
     - Ensures public read access for health chatbot functionality
     - Restricts write operations to authenticated users only
*/

-- First disable RLS to reset policies
ALTER TABLE medquad DISABLE ROW LEVEL SECURITY;

-- Drop existing policies
DROP POLICY IF EXISTS "allow_public_read" ON medquad;
DROP POLICY IF EXISTS "allow_authenticated_write" ON medquad;
DROP POLICY IF EXISTS "authenticated_full_access" ON medquad;
DROP POLICY IF EXISTS "public_select_access" ON medquad;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON medquad;
DROP POLICY IF EXISTS "Allow public read access" ON medquad;

-- Create a simple policy for public read access
CREATE POLICY "public_read_access"
  ON medquad
  FOR SELECT
  TO anon, authenticated
  USING (true);

-- Create a policy for authenticated users to perform all operations
CREATE POLICY "authenticated_full_access"
  ON medquad
  FOR ALL
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Re-enable RLS
ALTER TABLE medquad ENABLE ROW LEVEL SECURITY;

-- Grant basic permissions
GRANT SELECT ON medquad TO anon;
GRANT ALL ON medquad TO authenticated;