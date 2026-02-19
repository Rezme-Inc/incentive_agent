"""Quick smoke test for Exa API connectivity."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("EXA_API_KEY", "")
print(f"EXA_API_KEY: {api_key[:8]}... ({len(api_key)} chars total)")

if not api_key:
    print("ERROR: EXA_API_KEY not set in .env")
    sys.exit(1)

try:
    from exa_py import Exa

    exa = Exa(api_key=api_key)
    response = exa.search(
        query="Arizona employer hiring incentive programs",
        type="auto",
        num_results=5,
        contents={"text": {"max_characters": 500}},
    )

    print(f"Results returned: {len(response.results)}")
    if response.results:
        r = response.results[0]
        print(f"First result title: {r.title}")
        print(f"First result URL:   {r.url}")
    else:
        print("No results returned (empty list)")

except Exception as e:
    print(f"EXCEPTION: {type(e).__name__}: {e}")
    sys.exit(1)
