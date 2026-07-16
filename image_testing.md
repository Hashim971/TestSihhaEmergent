# Image Integration Testing Rules

- Always use base64-encoded images for all tests and requests.
- Accepted formats: JPEG, PNG, WEBP only.
- Do not use SVG, BMP, HEIC, or other formats.
- Do not upload blank, solid-color, or uniform-variance images.
- Every image must contain real visual features — objects, edges, textures, or shadows.
- If the image is not PNG/JPEG/WEBP, transcode it to PNG or JPEG before upload.
- Always re-detect and update the MIME after transformations.
- If the image is animated, extract the first frame only.
- Resize large images to reasonable bounds (avoid oversized payloads).

Pill identify endpoint: POST /api/pills/identify {"image_base64": "<b64>", "profile_id": "self"} (auth required via session_token cookie or Bearer token).
