import json
import os
from datetime import datetime

class FileHandler:
    """Handle file operations for intermediate outputs"""
    
    @staticmethod
    def save_raw_research(text: str, output_dir: str = "output"):
        """Save raw research from Discovery agent"""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "01_discovery_raw.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"   💾 Saved: {filepath}")
        return filepath
    
    @staticmethod
    def save_programs_json(data: dict, output_dir: str = "output"):
        """Save extracted programs JSON"""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "02_programs_extracted.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"   💾 Saved: {filepath}")
        return filepath
    
    @staticmethod
    def save_verification_json(data: dict, output_dir: str = "output"):
        """Save verification results JSON"""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "03_verification_results.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"   💾 Saved: {filepath}")
        return filepath
    
    @staticmethod
    def save_action_plan_json(data: dict, output_dir: str = "output"):
        """Save action plan JSON"""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, "04_action_plan.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"   💾 Saved: {filepath}")
        return filepath
    
    @staticmethod
    def load_programs_json(filepath: str = "output/02_programs_extracted.json") -> dict:
        """Load programs JSON"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def load_verification_json(filepath: str = "output/03_verification_results.json") -> dict:
        """Load verification JSON"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

