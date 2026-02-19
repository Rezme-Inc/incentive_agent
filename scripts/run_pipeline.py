"""Run the full discovery pipeline with diagnostic output."""
import asyncio
import sys
import time

sys.path.insert(0, ".")

from src.agents.orchestrator import run_discovery


async def main():
    address = "123 W Washington St, Phoenix, AZ 85003"
    print(f"{'#'*60}")
    print(f"RUNNING FULL PIPELINE")
    print(f"Address: {address}")
    print(f"{'#'*60}\n")

    start = time.time()
    try:
        result = await run_discovery(
            address=address,
            legal_entity_type="LLC",
            industry_code=None,
        )
        elapsed = time.time() - start

        print(f"\n{'#'*60}")
        print(f"PIPELINE COMPLETE in {elapsed:.1f}s")
        print(f"{'#'*60}")
        print(f"Phase: {result.get('current_phase')}")
        print(f"Programs (raw accumulated): {len(result.get('programs', []))}")
        print(f"Merged programs: {len(result.get('merged_programs', []))}")
        print(f"Validated programs: {len(result.get('validated_programs', []))}")
        print(f"Errors flagged: {len(result.get('errors', []))}")
        print(f"Shortlisted: {len(result.get('shortlisted_programs', []))}")
        print(f"ROI calculations: {len(result.get('roi_calculations', []))}")

    except Exception as e:
        elapsed = time.time() - start
        print(f"\nPIPELINE FAILED after {elapsed:.1f}s: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
