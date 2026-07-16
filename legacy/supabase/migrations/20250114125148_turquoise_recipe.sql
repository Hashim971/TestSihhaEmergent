/*
  # Import MedQuAD Dataset

  1. Schema Changes
    - Adds new columns to medquad table:
      - category (text): Medical category/topic
      - source_url (text): Original source URL
      - metadata (jsonb): Additional metadata
    - Adds indexes for improved search performance

  2. Security
    - Maintains existing RLS policies
    - Adds index for category-based searches

  Note: This migration assumes the base medquad table structure exists
*/

-- Add new columns for better data organization
ALTER TABLE medquad 
ADD COLUMN IF NOT EXISTS category text,
ADD COLUMN IF NOT EXISTS source_url text,
ADD COLUMN IF NOT EXISTS metadata jsonb;

-- Create index on category for faster filtering
CREATE INDEX IF NOT EXISTS medquad_category_idx ON medquad (category);

-- Create a composite index for category + text search
CREATE INDEX IF NOT EXISTS medquad_category_content_idx ON medquad USING gin(to_tsvector('english', category || ' ' || question || ' ' || answer));

-- Function to clean and format text for import
CREATE OR REPLACE FUNCTION clean_text(input_text text)
RETURNS text AS $$
BEGIN
  -- Remove multiple spaces
  input_text := regexp_replace(input_text, '\s+', ' ', 'g');
  -- Remove special characters but keep basic punctuation
  input_text := regexp_replace(input_text, '[^\w\s\.,;:\-\?!]', '', 'g');
  -- Trim whitespace
  input_text := trim(input_text);
  RETURN input_text;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Function to extract category from source
CREATE OR REPLACE FUNCTION extract_category(source_text text)
RETURNS text AS $$
BEGIN
  -- Extract category based on common medical specialties
  IF source_text ILIKE '%cardio%' THEN RETURN 'Cardiology';
  ELSIF source_text ILIKE '%gastro%' THEN RETURN 'Gastroenterology';
  ELSIF source_text ILIKE '%neuro%' THEN RETURN 'Neurology';
  ELSIF source_text ILIKE '%pediatr%' THEN RETURN 'Pediatrics';
  ELSIF source_text ILIKE '%emergency%' THEN RETURN 'Emergency Medicine';
  ELSIF source_text ILIKE '%surgery%' THEN RETURN 'Surgery';
  ELSIF source_text ILIKE '%mental%' OR source_text ILIKE '%psych%' THEN RETURN 'Mental Health';
  ELSE RETURN 'General Medicine';
  END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;