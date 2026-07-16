-- Update RLS policies for medquad table
ALTER TABLE medquad ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Allow public read access to medquad" ON medquad;
DROP POLICY IF EXISTS "Allow authenticated users to insert medquad data" ON medquad;

-- Create read policy (allow public read access)
CREATE POLICY "Allow public read access to medquad"
  ON medquad
  FOR SELECT
  TO public
  USING (true);

-- Create insert policy (allow authenticated users to insert)
CREATE POLICY "Allow authenticated users to insert medquad data"
  ON medquad
  FOR INSERT
  TO authenticated
  WITH CHECK (true);

-- Create update policy (allow authenticated users to update)
CREATE POLICY "Allow authenticated users to update medquad data"
  ON medquad
  FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

-- Create delete policy (allow authenticated users to delete)
CREATE POLICY "Allow authenticated users to delete medquad data"
  ON medquad
  FOR DELETE
  TO authenticated
  USING (true);