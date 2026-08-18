from pathlib import Path

PROMPT_DIR = Path(__file__).parent / "prompts"
REFERENCE_DIR = Path(__file__).parent / "reference"


def load_prompt(filename: str):
    """Returns (prompt_text, version). First line of the file must be 'version: vN'."""
    raw = (PROMPT_DIR / filename).read_text(encoding="utf-8")
    first, _, rest = raw.partition("\n")
    if first.strip().lower().startswith("version:"):
        return rest.strip(), first.split(":", 1)[1].strip()
    return raw.strip(), "unknown"
