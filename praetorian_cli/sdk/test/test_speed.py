#!/usr/bin/env python3
"""
API Speed Test Reference Script

This script serves as a reference for testing the speed of Praetorian API calls.
It is designed to be used by external users of the API to benchmark performance.
"""

import argparse
import time
import statistics
from typing import List, Dict, Any, Callable
import json
from tabulate import tabulate
import sys
from pathlib import Path

from praetorian_cli.sdk.keychain import Keychain, DEFAULT_PROFILE, DEFAULT_API, DEFAULT_CLIENT_ID
from praetorian_cli.sdk.chariot import Chariot


class APISpeedTest:
    """Class to test and measure the speed of Praetorian API calls"""

    def __init__(self, username=None, password=None, profile=DEFAULT_PROFILE, 
                 api=DEFAULT_API, client_id=DEFAULT_CLIENT_ID, account=None,
                 keychain_filepath=None):
        """
        Initialize the speed test with keychain details
        
        Args:
            username: Praetorian username (optional if using existing keychain)
            password: Praetorian password (optional if using existing keychain)
            profile: Keychain profile name (default: DEFAULT_PROFILE)
            api: API endpoint URL (default: DEFAULT_API)
            client_id: Client ID (default: DEFAULT_CLIENT_ID)
            account: Account to use (optional)
            keychain_filepath: Custom path to keychain file (optional)
        """
        if username and password:
            auth_params = {
                'username': username,
                'password': password,
                'profile': profile,
                'api': api if api else None,
                'client_id': client_id if client_id else None,
                'account': account if account else None
            }
            auth_params = {k: v for k, v in auth_params.items() if v is not None}
            Keychain.configure(**auth_params)
            
        # Create keychain instance with only necessary parameters
        keychain_kwargs = {'profile': profile}
        if keychain_filepath:
            keychain_kwargs['filepath'] = keychain_filepath
        if account:
            keychain_kwargs['account'] = account
            
        # Initialize API client
        self.keychain = Keychain(**keychain_kwargs)
        self.api = Chariot(self.keychain)
        
        # Results storage
        self.results = []

    def time_function(self, func: Callable, name: str, iterations: int = 3, **kwargs) -> Dict[str, Any]:
        """
        Time a function call over multiple iterations
        
        Args:
            func: Function to time
            name: Name of the function for reporting
            iterations: Number of times to run the function
            **kwargs: Arguments to pass to the function
            
        Returns:
            Dictionary with timing results
        """
        times = []
        results = []
        success = True
        
        print(f"Testing {name}...")
        
        # Run the function for the specified number of iterations
        for i in range(iterations):
            start_time = time.time()
            try:
                result = func(**kwargs)
                results.append(result)
            except Exception as e:
                result = str(e)
                results.append(result)
                success = False
                
            # Calculate and store elapsed time
            elapsed = time.time() - start_time
            times.append(elapsed)
            
            self._print_iteration_result(i, iterations, elapsed, results[-1])
            
        # Calculate statistics
        stats = self._calculate_statistics(times, iterations)
        
        result_data = {
            "name": name,
            "iterations": iterations,
            "avg_time": stats["avg_time"],
            "min_time": stats["min_time"],
            "max_time": stats["max_time"],
            "std_dev": stats["std_dev"],
            "success": success,
            "results": results
        }
        
        self.results.append(result_data)
        return result_data
        
    def _print_iteration_result(self, iteration_index: int, total_iterations: int, elapsed: float, result: Any):
        """Helper method to print iteration results"""
        if result and isinstance(result, tuple):
            print(f"  Iteration {iteration_index+1}/{total_iterations}: {elapsed:.4f} seconds returned {len(result[0])} results")
        else:
            print(f"  Iteration {iteration_index+1}/{total_iterations}: {elapsed:.4f} seconds")
            
    def _calculate_statistics(self, times: List[float], iterations: int) -> Dict[str, float]:
        """Helper method to calculate timing statistics"""
        avg_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        
        std_dev = statistics.stdev(times) if iterations > 1 else 0
        
        return {
            "avg_time": avg_time,
            "min_time": min_time,
            "max_time": max_time,
            "std_dev": std_dev
        }

    def run_asset_tests(self, iterations: int = 3):
        """Run speed tests for asset-related API calls"""
        # List assets
        self.time_function(
            self.api.assets.list,
            "List Assets",
            iterations=iterations,
            prefix_filter='',
            pages=100000
        )
        # Get specific asset if available
        assets, _ = self.api.assets.list(prefix_filter='', pages=1)
        if assets and len(assets) > 0:
            asset_key = assets[0]['key']
            self.time_function(
                self.api.assets.get,
                "Get Asset Details",
                iterations=iterations,
                key=asset_key,
                details=True
            )

    def run_search_tests(self, iterations: int = 3):
        """Run speed tests for search-related API calls"""
        #Basic search
        self.time_function(
            self.api.search.by_key_prefix,
            "Search by Key Prefix",
            iterations=iterations,
            key_prefix='#asset#',
            pages=100000
        )
        self.time_function(
            self.api.search.by_source,
            "Search by Source",
            iterations=1,
            source='#asset#',
            kind='attribute',
            pages=100000
        )

    def run_risk_tests(self, iterations: int = 3):
        """Run speed tests for risk-related API calls"""
        # List risks
        self.time_function(
            self.api.risks.list,
            "List Risks",
            iterations=iterations,
            pages=100000
        )

    def run_all_tests(self, iterations: int = 3):
        """Run all available speed tests"""
        self.run_asset_tests(iterations)
        self.run_search_tests(iterations)
        self.run_risk_tests(iterations)
        
        # Add more test categories as needed

    def print_results(self):
        """Print the test results in a tabular format"""
        if not self.results:
            print("No test results available.")
            return
            
        table_data = []
        for result in self.results:
            table_data.append([
                result["name"],
                result["iterations"],
                f"{result['avg_time']:.4f}s",
                f"{result['min_time']:.4f}s",
                f"{result['max_time']:.4f}s",
                f"{result['std_dev']:.4f}s",
                "✓" if result["success"] else "✗"
            ])
            
        headers = ["API Call", "Iterations", "Avg Time", "Min Time", "Max Time", "Std Dev", "Success"]
        print("\nAPI Speed Test Results:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
    def save_results(self, filename: str):
        """Save the test results to a JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Results saved to {filename}")





def main():
    """Main function to run the speed test from command line"""
    parser = argparse.ArgumentParser(description='Test the speed of Praetorian API calls')
    
    # Authentication options
    auth_group = parser.add_argument_group('Authentication')
    auth_group.add_argument('--profile', help='Keychain profile name (defaults to United States)')
    auth_group.add_argument('--username', default='', help='Praetorian username')
    auth_group.add_argument('--password', default='', help='Praetorian password')
    auth_group.add_argument('--api', default='', help='API endpoint URL')
    auth_group.add_argument('--client-id', default='', help='Client ID')
    auth_group.add_argument('--account', default='', help='Account to use')
    auth_group.add_argument('--keychain-filepath', help='Custom path to keychain file')
    
    # Test options
    test_group = parser.add_argument_group('Test Options')
    test_group.add_argument('--iterations', type=int, default=3, help='Number of iterations for each test')
    test_group.add_argument('--test', choices=['assets', 'search', 'risks', 'all'], default='all',
                           help='Test category to run (default: all)')
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument('--output', help='Save results to this JSON file')
    
    args = parser.parse_args()
    
    # Create speed test instance with profile defaulting to DEFAULT_PROFILE if not specified
    speed_test = APISpeedTest(
        username=args.username,
        password=args.password,
        profile=args.profile if args.profile else DEFAULT_PROFILE,
        api=args.api,
        client_id=args.client_id,
        account=args.account,
        keychain_filepath=args.keychain_filepath
    )
    
    # Run selected test category
    if args.test == 'all':
        speed_test.run_all_tests(iterations=args.iterations)
    elif args.test == 'assets':
        speed_test.run_asset_tests(iterations=args.iterations)
    elif args.test == 'search':
        speed_test.run_search_tests(iterations=args.iterations)
    elif args.test == 'risks':
        speed_test.run_risk_tests(iterations=args.iterations)
    
    # Print results
    speed_test.print_results()
    
    # Save results if requested
    if args.output:
        speed_test.save_results(args.output)


if __name__ == "__main__":
    main()
