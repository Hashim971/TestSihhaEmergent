/*
  # Add MedQuAD CSV Import Functions

  1. New Functions
    - import_medquad_csv: Safely imports CSV data into medquad table
    - validate_medquad_csv: Validates CSV data before import
  
  2. Security
    - Functions are SECURITY DEFINER
    - Limited to authenticated users
    - Input validation and sanitization
*/

-- Create a function to safely import CSV data
CREATE OR REPLACE FUNCTION import_medquad_csv(
  csv_content text
) RETURNS TABLE (
  imported_count int,
  error_message text
) AS $$
DECLARE
  v_count int := 0;
  v_error text := NULL;
  v_line text;
  v_parts text[];
BEGIN
  -- Create temporary table for staging
  CREATE TEMP TABLE temp_medquad (
    question text,
    answer text,
    source text,
    category text
  );

  BEGIN
    -- Process CSV content line by line
    FOR v_line IN 
      SELECT unnest(string_to_array(csv_content, E'\n'))
    LOOP
      -- Skip header row
      IF v_count > 0 THEN
        -- Split line into parts
        v_parts := string_to_array(v_line, ',');
        
        -- Insert into temp table if we have all required fields
        IF array_length(v_parts, 1) >= 3 THEN
          INSERT INTO temp_medquad (question, answer, source, category)
          VALUES (
            trim(v_parts[1]),
            trim(v_parts[2]),
            trim(v_parts[3]),
            CASE WHEN array_length(v_parts, 1) >= 4 THEN trim(v_parts[4]) ELSE NULL END
          );
        END IF;
      END IF;
      
      v_count := v_count + 1;
    END LOOP;

    -- Insert validated data into medquad table
    WITH inserted AS (
      INSERT INTO medquad (
        question,
        answer,
        source,
        category,
        metadata
      )
      SELECT
        clean_text(question),
        clean_text(answer),
        clean_text(source),
        COALESCE(category, extract_category(source)),
        jsonb_build_object(
          'imported_at', CURRENT_TIMESTAMP,
          'import_method', 'csv'
        )
      FROM temp_medquad
      WHERE question IS NOT NULL 
        AND answer IS NOT NULL 
        AND source IS NOT NULL
      RETURNING 1
    )
    SELECT count(*) INTO v_count FROM inserted;

  EXCEPTION WHEN OTHERS THEN
    v_error := SQLERRM;
  END;

  -- Clean up
  DROP TABLE IF EXISTS temp_medquad;

  RETURN QUERY SELECT v_count - 1, v_error; -- Subtract 1 to account for header row
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create a function to validate CSV data
CREATE OR REPLACE FUNCTION validate_medquad_csv(
  csv_content text
) RETURNS TABLE (
  row_number int,
  is_valid boolean,
  error_message text
) AS $$
DECLARE
  v_line text;
  v_row_number int := 0;
  v_parts text[];
BEGIN
  -- Process CSV content line by line
  FOR v_line IN 
    SELECT unnest(string_to_array(csv_content, E'\n'))
  LOOP
    v_row_number := v_row_number + 1;
    
    -- Skip header row validation
    IF v_row_number > 1 THEN
      -- Split line into parts
      v_parts := string_to_array(v_line, ',');
      
      RETURN QUERY
      SELECT 
        v_row_number,
        CASE
          WHEN array_length(v_parts, 1) < 3 THEN false
          WHEN trim(v_parts[1]) = '' THEN false
          WHEN trim(v_parts[2]) = '' THEN false
          WHEN trim(v_parts[3]) = '' THEN false
          ELSE true
        END,
        CASE
          WHEN array_length(v_parts, 1) < 3 THEN 'Missing required columns'
          WHEN trim(v_parts[1]) = '' THEN 'Missing question'
          WHEN trim(v_parts[2]) = '' THEN 'Missing answer'
          WHEN trim(v_parts[3]) = '' THEN 'Missing source'
          ELSE 'Valid'
        END;
    END IF;
  END LOOP;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Grant necessary permissions
GRANT EXECUTE ON FUNCTION import_medquad_csv TO authenticated;
GRANT EXECUTE ON FUNCTION validate_medquad_csv TO authenticated;

COMMENT ON FUNCTION import_medquad_csv IS 'Safely imports CSV data into the medquad table';
COMMENT ON FUNCTION validate_medquad_csv IS 'Validates CSV data before import into medquad table';