import time
import numpy as np
import matplotlib.pyplot as plt
import subprocess
import sys

def run_benchmark():
    print("Running benchmark comparisons...")
    
    # Number of runs for each implementation
    num_runs = 5
    
    # Run times for each implementation
    python_times = []
    cython_times = []
    
    # Run the Python implementation
    print("\nBenchmarking original Python implementation...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end="", flush=True)
        
        # Measure time for original implementation with small iteration count
        # We're using the -b flag to run in benchmark mode (this flag will be ignored if not implemented)
        start_time = time.time()
        subprocess.run(["python", "rock_paper_scissors_sim.py", "50", "50", "50", "-b", "300"], 
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        end_time = time.time()
        
        run_time = end_time - start_time
        python_times.append(run_time)
        print(f" {run_time:.2f} seconds")
    
    # Run the Cython implementation
    print("\nBenchmarking Cython implementation...")
    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs}...", end="", flush=True)
        
        # Measure time for Cython implementation with the same parameters
        start_time = time.time()
        subprocess.run(["python", "rock_paper_scissors_sim_cython.py", "50", "50", "50", "-b", "300"], 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        end_time = time.time()
        
        run_time = end_time - start_time
        cython_times.append(run_time)
        print(f" {run_time:.2f} seconds")
    
    # Calculate averages
    avg_python_time = np.mean(python_times)
    avg_cython_time = np.mean(cython_times)
    
    # Calculate speedup
    speedup = avg_python_time / avg_cython_time
    
    # Print results
    print("\nBenchmark Results:")
    print(f"  Original Python average time: {avg_python_time:.2f} seconds")
    print(f"  Cython optimized average time: {avg_cython_time:.2f} seconds")
    print(f"  Speedup: {speedup:.2f}x")
    
    # Create a bar chart to visualize the results
    labels = ['Python', 'Cython']
    times = [avg_python_time, avg_cython_time]
    
    plt.figure(figsize=(10, 6))
    bars = plt.bar(labels, times, color=['blue', 'orange'])
    plt.ylabel('Average Runtime (seconds)')
    plt.title('Performance Comparison: Python vs Cython')
    
    # Add the actual values on top of the bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                f'{height:.2f}s', ha='center', va='bottom')
    
    # Add speedup annotation
    plt.annotate(f'Speedup: {speedup:.2f}x', 
                 xy=(0.5, 0.9), 
                 xycoords='axes fraction',
                 ha='center',
                 va='center',
                 bbox=dict(boxstyle="round,pad=0.5", fc="yellow", alpha=0.5))
    
    # Save the figure
    plt.savefig('benchmark_results.png')
    print("Results saved to benchmark_results.png")
    
    return speedup

# Add a small modification to both files to add benchmark mode
def add_benchmark_mode():
    # Add code to parse a -b flag for benchmark mode with fewer frames
    with open('rock_paper_scissors_sim.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "# Benchmark support" not in content:
        with open('rock_paper_scissors_sim.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find the line where MAX_TIME is defined
        for i, line in enumerate(lines):
            if "MAX_TIME = " in line:
                # Insert benchmark check after this line
                benchmark_code = [
                    "\n# Benchmark support\n",
                    "if len(sys.argv) >= 5 and sys.argv[4] == '-b':\n",
                    "    MAX_TIME = int(sys.argv[5])\n",
                    "    print(f'Running in benchmark mode with MAX_TIME={MAX_TIME}')\n\n"
                ]
                lines[i:i] = benchmark_code
                break
        
        with open('rock_paper_scissors_sim.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print("Added benchmark mode to original Python implementation")
    
    # Add the same to the Cython implementation
    with open('rock_paper_scissors_sim_cython.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    if "# Benchmark support" not in content:
        with open('rock_paper_scissors_sim_cython.py', 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Find the line where MAX_TIME is defined
        for i, line in enumerate(lines):
            if "MAX_TIME = " in line:
                # Insert benchmark check after this line
                benchmark_code = [
                    "\n# Benchmark support\n",
                    "if len(sys.argv) >= 5 and sys.argv[4] == '-b':\n",
                    "    MAX_TIME = int(sys.argv[5])\n",
                    "    print(f'Running in benchmark mode with MAX_TIME={MAX_TIME}')\n\n"
                ]
                lines[i:i] = benchmark_code
                break
        
        with open('rock_paper_scissors_sim_cython.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
        print("Added benchmark mode to Cython implementation")

if __name__ == "__main__":
    # Add benchmark mode to both implementations
    add_benchmark_mode()
    
    # Run the benchmark
    speedup = run_benchmark()
    
    # Final summary
    print(f"\nOptimization summary: Cython implementation is {speedup:.2f}x faster than the original Python code.")
