# NBX Product Recommendation Engine

## Steps
1. Place your SMB Excel in `data/`.
2. Run the pipeline: `python -m nbx_recom.main`
3. Results are saved as JSON in `data/`.

## Config
Edit `nbx_recom/config.py` for file paths and API key.

## Notes
- Update HTML selectors in `scraper.py` as needed.
- The GenAI prompt is in `prompt_builder.py` and matches your screenshot. 