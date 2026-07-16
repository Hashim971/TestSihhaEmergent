/*
  # Create MedQuAD Table

  1. New Tables
    - `medquad`
      - `id` (uuid, primary key)
      - `question` (text)
      - `answer` (text)
      - `source` (text)
      - `content` (tsvector, generated column for full-text search)

  2. Security
    - Enable RLS on `medquad` table
    - Add policy for public read access
*/

-- Create the MedQuAD table with full-text search support
CREATE TABLE medquad (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  question text NOT NULL,
  answer text NOT NULL,
  source text NOT NULL,
  content tsvector GENERATED ALWAYS AS (
    to_tsvector('english', question || ' ' || answer)
  ) STORED
);

-- Create a GIN index for fast full-text search
CREATE INDEX medquad_content_idx ON medquad USING gin(content);

-- Enable Row Level Security
ALTER TABLE medquad ENABLE ROW LEVEL SECURITY;

-- Create a policy to allow public read access
CREATE POLICY "Allow public read access to medquad"
  ON medquad
  FOR SELECT
  TO public
  USING (true);

-- Insert initial medical QA data
INSERT INTO medquad (question, answer, source) VALUES
  (
    'What are the common symptoms of COVID-19?',
    'Common COVID-19 symptoms include fever, dry cough, fatigue, loss of taste or smell, body aches, and difficulty breathing. Symptoms can range from mild to severe. If you experience severe symptoms, seek immediate medical attention.',
    'WHO Guidelines'
  ),
  (
    'When should I seek emergency medical care?',
    'Seek emergency care immediately for: 1) Severe difficulty breathing 2) Persistent chest pain or pressure 3) New confusion 4) Inability to wake or stay awake 5) Bluish lips or face 6) Severe allergic reactions 7) Signs of stroke or heart attack',
    'Emergency Medicine Protocol'
  ),
  (
    'What are signs of dehydration?',
    'Common signs of dehydration include: 1) Dark yellow or amber-colored urine 2) Decreased urination 3) Dry mouth and lips 4) Fatigue or sleepiness 5) Dizziness or lightheadedness 6) Decreased skin elasticity 7) Headache. Severe cases may require immediate medical attention.',
    'Medical Reference Guide'
  );