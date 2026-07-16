-- Create a function for searching MedQuAD entries
CREATE OR REPLACE FUNCTION search_medquad(search_query text)
RETURNS TABLE (
    id uuid,
    question text,
    answer text,
    source text,
    category text,
    metadata jsonb,
    rank float4
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
        ts_rank_cd(to_tsvector('english', m.question || ' ' || m.answer), to_tsquery('english', search_query)) as rank
    FROM
        medquad m
    WHERE
        to_tsvector('english', m.question || ' ' || m.answer) @@ to_tsquery('english', search_query)
    ORDER BY
        rank DESC
    LIMIT 5;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;