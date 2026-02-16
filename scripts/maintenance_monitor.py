#!/usr/bin/env python3
"""
Maintenance Monitor - Re-check Active URLs for Status Changes
Goes back and checks all active programs to detect status changes or content updates
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import GoldenDataset
from agents.deep_verification import DeepVerificationAgent

class MaintenanceMonitor:
    """
    Re-scrape active URLs to check for status changes
    """
    
    def __init__(self, database_path: str = 'agents/Golden_Dataset.xlsx'):
        self.golden = GoldenDataset(database_path)
        self.verifier = DeepVerificationAgent()
    
    def get_active_urls(self) -> List[Dict]:
        """Get all programs with active status and URLs"""
        active_programs = self.golden.get_by_status_tag('ACTIVE')
        
        urls_to_check = []
        for program in active_programs:
            url = program.get('Official_Source_URL')
            if url:
                urls_to_check.append({
                    'program_id': program.get('Program_ID'),
                    'program_name': program.get('Program_Name'),
                    'url': url,
                    'current_status': program.get('Verified_Status'),
                    'last_checked': program.get('Verified_Date')
                })
        
        return urls_to_check
    
    def check_url_status(self, url_info: Dict) -> Dict:
        """
        Re-check a single URL for status changes
        
        Args:
            url_info: Dict with program_id, program_name, url, current_status
            
        Returns:
            {
                'program_id': ...,
                'status_changed': bool,
                'old_status': ...,
                'new_status': ...,
                'content_changed': bool,
                'check_date': ...
            }
        """
        url = url_info['url']
        program_name = url_info['program_name']
        
        print(f"  Checking: {program_name} ({url_info['program_id']})")
        
        # Use deep verification to check URL
        verification_result = self.verifier.verify_url(url, program_name)
        
        old_status = url_info['current_status']
        new_status = verification_result.get('status', 'unclear')
        
        # Check if content changed (based on verification result)
        content_changed = verification_result.get('content_changed', False)
        
        return {
            'program_id': url_info['program_id'],
            'program_name': program_name,
            'url': url,
            'status_changed': old_status != new_status,
            'old_status': old_status,
            'new_status': new_status,
            'content_changed': content_changed,
            'check_date': datetime.now().isoformat(),
            'verification_details': verification_result
        }
    
    def run_maintenance_check(self) -> Dict:
        """
        Check all active URLs for changes
        
        Returns:
            Summary of changes found
        """
        print("🔍 Starting maintenance check...")
        print("=" * 60)
        
        urls_to_check = self.get_active_urls()
        print(f"✓ Found {len(urls_to_check)} active URLs to check\n")
        
        if len(urls_to_check) == 0:
            print("⚠️  No active URLs found to check")
            return {
                'total_checked': 0,
                'status_changes': [],
                'content_changes': [],
                'results': [],
                'check_date': datetime.now().isoformat()
            }
        
        results = []
        status_changes = []
        content_changes = []
        
        for i, url_info in enumerate(urls_to_check, 1):
            print(f"[{i}/{len(urls_to_check)}] ", end="")
            result = self.check_url_status(url_info)
            results.append(result)
            
            if result['status_changed']:
                status_changes.append(result)
                print(f"    ⚠️  STATUS CHANGED: {result['old_status']} → {result['new_status']}")
            
            if result['content_changed']:
                content_changes.append(result)
                print(f"    📝 Content changed")
        
        print(f"\n{'='*60}")
        print(f"📊 Maintenance Check Summary")
        print(f"{'='*60}")
        print(f"Total checked: {len(results)}")
        print(f"Status changes: {len(status_changes)}")
        print(f"Content changes: {len(content_changes)}")
        
        return {
            'total_checked': len(results),
            'status_changes': status_changes,
            'content_changes': content_changes,
            'results': results,
            'check_date': datetime.now().isoformat()
        }
    
    def save_results(self, results: Dict, output_path: str = 'maintenance_check.json'):
        """Save maintenance check results"""
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results saved to {output_path}")
    
    def generate_update_plan(self, results: Dict) -> List[Dict]:
        """
        Generate action plan for status updates
        
        Returns:
            List of update actions
        """
        updates = []
        
        for change in results['status_changes']:
            updates.append({
                'action': 'UPDATE_STATUS',
                'program_id': change['program_id'],
                'program_name': change['program_name'],
                'old_status': change['old_status'],
                'new_status': change['new_status'],
                'url': change['url'],
                'check_date': change['check_date']
            })
        
        return updates

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Maintenance monitor for checking active program URLs")
    parser.add_argument('--database', default='agents/Golden_Dataset.xlsx', help='Path to golden dataset')
    parser.add_argument('--output', default='maintenance_check.json', help='Output file for results')
    
    args = parser.parse_args()
    
    monitor = MaintenanceMonitor(args.database)
    results = monitor.run_maintenance_check()
    
    monitor.save_results(results, args.output)
    
    # Generate update plan
    if results['status_changes']:
        print(f"\n{'='*60}")
        print("UPDATE PLAN")
        print(f"{'='*60}")
        updates = monitor.generate_update_plan(results)
        for update in updates:
            print(f"  {update['program_id']}: {update['old_status']} → {update['new_status']}")

