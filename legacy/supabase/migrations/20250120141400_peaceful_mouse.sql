-- Add content column for full-text search
ALTER TABLE medquad ADD COLUMN IF NOT EXISTS content tsvector
GENERATED ALWAYS AS (
    to_tsvector('english',
        coalesce(question, '') || ' ' ||
        coalesce(answer, '') || ' ' ||
        coalesce(source, '') || ' ' ||
        coalesce(focus_area, '')
    )
) STORED;

-- Create GIN index for faster full-text search
CREATE INDEX IF NOT EXISTS medquad_content_idx ON medquad USING gin(content);

-- Update the text search function to use the new column
CREATE OR REPLACE FUNCTION search_medquad(
    search_query text,
    limit_count int DEFAULT 3
) RETURNS TABLE (
    id uuid,
    question text,
    answer text,
    source text,
    focus_area text,
    relevance float4
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id,
        m.question,
        m.answer,
        m.source,
        m.focus_area,
        ts_rank_cd(m.content, websearch_to_tsquery('english', search_query)) as relevance
    FROM medquad m
    WHERE m.content @@ websearch_to_tsquery('english', search_query)
    ORDER BY relevance DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;