-- Ensure the table has the correct structure
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

    -- Create or replace the category index
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'medquad_category_idx'
    ) THEN
        CREATE INDEX medquad_category_idx ON medquad (category);
    END IF;

    -- Create or replace the composite text search index
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE indexname = 'medquad_category_content_idx'
    ) THEN
        CREATE INDEX medquad_category_content_idx ON medquad 
        USING gin(to_tsvector('english', coalesce(category, '') || ' ' || question || ' ' || answer));
    END IF;
END $$;

-- Create functions for data processing
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

-- Create function to extract category
CREATE OR REPLACE FUNCTION extract_category(source_text text)
RETURNS text AS $$
BEGIN
    IF source_text ILIKE '%cardio%' THEN RETURN 'Cardiology';
    ELSIF source_text ILIKE '%neuro%' THEN RETURN 'Neurology';
    ELSIF source_text ILIKE '%gastro%' THEN RETURN 'Gastroenterology';
    ELSIF source_text ILIKE '%pediatr%' THEN RETURN 'Pediatrics';
    ELSIF source_text ILIKE '%emergency%' THEN RETURN 'Emergency Medicine';
    ELSIF source_text ILIKE '%surgery%' THEN RETURN 'Surgery';
    ELSIF source_text ILIKE '%mental%' OR source_text ILIKE '%psych%' THEN RETURN 'Mental Health';
    ELSE RETURN 'General Medicine';
    END IF;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Create a function to process and insert MedQuAD data
CREATE OR REPLACE FUNCTION process_medquad_entry(
    p_question text,
    p_answer text,
    p_source text,
    p_category text DEFAULT NULL,
    p_metadata jsonb DEFAULT NULL
)
RETURNS uuid AS $$
DECLARE
    v_id uuid;
BEGIN
    INSERT INTO medquad (
        question,
        answer,
        source,
        category,
        metadata
    ) VALUES (
        clean_text(p_question),
        clean_text(p_answer),
        clean_text(p_source),
        COALESCE(p_category, extract_category(p_source)),
        p_metadata
    )
    RETURNING id INTO v_id;
    
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;