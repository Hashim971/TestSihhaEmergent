/*
  # Update RLS policies for MedQuAD table
  
  1. Changes
     - Simplify RLS policies
     - Enable public read access
     - Allow authenticated users to perform all operations
  
  2. Security
     - Maintains data security while allowing necessary access
     - Preserves public read access for the health chatbot
     - Restricts write operations to authenticated users
*/

-- Create policies for public read access
CREATE POLICY "allow_public_read"
  ON medquad
  FOR SELECT
  TO public
  USING (true);

-- Create policy for authenticated users
CREATE POLICY "allow_authenticated_write"
  ON medquad
  FOR ALL 
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Ensure RLS is enabled
ALTER TABLE medquad ENABLE ROW LEVEL SECURITY;