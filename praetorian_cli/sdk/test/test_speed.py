import time
import statistics
from typing import List, Dict, Any, Callable, Optional
import json
from tabulate import tabulate

from praetorian_cli.sdk.keychain import Keychain
from praetorian_cli.sdk.test.utils import setup_chariot
from praetorian_cli.sdk.chariot import Chariot


class APISpeedTest:

    def __init__(self, profile: Optional[str] = None, account: Optional[str] = None, iterations: int = 3):
        """
        Args:
            profile: Keychain profile name (defaults to CHARIOT_TEST_PROFILE)
            account: Account to use
            iterations: Number of iterations to run each test
        """
        if profile:
            self.api = Chariot(Keychain(profile=profile, account=account))
        else:
            self.api = setup_chariot()
        self.results = []
        self.iterations = iterations

    def run_tests(self, test_name: str, output: Optional[str] = None):
        if test_name == 'assets':
            self.run_asset_tests()
        elif test_name == 'search':
            self.run_search_tests()
        elif test_name == 'risks':
            self.run_risk_tests()
        else:
            self.run_all_tests()

        self.print_results()

        if output:
            self.save_results(output)

    def run_all_tests(self):
        self.run_asset_tests()
        self.run_search_tests()
        self.run_risk_tests()


    def run_asset_tests(self):
        self.time_function(
            self.api.assets.list,
            "List Assets",
            iterations=self.iterations,
            prefix_filter='',
            pages=100000
        )

        assets, _ = self.api.assets.list(prefix_filter='', pages=1)
        if assets and len(assets) > 0:
            asset_key = assets[0]['key']
            self.time_function(
                self.api.assets.get,
                "Get Single Asset Details",
                iterations=self.iterations,
                key=asset_key,
                details=True
            )

    def run_search_tests(self):
        self.time_function(
            self.api.search.by_key_prefix,
            "Search by Key Prefix",
            iterations=self.iterations,
            key_prefix='#asset#',
            pages=100000
        )
        self.time_function(
            self.api.search.by_source,
            "Search by Source",
            iterations=1, # 1 iteration is enough for this test
            source='#asset#',
            kind='attribute',
            pages=100000
        )

    def run_risk_tests(self):
        self.time_function(
            self.api.risks.list,
            "List All Risks",
            iterations=self.iterations,
            pages=100000
        )

    def time_function(self, func: Callable, name: str, iterations: int = 3, **kwargs) -> Dict[str, Any]:
        """
        Args:
            func: Function to time
            name: Name of the function for reporting
            iterations: Number of times to run the function
            **kwargs: Arguments to pass to the function
            
        Returns:
            Dictionary with timing results
        """
        times = []
        result_length = 0
        success = True
        
        print(f"Testing {name}...")
        
        for i in range(iterations):
            start_time = time.time()
            try:
                result = func(**kwargs)
                elapsed = time.time() - start_time
                times.append(elapsed)
                result_length = self._iteration_result(i, iterations, elapsed, result)
            except Exception as e:
                elapsed = time.time() - start_time
                times.append(elapsed)
                print(f"Error: {e}")
                result = str(e)
                success = False
                result_length = self._iteration_result(i, iterations, elapsed, result)
                
        stats = self._calculate_statistics(times, iterations)
        
        result_data = {
            "name": name,
            "iterations": iterations,
            "avg_time": stats["avg_time"],
            "min_time": stats["min_time"],
            "max_time": stats["max_time"],
            "std_dev": stats["std_dev"],
            "success": success,
            "resultsLength": result_length
        }
        
        self.results.append(result_data)
        return result_data
        
    def _iteration_result(self, iteration_index: int, total_iterations: int, elapsed: float, result: Any):
        if not result:
            print(f"  Iteration {iteration_index+1}/{total_iterations}: {elapsed:.4f} seconds")
            return -1
        if isinstance(result, tuple):
            print(f"  Iteration {iteration_index+1}/{total_iterations}: {elapsed:.4f} seconds returned {len(result[0])} results")
            return len(result[0])   
        elif isinstance(result, dict):
            print(f"  Iteration {iteration_index+1}/{total_iterations}: {elapsed:.4f} seconds returned 1 result")
            return 1
        else:
            print(f"  Iteration {iteration_index+1}/{total_iterations}: {elapsed:.4f} seconds returned error: {result}")
            return 0
        
    def _calculate_statistics(self, times: List[float], iterations: int) -> Dict[str, float]:
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

    def print_results(self):
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
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Results saved to {filename}")
