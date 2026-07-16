/*
  # MedQuAD Dataset Schema Update

  1. Changes
    - Add new columns for better data organization
    - Create improved search functions
    - Add indexes for performance
  
  2. Security
    - Maintain existing RLS policies
    - Add security definer to functions
*/

-- Add new columns if they don't exist
DO $$ 
BEGIN
    -- Add category column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'medquad' AND column_name = 'category'
    ) THEN
        ALTER TABLE medquad ADD COLUMN category text;
    END IF;

    -- Add metadata column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'medquad' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE medquad ADD COLUMN metadata jsonb;
    END IF;
END $$;

-- Create or replace indexes
CREATE INDEX IF NOT EXISTS medquad_category_idx ON medquad (category);
CREATE INDEX IF NOT EXISTS medquad_content_category_idx ON medquad 
USING gin(to_tsvector('english', coalesce(category, '') || ' ' || question || ' ' || answer));

-- Create improved search function
CREATE OR REPLACE FUNCTION search_medquad(
  search_query text,
  category_filter text DEFAULT NULL,
  limit_count int DEFAULT 5
) RETURNS TABLE (
  id uuid,
  question text,
  answer text,
  source text,
  category text,
  metadata jsonb,
  relevance float4
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    m.id,
    m.question,
    m.answer,
    m.source,
    m.category,
    m.metadata,
    ts_rank_cd(
      to_tsvector('english', 
        coalesce(m.category, '') || ' ' || 
        m.question || ' ' || 
        m.answer
      ),
      websearch_to_tsquery('english', search_query)
    ) as relevance
  FROM medquad m
  WHERE
    (category_filter IS NULL OR m.category = category_filter)
    AND to_tsvector('english', 
      coalesce(m.category, '') || ' ' || 
      m.question || ' ' || 
      m.answer
    ) @@ websearch_to_tsquery('english', search_query)
  ORDER BY relevance DESC
  LIMIT limit_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;